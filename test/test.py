# SPDX-FileCopyrightText: © 2026 Derek Su
# SPDX-License-Identifier: Apache-2.0

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, ReadOnly, RisingEdge


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
