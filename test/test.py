# SPDX-FileCopyrightText: © 2026 Derek Su
# SPDX-License-Identifier: Apache-2.0

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, RisingEdge


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
