/*
 * Copyright (c) 2026 Derek Su
 * SPDX-License-Identifier: Apache-2.0
 */

`default_nettype none

module tt_um_derek_su_protocol_emulator (
    input  wire [7:0] ui_in,
    output wire [7:0] uo_out,
    input  wire [7:0] uio_in,
    output wire [7:0] uio_out,
    output wire [7:0] uio_oe,
    input  wire       ena,
    input  wire       clk,
    input  wire       rst_n
);

  localparam [3:0] OP_OUT  = 4'h1;
  localparam [3:0] OP_HALT = 4'hf;

  reg [15:0] program [0:63];
  reg [15:0] cfg_shift_reg;
  reg [5:0]  cfg_addr;
  reg [5:0]  pc;
  reg [7:0]  pin_out;
  reg [7:0]  pin_oe;
  reg        halted;

  wire cfg_data   = ui_in[0];
  wire cfg_shift  = ui_in[1];
  wire cfg_commit = ui_in[2];
  wire run        = ui_in[3];

  assign uio_out = pin_out;
  assign uio_oe  = pin_oe;
  assign uo_out  = {halted, 1'b0, pc};

  always @(posedge clk) begin
    if (!rst_n) begin
      cfg_shift_reg <= 16'b0;
      cfg_addr       <= 6'b0;
      pc             <= 6'b0;
      pin_out        <= 8'b0;
      pin_oe         <= 8'b0;
      halted         <= 1'b0;
    end else if (!run) begin
      pc     <= 6'b0;
      halted <= 1'b0;

      if (cfg_shift)
        cfg_shift_reg <= {cfg_data, cfg_shift_reg[15:1]};

      if (cfg_commit) begin
        program[cfg_addr] <= cfg_shift_reg;
        cfg_addr <= cfg_addr + 1'b1;
      end
    end else if (ena && !halted) begin
      case (program[pc][15:12])
        OP_OUT: begin
          pin_out <= program[pc][7:0];
          pc <= pc + 1'b1;
        end
        OP_HALT: begin
          halted <= 1'b1;
        end
        default: begin
          pc <= pc + 1'b1;
        end
      endcase
    end
  end

  wire _unused = &{uio_in, ui_in[7:4], 1'b0};

endmodule
