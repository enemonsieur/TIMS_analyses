/*
    Module: multiplier 
    Description:
        Simple pipelined multiplier for two signed FP_NBITS with FP_NBITS-1
        fraction bits inputs producing a signed FP_NBITS output with the same
        number of fraction bits.
        
        Latency of 4 clk cycles.
*/

`timescale 1ns/1ps

`include "config.sv"

module multiplier(
    input clk,
    input rst,
    input signed [`FP_NBITS-1:0] x,
    input signed [`FP_NBITS-1:0] y,
    
    output reg signed [`FP_NBITS-1:0] out
);
    reg signed [`FP_NBITS-1:0] x_z = 0, y_z = 0; 
    reg signed [2*`FP_NBITS-1:0] xy_scaled = 0, xy_scaled_z = 0;
    
    always @(posedge clk) begin
        if (rst) begin
            x_z <= 0; y_z <= 0; xy_scaled <= 0; xy_scaled_z <= 0;
            out <= 0;
        end 
        else begin
            // load multiplier input registers
            x_z <= x;
            y_z <= y;

            // multiply
            xy_scaled <= x_z * y_z;

            // pull result multiplier output register
            xy_scaled_z <= xy_scaled;

            // scale down the result
            out <= xy_scaled_z >>> (`FP_NBITS-1);
        end
    end
endmodule

