/*
    Module: mux_3bit 
    Description: 3-bit multiplexer
*/

`timescale 1ns/1ps

`include "config.sv"

module mux_3bit(
    input clk,
    input rst,
    input [2:0] control,
    input signed [`FP_NBITS-1:0] in0,
    input signed [`FP_NBITS-1:0] in1,
    input signed [`FP_NBITS-1:0] in2,
    input signed [`FP_NBITS-1:0] in3,
    input signed [`FP_NBITS-1:0] in4,
    input signed [`FP_NBITS-1:0] in5,
    input signed [`FP_NBITS-1:0] in6,
    input signed [`FP_NBITS-1:0] in7,
    
    output reg signed [`FP_NBITS-1:0] out
);
    always @(posedge clk) begin
        if (rst) begin
            out <= 0;
        end 
        else begin
            case(control)
                0: out <= in0;
                1: out <= in1;
                2: out <= in2;
                3: out <= in3;
                4: out <= in4;
                5: out <= in5;
                6: out <= in6;
                7: out <= in7;
            endcase
        end
    end
endmodule
