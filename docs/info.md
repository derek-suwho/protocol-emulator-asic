## How it works

The Programmable Protocol Emulator is a small deterministic processor optimized
for cycle-accurate digital pin control. A host loads compact instructions through
a synchronous serial configuration interface, then asserts `run`. The processor
executes instructions that drive, sample, wait on, and change the direction of
eight bidirectional protocol pins. Protocol behavior is firmware rather than
fixed RTL, allowing the same silicon to implement UART, SPI, I2C, and other
timing-compatible interfaces.

## How to test

Hold `run` low and reset the design. Shift the program into instruction memory
with `cfg_data` and `cfg_shift`; pulse `cfg_commit` after each complete instruction.
Assert `run` to begin execution. Observe `protocol_io_0` through
`protocol_io_7` and the status output while applying any required protocol input
stimulus. Exact instruction encoding and reference UART, SPI, and I2C programs
will be documented as the implementation stabilizes.

## External hardware

No external hardware is required for simulation. FPGA and fabricated-silicon
testing will use level-compatible loopback wiring and a logic analyzer.
