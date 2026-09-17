# Protocol Emulator Architecture

Status: draft v0.3 — the loader plus `OUT`, `OE`, `WAIT`, `IN`, `LDI`,
`HOST`, `ALU AND`, `ALU OR`, `ALU XOR`, `ALU ADD`, `ALU SUB`, `ALU SHL`, `ALU SHR`, `ALU ASR`, `ALU ROR`, `ALU ROL`, `ALU NOT`, `ALU NEG`, `ALU REV`, `ALU SWAP`, `JMP`, `JZ`, `JNZ`, `JPIN`, `OUTA`, and `HALT` are
implemented and tested. Firmware can sample an external or host byte, transform
it with AND-immediate, OR-immediate, XOR-immediate, wrapping ADD/SUB-immediate, logical or arithmetic shifts, rotates, bitwise inversion, two's-complement negation, bit-order reversal, or nibble swapping, and later drive the retained value
onto the protocol pins. A firmware-only UART transmitter has produced a verified
8N1 frame for byte `0x55` with exact four-clock bit periods. The assembler can
also emit UART programs that sample a byte from either the protocol pins or host
bus at runtime, then transmit it LSB-first on protocol pin 0. Pin input uses 33
words; host input uses a leading `NOP` and 34 words so `run` can be pulsed before
all eight host-input bits carry data.

## Design goals

1. Execute every non-wait instruction in one clock cycle.
2. Make pin timing deterministic and easy to verify formally.
3. Implement protocols in firmware rather than fixed protocol RTL.
4. Keep the processor small enough that instruction memory, routing, and clock
   distribution fit comfortably in the competition allocation.
5. Keep the host/programming interface usable with inexpensive FPGA or
   microcontroller hardware.

## Datapath

- 16-bit fixed-width instructions
- 6-bit program counter
- 64 x 16-bit instruction memory for the first physical-design baseline
- 8-bit accumulator
- 12-bit wait counter
- 8-bit sampled input, output, and output-enable registers
- One instruction issued per rising clock edge when not waiting or halted

Instruction-memory depth will only increase after synthesis and place-and-route
show sufficient margin. An SRAM-backed implementation will be evaluated after
the flip-flop version is functionally complete.

## External interface

The eight bidirectional `uio` pins are the emulated protocol pins. While `run`
is low, the processor is stopped at address zero and the host loads 16-bit
instructions through `cfg_data`, `cfg_shift`, and `cfg_commit`. Bits are shifted
least-significant first. Each `cfg_commit` pulse writes one word and advances
the configuration address. Raising `run` starts execution at address zero and
latches the processor in its running state, allowing all eight `ui_in` bits to
carry host data on following cycles. After `HALT`, lowering `run` returns to
configuration mode.

The dedicated output bus reports `{halted, 1'b0, pc[5:0]}` during development.
This debug mapping may be replaced with host handshaking before tapeout.

## Instruction format

All instructions are 16 bits. Bits `[15:12]` select an opcode. Unused encodings
must behave as `NOP` so malformed firmware cannot create uncontrolled pin
changes.

| Opcode | Mnemonic | Operand | Planned behavior |
|---|---|---|---|
| `0` | `NOP` | — | Advance PC without changing architectural state |
| `1` | `OUT imm8` | `[7:0]` | Set protocol output register |
| `2` | `OE imm8` | `[7:0]` | Set protocol output-enable register |
| `3` | `WAIT imm12` | `[11:0]` | Delay a precisely defined number of clocks |
| `4` | `IN` | — | Sample protocol inputs into accumulator |
| `5` | `LDI imm8` | `[7:0]` | Load accumulator immediate |
| `6` | `HOST` | — | Sample host input byte into accumulator |
| `7` | `ALU fn,imm8` | `[11:8]`, `[7:0]` | Transform accumulator; functions `0`–`3` are AND, OR, XOR, and wrapping ADD immediate, functions `4`/`5` are logical shift-left/right by `[2:0]`, function `6` is wrapping SUB immediate, functions `7`/`8` are rotate-right/left by `[2:0]`, function `9` is bitwise NOT, function `A` is eight-bit two's-complement negation, function `B` is arithmetic shift-right by `[2:0]`, function `C` reverses bit order, and function `D` swaps the upper and lower nibbles |
| `8` | `JMP addr6` | `[5:0]` | Unconditional branch |
| `9` | `JZ addr6` | `[5:0]` | Branch when accumulator is zero |
| `A` | `JNZ addr6` | `[5:0]` | Branch when accumulator is nonzero |
| `B` | `JPIN pin,value,addr6` | `[11:9]`, `[8]`, `[5:0]` | Branch when the selected live protocol pin matches `value` |
| `C` | `OUTA` | — | Copy accumulator to protocol output register |
| `D` | reserved | — | Reserved for host synchronization or timing extensions |
| `E` | reserved | — | Reserved for verification-driven extensions |
| `F` | `HALT` | — | Stop until `run` is lowered or reset is asserted |

`OUT`, `OE`, `WAIT`, and `HALT` are frozen in v0.2. `IN`, `LDI`, `ALU XOR`,
`HOST`, `ALU AND`, `ALU OR`, `ALU ADD`, `ALU SUB`, `ALU SHL`, `ALU SHR`, `ALU ASR`, `ALU ROR`, `ALU ROL`, `ALU NOT`, `ALU NEG`, `ALU REV`, `ALU SWAP`, `JMP`, `JZ`, `JNZ`, `JPIN`, and `OUTA` are implemented in draft
v0.3. Every additional operation will be added through a failing behavioral test
before RTL implementation.
Unimplemented ALU function values advance the PC without changing the
accumulator.

## Verification sequence

1. Loader bit order, commit behavior, and address progression
2. Reset safety and deterministic restart
3. `OUT`, `OE`, and `HALT`
4. Exact `WAIT` cycle semantics, including zero and maximum operands
5. Input sampling and ALU behavior
6. Branch boundaries and loop timing
7. UART transmit and receive firmware
8. SPI controller and peripheral firmware
9. I2C controller and target firmware, including open-drain behavior
10. Random instruction streams checked against a Python reference model
11. Formal properties for PC bounds, wait termination, reset safety, and
    output changes only at documented instruction boundaries
12. Gate-level regression after synthesis and place-and-route

## Scope gates

Low-speed USB, Ethernet, CAN, JTAG, and SWD remain stretch goals. None will be
started until UART, SPI, and I2C pass RTL, randomized/reference-model, and
post-layout gate-level testing within area and timing budgets.
