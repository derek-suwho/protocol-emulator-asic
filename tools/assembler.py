# SPDX-FileCopyrightText: © 2026 Derek Su
# SPDX-License-Identifier: Apache-2.0

"""Assembler helpers for the verified Protocol Emulator ISA."""


def _checked(value: int, bits: int, name: str) -> int:
    if not isinstance(value, int) or not 0 <= value < (1 << bits):
        raise ValueError(f"{name} must fit in {bits} unsigned bits")
    return value


def out(value: int) -> int:
    """Encode OUT imm8."""
    return 0x1000 | _checked(value, 8, "OUT operand")


def oe(value: int) -> int:
    """Encode OE imm8."""
    return 0x2000 | _checked(value, 8, "OE operand")


def wait(additional_ticks: int) -> int:
    """Encode WAIT imm12; total OUT-to-OUT duration is operand + 2 ticks."""
    return 0x3000 | _checked(additional_ticks, 12, "WAIT operand")


def inp() -> int:
    """Encode IN."""
    return 0x4000


def ldi(value: int) -> int:
    """Encode LDI imm8."""
    return 0x5000 | _checked(value, 8, "LDI operand")


def host() -> int:
    """Encode HOST."""
    return 0x6000


def alu_and(value: int) -> int:
    """Encode ALU AND,imm8."""
    return 0x7000 | _checked(value, 8, "ALU AND operand")


def alu_or(value: int) -> int:
    """Encode ALU OR,imm8."""
    return 0x7100 | _checked(value, 8, "ALU OR operand")


def alu_xor(value: int) -> int:
    """Encode ALU XOR,imm8."""
    return 0x7200 | _checked(value, 8, "ALU XOR operand")


def alu_add(value: int) -> int:
    """Encode ALU ADD,imm8."""
    return 0x7300 | _checked(value, 8, "ALU ADD operand")


def alu_shl(amount: int) -> int:
    """Encode ALU logical shift-left by a three-bit immediate."""
    return 0x7400 | _checked(amount, 3, "ALU SHL operand")


def alu_shr(amount: int) -> int:
    """Encode ALU logical shift-right by a three-bit immediate."""
    return 0x7500 | _checked(amount, 3, "ALU SHR operand")


def alu_sub(value: int) -> int:
    """Encode ALU SUB,imm8."""
    return 0x7600 | _checked(value, 8, "ALU SUB operand")


def jmp(address: int) -> int:
    """Encode JMP addr6."""
    return 0x8000 | _checked(address, 6, "JMP address")


def jz(address: int) -> int:
    """Encode JZ addr6."""
    return 0x9000 | _checked(address, 6, "JZ address")


def jnz(address: int) -> int:
    """Encode JNZ addr6."""
    return 0xA000 | _checked(address, 6, "JNZ address")


def jpin(pin: int, value: int, address: int) -> int:
    """Encode JPIN pin,value,addr6."""
    return (
        0xB000
        | (_checked(pin, 3, "JPIN pin") << 9)
        | (_checked(value, 1, "JPIN value") << 8)
        | _checked(address, 6, "JPIN address")
    )


def outa() -> int:
    """Encode OUTA."""
    return 0xC000


def halt() -> int:
    """Encode HALT."""
    return 0xF000


def uart_tx8n1(byte: int, *, tx_mask: int = 0x01, bit_ticks: int = 4) -> list[int]:
    """Build unrolled firmware that transmits one UART 8N1 byte.

    The selected byte is compiled into OUT immediates. The line idles high for
    one bit period before the start bit and remains high after HALT.
    """
    byte = _checked(byte, 8, "UART byte")
    tx_mask = _checked(tx_mask, 8, "TX mask")
    if bit_ticks < 2:
        raise ValueError("bit_ticks must be at least 2")

    delay = bit_ticks - 2
    frame_bits = [0] + [(byte >> bit) & 1 for bit in range(8)] + [1]
    program = [oe(tx_mask), out(tx_mask), wait(delay)]
    for bit in frame_bits:
        program.extend((out(tx_mask if bit else 0), wait(delay)))
    program.append(halt())
    return program
