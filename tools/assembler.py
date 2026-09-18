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


def alu_ror(amount: int) -> int:
    """Encode ALU rotate-right by a three-bit immediate."""
    return 0x7700 | _checked(amount, 3, "ALU ROR operand")


def alu_rol(amount: int) -> int:
    """Encode ALU rotate-left by a three-bit immediate."""
    return 0x7800 | _checked(amount, 3, "ALU ROL operand")


def alu_not() -> int:
    """Encode ALU NOT."""
    return 0x7900


def alu_neg() -> int:
    """Encode ALU NEG (eight-bit two's complement)."""
    return 0x7A00


def alu_asr(amount: int) -> int:
    """Encode ALU arithmetic shift-right by a three-bit immediate."""
    return 0x7B00 | _checked(amount, 3, "ALU ASR operand")


def alu_rev() -> int:
    """Encode ALU REV (reverse accumulator bit order)."""
    return 0x7C00


def alu_swap() -> int:
    """Encode ALU SWAP (exchange accumulator nibbles)."""
    return 0x7D00


def alu_popcnt() -> int:
    """Encode ALU POPCNT (count set accumulator bits)."""
    return 0x7E00


def alu_parity() -> int:
    """Encode ALU PARITY (reduce accumulator bits with XOR)."""
    return 0x7F00


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


def outbit(pin: int, source_bit: int = 0) -> int:
    """Encode OUTBIT pin,source_bit (copy one accumulator bit to an output)."""
    return (
        0xD000
        | (_checked(source_bit, 3, "OUTBIT source bit") << 3)
        | _checked(pin, 3, "OUTBIT pin")
    )


def oea() -> int:
    """Encode OEA (copy accumulator to output-enable register)."""
    return 0xE000


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


def uart_tx8n1_from_pins(
    *,
    tx_mask: int = 0x01,
    bit_ticks: int = 4,
    background_output: int = 0,
    background_oe: int = 0,
    data_and: int = 0xFF,
    data_or: int = 0,
    data_xor: int = 0,
    data_add: int = 0,
) -> list[int]:
    """Build firmware that transmits a runtime byte sampled from protocol pins.

    The byte is sampled before the selected TX pin becomes an output. Data is sent
    least-significant-bit first with exact ``bit_ticks`` periods, and the line
    remains high after HALT. ``data_and`` and ``data_xor`` optionally transform
    the sampled byte before transmission. Non-TX output values come from
    ``background_output`` throughout the frame, and ``background_oe`` keeps
    selected non-TX pins driven.
    """
    tx_mask = _checked(tx_mask, 8, "TX mask")
    background_output = _checked(background_output, 8, "UART background output")
    background_oe = _checked(background_oe, 8, "UART background output enable")
    data_and = _checked(data_and, 8, "UART data AND mask")
    data_or = _checked(data_or, 8, "UART data OR mask")
    data_xor = _checked(data_xor, 8, "UART data XOR mask")
    data_add = _checked(data_add, 8, "UART data addend")
    if tx_mask == 0 or tx_mask & (tx_mask - 1):
        raise ValueError("runtime UART TX mask must select exactly one pin")
    if bit_ticks < 2:
        raise ValueError("bit_ticks must be at least 2 for runtime UART")

    tx_pin = tx_mask.bit_length() - 1
    idle_output = background_output | tx_mask
    start_output = background_output & ~tx_mask
    program = [inp()]
    if data_and != 0xFF:
        program.append(alu_and(data_and))
    if data_or:
        program.append(alu_or(data_or))
    if data_xor:
        program.append(alu_xor(data_xor))
    if data_add:
        program.append(alu_add(data_add))
    program.extend((oe(tx_mask | background_oe), out(idle_output), wait(bit_ticks - 2)))

    # OUTx and SHRx provide two ticks per runtime-generated bit. Longer periods
    # insert a WAIT between them. A zero-distance shift gives the start bit the
    # same timing as the data bits.
    data_delay = bit_ticks - 3
    program.append(out(start_output))
    if bit_ticks > 2:
        program.append(wait(data_delay))
    program.append(alu_shr(0))

    data_output = outbit(tx_pin)
    for _ in range(8):
        program.append(data_output)
        if bit_ticks > 2:
            program.append(wait(data_delay))
        program.append(alu_shr(1))
    program.extend((out(idle_output), halt()))
    return program


def uart_tx8n1_from_host(
    *,
    tx_mask: int = 0x01,
    bit_ticks: int = 4,
    background_output: int = 0,
    background_oe: int = 0,
    data_and: int = 0xFF,
    data_or: int = 0,
    data_xor: int = 0,
    data_add: int = 0,
) -> list[int]:
    """Build firmware that transmits an optionally transformed runtime host byte."""
    program = uart_tx8n1_from_pins(
        tx_mask=tx_mask,
        bit_ticks=bit_ticks,
        background_output=background_output,
        background_oe=background_oe,
        data_and=data_and,
        data_or=data_or,
        data_xor=data_xor,
        data_add=data_add,
    )
    program[0] = host()
    # Start with a NOP so run can be pulsed before all eight ui_in bits carry data.
    program.insert(0, 0x0000)
    return program
