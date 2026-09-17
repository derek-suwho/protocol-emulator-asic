# SPDX-FileCopyrightText: © 2026 Derek Su
# SPDX-License-Identifier: Apache-2.0

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, ReadOnly, RisingEdge, Timer


CLOCK_PERIOD_US = 1


async def reset_dut(dut):
    dut.ena.value = 1
    dut.ui_in.value = 0
    dut.uio_in.value = 0
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 4)
    dut.rst_n.value = 1
    await RisingEdge(dut.clk)


async def load_instruction_lsb_first(dut, instruction):
    """Shift one 16-bit instruction through cfg_data, then commit it."""
    for bit_index in range(16):
        cfg_data = (instruction >> bit_index) & 1
        dut.ui_in.value = cfg_data | (1 << 1)  # cfg_shift=1
        await RisingEdge(dut.clk)

    dut.ui_in.value = 1 << 2  # cfg_commit=1
    await RisingEdge(dut.clk)
    dut.ui_in.value = 0
    await RisingEdge(dut.clk)


@cocotb.test()
async def test_loaded_out_instruction_drives_protocol_pins(dut):
    """A loaded OUT-immediate instruction must deterministically drive the pins."""
    cocotb.start_soon(Clock(dut.clk, CLOCK_PERIOD_US, unit="us").start())
    await reset_dut(dut)

    # ISA v0: 0x1IMM = OUT immediate; 0xF000 = HALT.
    await load_instruction_lsb_first(dut, 0x10A5)
    await load_instruction_lsb_first(dut, 0xF000)

    dut.ui_in.value = 1 << 3  # run=1
    await ClockCycles(dut.clk, 2)

    assert dut.uio_out.value == 0xA5
    assert dut.uio_oe.value == 0x00


@cocotb.test()
async def test_programmed_pin0_pulse_has_exact_width(dut):
    """OE/OUT/WAIT must produce a three-clock enabled-high pulse."""
    cocotb.start_soon(Clock(dut.clk, CLOCK_PERIOD_US, unit="us").start())
    await reset_dut(dut)

    # OE pin 0, raise pin 0, wait one additional tick, lower pin 0, halt.
    for instruction in (0x2001, 0x1001, 0x3001, 0x1000, 0xF000):
        await load_instruction_lsb_first(dut, instruction)

    # Configuration must not drive protocol pins.
    assert dut.uio_out.value == 0x00
    assert dut.uio_oe.value == 0x00

    dut.ui_in.value = 1 << 3

    # OE retires first, then OUT raises the pin.
    await RisingEdge(dut.clk)
    await ReadOnly()
    assert dut.uio_oe.value == 0x01
    assert dut.uio_out.value == 0x00

    expected_pin0 = (1, 1, 1, 0)
    for expected in expected_pin0:
        await RisingEdge(dut.clk)
        await ReadOnly()
        assert (int(dut.uio_out.value) & 1) == expected
        assert dut.uio_oe.value == 0x01


@cocotb.test()
async def test_firmware_transmits_uart_8n1_byte(dut):
    """Firmware alone must transmit 0x55 as a cycle-exact UART 8N1 frame."""
    cocotb.start_soon(Clock(dut.clk, CLOCK_PERIOD_US, unit="us").start())
    await reset_dut(dut)

    bit_ticks = 4
    wait_operand = bit_ticks - 2
    frame_bits = [0] + [(0x55 >> bit) & 1 for bit in range(8)] + [1]

    # Configure TX pin 0 as an output and establish one idle-high bit period.
    firmware = [0x2001, 0x1001, 0x3000 | wait_operand]
    for bit in frame_bits:
        firmware.extend((0x1000 | bit, 0x3000 | wait_operand))
    firmware.append(0xF000)

    for instruction in firmware:
        await load_instruction_lsb_first(dut, instruction)

    dut.ui_in.value = 1 << 3

    # Retire OE, then hold the idle-high level for exactly one bit period.
    await RisingEdge(dut.clk)
    await ReadOnly()
    assert dut.uio_oe.value == 0x01
    assert dut.uio_out.value == 0x00

    for _ in range(bit_ticks):
        await RisingEdge(dut.clk)
        await ReadOnly()
        assert (int(dut.uio_out.value) & 1) == 1

    # Start, eight data bits LSB-first, and one stop bit.
    for expected_bit in frame_bits:
        for _ in range(bit_ticks):
            await RisingEdge(dut.clk)
            await ReadOnly()
            assert (int(dut.uio_out.value) & 1) == expected_bit
            assert dut.uio_oe.value == 0x01


@cocotb.test()
async def test_ldi_and_outa_drive_accumulator_value(dut):
    """LDI must load the accumulator and OUTA must copy it to protocol pins."""
    cocotb.start_soon(Clock(dut.clk, CLOCK_PERIOD_US, unit="us").start())
    await reset_dut(dut)

    for instruction in (0x50A5, 0xC000, 0xF000):
        await load_instruction_lsb_first(dut, instruction)

    dut.ui_in.value = 1 << 3

    await RisingEdge(dut.clk)  # LDI
    await ReadOnly()
    assert dut.uio_out.value == 0x00

    await RisingEdge(dut.clk)  # OUTA
    await ReadOnly()
    assert dut.uio_out.value == 0xA5


@cocotb.test()
async def test_in_samples_protocol_pins_for_later_firmware_output(dut):
    """IN must retain one pin sample in the accumulator for a later OUTA."""
    cocotb.start_soon(Clock(dut.clk, CLOCK_PERIOD_US, unit="us").start())
    await reset_dut(dut)

    for instruction in (0x4000, 0xC000, 0xF000):
        await load_instruction_lsb_first(dut, instruction)

    dut.uio_in.value = 0xA5
    dut.ui_in.value = 1 << 3
    await RisingEdge(dut.clk)  # IN samples 0xA5.
    await ReadOnly()
    assert dut.uio_out.value == 0x00

    await Timer(1, unit="ns")
    dut.uio_in.value = 0x3C  # Prove OUTA uses the retained sample, not live pins.
    await RisingEdge(dut.clk)
    await ReadOnly()
    assert dut.uio_out.value == 0xA5


@cocotb.test()
async def test_host_samples_runtime_byte_for_later_firmware_output(dut):
    """HOST must retain one host byte in the accumulator for a later OUTA."""
    cocotb.start_soon(Clock(dut.clk, CLOCK_PERIOD_US, unit="us").start())
    await reset_dut(dut)

    for instruction in (0x6000, 0xC000, 0xF000):
        await load_instruction_lsb_first(dut, instruction)

    dut.ui_in.value = 0xAD  # run=1 and runtime host byte 0xAD.
    await RisingEdge(dut.clk)  # HOST samples 0xAD.
    await ReadOnly()
    assert dut.uio_out.value == 0x00

    await Timer(1, unit="ns")
    dut.ui_in.value = 0x5B  # Prove OUTA uses the retained byte, not live ui_in.
    await RisingEdge(dut.clk)
    await ReadOnly()
    assert dut.uio_out.value == 0xAD


@cocotb.test()
async def test_run_pulse_allows_host_to_sample_byte_with_bit3_clear(dut):
    """Once started, execution must continue while host data drives run low."""
    cocotb.start_soon(Clock(dut.clk, CLOCK_PERIOD_US, unit="us").start())
    await reset_dut(dut)

    # NOP gives the host one cycle to replace the run pulse with runtime data.
    for instruction in (0x0000, 0x6000, 0xC000, 0xF000):
        await load_instruction_lsb_first(dut, instruction)

    dut.ui_in.value = 1 << 3  # Pulse run for NOP.
    await RisingEdge(dut.clk)
    dut.ui_in.value = 0xA5  # Runtime byte has bit 3 clear.
    await RisingEdge(dut.clk)  # HOST
    await RisingEdge(dut.clk)  # OUTA
    await ReadOnly()

    assert dut.uio_out.value == 0xA5


@cocotb.test()
async def test_alu_xor_immediate_updates_accumulator(dut):
    """ALU XOR-immediate must update the accumulator consumed by OUTA."""
    cocotb.start_soon(Clock(dut.clk, CLOCK_PERIOD_US, unit="us").start())
    await reset_dut(dut)

    # LDI 0xA5; ALU XOR,0xFF; OUTA; HALT.
    for instruction in (0x50A5, 0x72FF, 0xC000, 0xF000):
        await load_instruction_lsb_first(dut, instruction)

    dut.ui_in.value = 1 << 3
    await ClockCycles(dut.clk, 3)
    await ReadOnly()

    assert dut.uio_out.value == 0x5A


@cocotb.test()
async def test_alu_add_immediate_wraps_accumulator(dut):
    """ALU ADD-immediate must update the accumulator with eight-bit wraparound."""
    cocotb.start_soon(Clock(dut.clk, CLOCK_PERIOD_US, unit="us").start())
    await reset_dut(dut)

    # LDI 0xFE; ALU ADD,0x07; OUTA; HALT.
    for instruction in (0x50FE, 0x7307, 0xC000, 0xF000):
        await load_instruction_lsb_first(dut, instruction)

    dut.ui_in.value = 1 << 3
    await ClockCycles(dut.clk, 3)
    await ReadOnly()

    assert dut.uio_out.value == 0x05


@cocotb.test()
async def test_alu_sub_immediate_wraps_accumulator(dut):
    """ALU SUB-immediate must update the accumulator with eight-bit wraparound."""
    cocotb.start_soon(Clock(dut.clk, CLOCK_PERIOD_US, unit="us").start())
    await reset_dut(dut)

    # LDI 0x03; ALU SUB,0x07; OUTA; HALT.
    for instruction in (0x5003, 0x7607, 0xC000, 0xF000):
        await load_instruction_lsb_first(dut, instruction)

    dut.ui_in.value = 1 << 3
    await ClockCycles(dut.clk, 3)
    await ReadOnly()

    assert dut.uio_out.value == 0xFC


@cocotb.test()
async def test_alu_or_immediate_sets_accumulator_bits(dut):
    """ALU OR-immediate must set accumulator bits for later output."""
    cocotb.start_soon(Clock(dut.clk, CLOCK_PERIOD_US, unit="us").start())
    await reset_dut(dut)

    # LDI 0x50; ALU OR,0x0F; OUTA; HALT.
    for instruction in (0x5050, 0x710F, 0xC000, 0xF000):
        await load_instruction_lsb_first(dut, instruction)

    dut.ui_in.value = 1 << 3
    await ClockCycles(dut.clk, 3)
    await ReadOnly()

    assert dut.uio_out.value == 0x5F


@cocotb.test()
async def test_alu_shift_right_immediate_updates_accumulator(dut):
    """ALU SHR-immediate must logically shift the accumulator for later output."""
    cocotb.start_soon(Clock(dut.clk, CLOCK_PERIOD_US, unit="us").start())
    await reset_dut(dut)

    # LDI 0xA5; ALU SHR,1; OUTA; HALT.
    for instruction in (0x50A5, 0x7501, 0xC000, 0xF000):
        await load_instruction_lsb_first(dut, instruction)

    dut.ui_in.value = 1 << 3
    await ClockCycles(dut.clk, 3)
    await ReadOnly()

    assert dut.uio_out.value == 0x52


@cocotb.test()
async def test_alu_and_immediate_masks_accumulator(dut):
    """ALU AND-immediate must mask the accumulator for later output."""
    cocotb.start_soon(Clock(dut.clk, CLOCK_PERIOD_US, unit="us").start())
    await reset_dut(dut)

    # LDI 0xA5; ALU AND,0x0F; OUTA; HALT.
    for instruction in (0x50A5, 0x700F, 0xC000, 0xF000):
        await load_instruction_lsb_first(dut, instruction)

    dut.ui_in.value = 1 << 3
    await ClockCycles(dut.clk, 3)
    await ReadOnly()

    assert dut.uio_out.value == 0x05


@cocotb.test()
async def test_alu_shift_left_immediate_updates_accumulator(dut):
    """ALU SHL-immediate must logically shift the accumulator for later output."""
    cocotb.start_soon(Clock(dut.clk, CLOCK_PERIOD_US, unit="us").start())
    await reset_dut(dut)

    # LDI 0x25; ALU SHL,1; OUTA; HALT.
    for instruction in (0x5025, 0x7401, 0xC000, 0xF000):
        await load_instruction_lsb_first(dut, instruction)

    dut.ui_in.value = 1 << 3
    await ClockCycles(dut.clk, 3)
    await ReadOnly()

    assert dut.uio_out.value == 0x4A


@cocotb.test()
async def test_jmp_skips_intervening_instruction(dut):
    """JMP must continue execution at its six-bit absolute target."""
    cocotb.start_soon(Clock(dut.clk, CLOCK_PERIOD_US, unit="us").start())
    await reset_dut(dut)

    # OUT 0x11; JMP 3; OUT 0x22 (skipped); OUT 0xA5; HALT.
    for instruction in (0x1011, 0x8003, 0x1022, 0x10A5, 0xF000):
        await load_instruction_lsb_first(dut, instruction)

    dut.ui_in.value = 1 << 3
    await ClockCycles(dut.clk, 3)
    await ReadOnly()

    assert dut.uio_out.value == 0xA5


@cocotb.test()
async def test_jz_branches_when_accumulator_is_zero(dut):
    """JZ must continue at its absolute target when the accumulator is zero."""
    cocotb.start_soon(Clock(dut.clk, CLOCK_PERIOD_US, unit="us").start())
    await reset_dut(dut)

    # LDI 0; JZ 4; OUT 0x22 (skipped); HALT; OUT 0xA5; HALT.
    for instruction in (0x5000, 0x9004, 0x1022, 0xF000, 0x10A5, 0xF000):
        await load_instruction_lsb_first(dut, instruction)

    dut.ui_in.value = 1 << 3
    await ClockCycles(dut.clk, 3)
    await ReadOnly()

    assert dut.uio_out.value == 0xA5


@cocotb.test()
async def test_jnz_branches_when_accumulator_is_nonzero(dut):
    """JNZ must continue at its absolute target when the accumulator is nonzero."""
    cocotb.start_soon(Clock(dut.clk, CLOCK_PERIOD_US, unit="us").start())
    await reset_dut(dut)

    # LDI 1; JNZ 4; OUT 0x22 (skipped); HALT; OUT 0xA5; HALT.
    for instruction in (0x5001, 0xA004, 0x1022, 0xF000, 0x10A5, 0xF000):
        await load_instruction_lsb_first(dut, instruction)

    dut.ui_in.value = 1 << 3
    await ClockCycles(dut.clk, 3)
    await ReadOnly()

    assert dut.uio_out.value == 0xA5


@cocotb.test()
async def test_jpin_branches_when_selected_protocol_pin_matches(dut):
    """JPIN must branch when the selected live protocol pin matches its value."""
    cocotb.start_soon(Clock(dut.clk, CLOCK_PERIOD_US, unit="us").start())
    await reset_dut(dut)

    # JPIN pin 2,high,3; OUT 0x22; HALT; OUT 0xA5; HALT.
    # Encoding: opcode B, pin in [11:9], value in [8], target in [5:0].
    for instruction in (0xB503, 0x1022, 0xF000, 0x10A5, 0xF000):
        await load_instruction_lsb_first(dut, instruction)

    dut.uio_in.value = 1 << 2
    dut.ui_in.value = 1 << 3
    await ClockCycles(dut.clk, 2)
    await ReadOnly()

    assert dut.uio_out.value == 0xA5
