# SPDX-FileCopyrightText: © 2026 Derek Su
# SPDX-License-Identifier: Apache-2.0

import inspect

import pytest

from tools import assembler
from tools.assembler import alu_add, alu_and, alu_asr, alu_neg, alu_not, alu_or, alu_parity, alu_popcnt, alu_rev, alu_rol, alu_ror, alu_shl, alu_shr, alu_sub, alu_swap, alu_xor, halt, host, inp, jmp, jnz, jpin, jz, ldi, oe, oea, out, outa, outbit, uart_tx8n1, wait


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
    assert alu_add(0x07) == 0x7307
    assert alu_shl(1) == 0x7401
    assert alu_shr(1) == 0x7501
    assert alu_sub(0x07) == 0x7607
    assert alu_ror(1) == 0x7701
    assert alu_rol(1) == 0x7801
    assert alu_not() == 0x7900
    assert alu_neg() == 0x7A00
    assert alu_asr(1) == 0x7B01
    assert alu_rev() == 0x7C00
    assert alu_swap() == 0x7D00
    assert alu_popcnt() == 0x7E00
    assert alu_parity() == 0x7F00
    assert jmp(0x3F) == 0x803F
    assert jz(0x3F) == 0x903F
    assert jnz(0x3F) == 0xA03F
    assert jpin(2, 1, 3) == 0xB503
    assert outa() == 0xC000
    assert outbit(7) == 0xD007
    assert outbit(2, source_bit=7) == 0xD03A
    assert oea() == 0xE000


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
        (alu_add, -1),
        (alu_add, 0x100),
        (alu_shl, -1),
        (alu_shl, 8),
        (alu_shr, -1),
        (alu_shr, 8),
        (alu_sub, -1),
        (alu_sub, 0x100),
        (alu_ror, -1),
        (alu_ror, 8),
        (alu_rol, -1),
        (alu_rol, 8),
        (alu_asr, -1),
        (alu_asr, 8),
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
        (outbit, -1),
        (outbit, 8),
        (lambda operand: outbit(0, source_bit=operand), -1),
        (lambda operand: outbit(0, source_bit=operand), 8),
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


def test_generates_uart_8n1_firmware_for_runtime_pin_byte():
    assert hasattr(assembler, "uart_tx8n1_from_pins")

    program = assembler.uart_tx8n1_from_pins(tx_mask=0x01, bit_ticks=4)
    expected = [inp(), oe(0x01), out(0x01), wait(2)]
    expected.extend((out(0), wait(1), alu_shr(0)))
    for _ in range(8):
        expected.extend((outbit(0), wait(1), alu_shr(1)))
    expected.extend((out(0x01), halt()))

    assert program == expected
    assert len(program) <= 64


def test_generates_runtime_uart_on_selected_protocol_pin():
    program = assembler.uart_tx8n1_from_pins(tx_mask=0x08, bit_ticks=4)

    expected = [inp(), oe(0x08), out(0x08), wait(2)]
    expected.extend((out(0), wait(1), alu_shr(0)))
    for _ in range(8):
        expected.extend((outbit(3), wait(1), alu_shr(1)))
    expected.extend((out(0x08), halt()))

    assert program == expected
    assert len(program) <= 64


def test_runtime_uart_on_pin_zero_uses_selected_bit_updates():
    program = assembler.uart_tx8n1_from_pins(tx_mask=0x01, bit_ticks=4)

    assert program.count(outbit(0)) == 8


def test_generates_two_tick_runtime_uart_without_waits_between_bits():
    expected = [inp(), oe(0x08), out(0x08), wait(0), out(0), alu_shr(0)]
    for _ in range(8):
        expected.extend((outbit(3), alu_shr(1)))
    expected.extend((out(0x08), halt()))

    program = assembler.uart_tx8n1_from_pins(tx_mask=0x08, bit_ticks=2)

    assert program == expected
    assert len(program) <= 64


def test_generates_uart_8n1_firmware_for_runtime_host_byte():
    assert hasattr(assembler, "uart_tx8n1_from_host")

    program = assembler.uart_tx8n1_from_host(tx_mask=0x01, bit_ticks=4)
    expected = [0x0000, host(), oe(0x01), out(0x01), wait(2)]
    expected.extend((out(0), wait(1), alu_shr(0)))
    for _ in range(8):
        expected.extend((outbit(0), wait(1), alu_shr(1)))
    expected.extend((out(0x01), halt()))

    assert program == expected
    assert len(program) <= 64


def test_runtime_host_uart_preserves_configured_background_outputs():
    signature = inspect.signature(assembler.uart_tx8n1_from_host)
    assert "background_output" in signature.parameters

    program = assembler.uart_tx8n1_from_host(
        tx_mask=0x08, bit_ticks=4, background_output=0xA0
    )

    assert program[3] == out(0xA8)  # Idle-high TX plus background outputs.
    assert program[5] == out(0xA0)  # Start bit only clears TX.
    assert program[-2] == out(0xA8)  # Stop/idle restores TX without clearing them.


def test_runtime_host_uart_enables_configured_background_outputs():
    signature = inspect.signature(assembler.uart_tx8n1_from_host)
    assert "background_oe" in signature.parameters

    program = assembler.uart_tx8n1_from_host(
        tx_mask=0x08,
        bit_ticks=4,
        background_output=0xA0,
        background_oe=0xA4,
    )

    assert program[2] == oe(0xAC)


def test_runtime_uart_preserves_configured_background_outputs():
    signature = inspect.signature(assembler.uart_tx8n1_from_pins)
    assert "background_output" in signature.parameters

    program = assembler.uart_tx8n1_from_pins(
        tx_mask=0x08, bit_ticks=4, background_output=0xA0
    )

    assert program[2] == out(0xA8)  # Idle-high TX plus background outputs.
    assert program[4] == out(0xA0)  # Start bit only clears TX.
    assert program[-2] == out(0xA8)  # Stop/idle restores TX without clearing them.


def test_runtime_pin_uart_enables_configured_background_outputs():
    signature = inspect.signature(assembler.uart_tx8n1_from_pins)
    assert "background_oe" in signature.parameters

    program = assembler.uart_tx8n1_from_pins(
        tx_mask=0x08,
        bit_ticks=4,
        background_output=0xA0,
        background_oe=0xA4,
    )

    assert program[1] == oe(0xAC)


def test_runtime_pin_uart_xors_sampled_byte_before_transmission():
    signature = inspect.signature(assembler.uart_tx8n1_from_pins)
    assert "data_xor" in signature.parameters

    program = assembler.uart_tx8n1_from_pins(
        tx_mask=0x08, bit_ticks=4, data_xor=0xFF
    )

    assert program[:3] == [inp(), alu_xor(0xFF), oe(0x08)]


def test_runtime_pin_uart_masks_sampled_byte_before_transmission():
    signature = inspect.signature(assembler.uart_tx8n1_from_pins)
    assert "data_and" in signature.parameters

    program = assembler.uart_tx8n1_from_pins(
        tx_mask=0x08, bit_ticks=4, data_and=0x0F
    )

    assert program[:3] == [inp(), alu_and(0x0F), oe(0x08)]


def test_runtime_pin_uart_sets_sampled_byte_bits_before_transmission():
    signature = inspect.signature(assembler.uart_tx8n1_from_pins)
    assert "data_or" in signature.parameters

    program = assembler.uart_tx8n1_from_pins(
        tx_mask=0x08, bit_ticks=4, data_or=0xA0
    )

    assert program[:3] == [inp(), alu_or(0xA0), oe(0x08)]


def test_runtime_host_uart_xors_sampled_byte_before_transmission():
    signature = inspect.signature(assembler.uart_tx8n1_from_host)
    assert "data_xor" in signature.parameters

    program = assembler.uart_tx8n1_from_host(
        tx_mask=0x08, bit_ticks=4, data_xor=0xA5
    )

    assert program[:4] == [0x0000, host(), alu_xor(0xA5), oe(0x08)]


def test_runtime_host_uart_masks_sampled_byte_before_transmission():
    signature = inspect.signature(assembler.uart_tx8n1_from_host)
    assert "data_and" in signature.parameters

    program = assembler.uart_tx8n1_from_host(
        tx_mask=0x08, bit_ticks=4, data_and=0x0F
    )

    assert program[:4] == [0x0000, host(), alu_and(0x0F), oe(0x08)]


@pytest.mark.parametrize("bit_ticks", [0, 1])
def test_uart_rejects_bit_period_too_short_for_out_wait_pair(bit_ticks):
    with pytest.raises(ValueError):
        uart_tx8n1(0x55, tx_mask=0x01, bit_ticks=bit_ticks)
