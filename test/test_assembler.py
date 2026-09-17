# SPDX-FileCopyrightText: © 2026 Derek Su
# SPDX-License-Identifier: Apache-2.0

import pytest

from tools.assembler import alu_and, alu_or, alu_shl, alu_shr, alu_xor, halt, host, inp, jmp, jnz, jpin, jz, ldi, oe, out, outa, uart_tx8n1, wait


def test_encodes_v02_instructions():
    assert out(0xA5) == 0x10A5
    assert oe(0x81) == 0x2081
    assert wait(0) == 0x3000
    assert wait(0xFFF) == 0x3FFF
    assert halt() == 0xF000


def test_encodes_accumulator_data_instructions():
    assert inp() == 0x4000
    assert ldi(0xA5) == 0x50A5
    assert host() == 0x6000
    assert alu_and(0x0F) == 0x700F
    assert alu_or(0xF0) == 0x71F0
    assert alu_xor(0xFF) == 0x72FF
    assert alu_shl(1) == 0x7401
    assert alu_shr(1) == 0x7501
    assert jmp(0x3F) == 0x803F
    assert jz(0x3F) == 0x903F
    assert jnz(0x3F) == 0xA03F
    assert jpin(2, 1, 3) == 0xB503
    assert outa() == 0xC000


@pytest.mark.parametrize(
    ("encoder", "operand"),
    [
        (out, -1),
        (out, 0x100),
        (oe, -1),
        (oe, 0x100),
        (wait, -1),
        (wait, 0x1000),
        (ldi, -1),
        (ldi, 0x100),
        (alu_and, -1),
        (alu_and, 0x100),
        (alu_or, -1),
        (alu_or, 0x100),
        (alu_xor, -1),
        (alu_xor, 0x100),
        (alu_shl, -1),
        (alu_shl, 8),
        (alu_shr, -1),
        (alu_shr, 8),
        (jmp, -1),
        (jmp, 0x40),
        (jz, -1),
        (jz, 0x40),
        (jnz, -1),
        (jnz, 0x40),
        (lambda operand: jpin(operand, 0, 0), -1),
        (lambda operand: jpin(operand, 0, 0), 8),
        (lambda operand: jpin(0, operand, 0), -1),
        (lambda operand: jpin(0, operand, 0), 2),
        (lambda operand: jpin(0, 0, operand), -1),
        (lambda operand: jpin(0, 0, operand), 0x40),
    ],
)
def test_rejects_operands_that_do_not_fit(encoder, operand):
    with pytest.raises(ValueError):
        encoder(operand)


def test_generates_uart_8n1_firmware_for_runtime_selected_byte():
    program = uart_tx8n1(0x55, tx_mask=0x01, bit_ticks=4)

    frame_bits = [0] + [(0x55 >> bit) & 1 for bit in range(8)] + [1]
    expected = [oe(0x01), out(0x01), wait(2)]
    for bit in frame_bits:
        expected.extend((out(bit), wait(2)))
    expected.append(halt())

    assert program == expected
    assert len(program) <= 64


@pytest.mark.parametrize("bit_ticks", [0, 1])
def test_uart_rejects_bit_period_too_short_for_out_wait_pair(bit_ticks):
    with pytest.raises(ValueError):
        uart_tx8n1(0x55, tx_mask=0x01, bit_ticks=bit_ticks)
