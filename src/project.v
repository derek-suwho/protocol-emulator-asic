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
  localparam [3:0] OP_OE   = 4'h2;
  localparam [3:0] OP_WAIT = 4'h3;
  localparam [3:0] OP_IN   = 4'h4;
  localparam [3:0] OP_LDI  = 4'h5;
  localparam [3:0] OP_HOST = 4'h6;
  localparam [3:0] OP_ALU  = 4'h7;
  localparam [3:0] OP_JMP  = 4'h8;
  localparam [3:0] OP_JZ   = 4'h9;
  localparam [3:0] OP_JNZ  = 4'ha;
  localparam [3:0] OP_JPIN = 4'hb;
  localparam [3:0] OP_OUTA = 4'hc;
  localparam [3:0] OP_OUTBIT = 4'hd;
  localparam [3:0] OP_HALT = 4'hf;

  localparam [3:0] ALU_AND = 4'h0;
  localparam [3:0] ALU_OR  = 4'h1;
  localparam [3:0] ALU_XOR = 4'h2;
  localparam [3:0] ALU_ADD = 4'h3;
  localparam [3:0] ALU_SHL = 4'h4;
  localparam [3:0] ALU_SHR = 4'h5;
  localparam [3:0] ALU_SUB = 4'h6;
  localparam [3:0] ALU_ROR = 4'h7;
  localparam [3:0] ALU_ROL = 4'h8;
  localparam [3:0] ALU_NOT = 4'h9;
  localparam [3:0] ALU_NEG = 4'ha;
  localparam [3:0] ALU_ASR = 4'hb;
  localparam [3:0] ALU_REV = 4'hc;
  localparam [3:0] ALU_SWAP = 4'hd;
  localparam [3:0] ALU_POPCNT = 4'he;
  localparam [3:0] ALU_PARITY = 4'hf;

  reg [15:0] imem [0:63];
  reg [15:0] cfg_shift_reg;
  reg [5:0]  cfg_addr;
  reg [5:0]  pc;
  reg [11:0] wait_count;
  reg [7:0]  pin_out;
  reg [7:0]  pin_oe;
  reg [7:0]  accumulator;
  reg        halted;
  reg        running;

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
      wait_count     <= 12'b0;
      pin_out        <= 8'b0;
      pin_oe         <= 8'b0;
      accumulator    <= 8'b0;
      halted         <= 1'b0;
      running        <= 1'b0;
    end else if (!run && !running) begin
      pc     <= 6'b0;
      wait_count <= 12'b0;
      halted <= 1'b0;

      if (cfg_shift)
        cfg_shift_reg <= {cfg_data, cfg_shift_reg[15:1]};

      if (cfg_commit) begin
        imem[cfg_addr] <= cfg_shift_reg;
        cfg_addr <= cfg_addr + 1'b1;
      end
    end else if (ena && !halted && (wait_count != 0)) begin
      running <= 1'b1;
      wait_count <= wait_count - 1'b1;
    end else if (ena && !halted) begin
      running <= 1'b1;
      case (imem[pc][15:12])
        OP_OUT: begin
          pin_out <= imem[pc][7:0];
          pc <= pc + 1'b1;
        end
        OP_OE: begin
          pin_oe <= imem[pc][7:0];
          pc <= pc + 1'b1;
        end
        OP_WAIT: begin
          wait_count <= imem[pc][11:0];
          pc <= pc + 1'b1;
        end
        OP_IN: begin
          accumulator <= uio_in;
          pc <= pc + 1'b1;
        end
        OP_LDI: begin
          accumulator <= imem[pc][7:0];
          pc <= pc + 1'b1;
        end
        OP_HOST: begin
          accumulator <= ui_in;
          pc <= pc + 1'b1;
        end
        OP_ALU: begin
          if (imem[pc][11:8] == ALU_AND)
            accumulator <= accumulator & imem[pc][7:0];
          else if (imem[pc][11:8] == ALU_OR)
            accumulator <= accumulator | imem[pc][7:0];
          else if (imem[pc][11:8] == ALU_XOR)
            accumulator <= accumulator ^ imem[pc][7:0];
          else if (imem[pc][11:8] == ALU_ADD)
            accumulator <= accumulator + imem[pc][7:0];
          else if (imem[pc][11:8] == ALU_SHL)
            accumulator <= accumulator << imem[pc][2:0];
          else if (imem[pc][11:8] == ALU_SHR)
            accumulator <= accumulator >> imem[pc][2:0];
          else if (imem[pc][11:8] == ALU_SUB)
            accumulator <= accumulator - imem[pc][7:0];
          else if (imem[pc][11:8] == ALU_ROR)
            accumulator <= ({accumulator, accumulator} >> imem[pc][2:0]);
          else if (imem[pc][11:8] == ALU_ROL)
            accumulator <= ({accumulator, accumulator} << imem[pc][2:0]) >> 8;
          else if (imem[pc][11:8] == ALU_NOT)
            accumulator <= ~accumulator;
          else if (imem[pc][11:8] == ALU_NEG)
            accumulator <= -accumulator;
          else if (imem[pc][11:8] == ALU_ASR)
            accumulator <= $signed(accumulator) >>> imem[pc][2:0];
          else if (imem[pc][11:8] == ALU_REV)
            accumulator <= {accumulator[0], accumulator[1], accumulator[2], accumulator[3],
                            accumulator[4], accumulator[5], accumulator[6], accumulator[7]};
          else if (imem[pc][11:8] == ALU_SWAP)
            accumulator <= {accumulator[3:0], accumulator[7:4]};
          else if (imem[pc][11:8] == ALU_POPCNT)
            accumulator <= {3'b0, accumulator[0]} + {3'b0, accumulator[1]} +
                           {3'b0, accumulator[2]} + {3'b0, accumulator[3]} +
                           {3'b0, accumulator[4]} + {3'b0, accumulator[5]} +
                           {3'b0, accumulator[6]} + {3'b0, accumulator[7]};
          else if (imem[pc][11:8] == ALU_PARITY)
            accumulator <= {7'b0, ^accumulator};
          pc <= pc + 1'b1;
        end
        OP_JMP: begin
          pc <= imem[pc][5:0];
        end
        OP_JZ: begin
          if (accumulator == 0)
            pc <= imem[pc][5:0];
          else
            pc <= pc + 1'b1;
        end
        OP_JNZ: begin
          if (accumulator != 0)
            pc <= imem[pc][5:0];
          else
            pc <= pc + 1'b1;
        end
        OP_JPIN: begin
          if (uio_in[imem[pc][11:9]] == imem[pc][8])
            pc <= imem[pc][5:0];
          else
            pc <= pc + 1'b1;
        end
        OP_OUTA: begin
          pin_out <= accumulator;
          pc <= pc + 1'b1;
        end
        OP_OUTBIT: begin
          pin_out[imem[pc][2:0]] <= accumulator[imem[pc][5:3]];
          pc <= pc + 1'b1;
        end
        OP_HALT: begin
          halted <= 1'b1;
        end
        default: begin
          pc <= pc + 1'b1;
        end
      endcase
    end else if (halted && !run) begin
      pc <= 6'b0;
      wait_count <= 12'b0;
      halted <= 1'b0;
      running <= 1'b0;
    end
  end

  wire _unused = &{ui_in[7:4], 1'b0};

endmodule
