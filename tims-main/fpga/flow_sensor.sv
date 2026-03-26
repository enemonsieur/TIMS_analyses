/*
    Module: flow_sensor
    Description:
        Measures half-period of the input flow rate sensor signal as a correlate of flow rate
        Output is measured in as the number of ticks of a clock with frequency of
            FPGA_FCLK / FLOW_SENSOR_CLK_DIVIDER

    Inputs:
        - clk: The main clock signal.
        - signal: Flow sensor signal.

    Outputs:
        - out: Half-period of the input signal measurent in FPGA_FCLK ticks

    Notes:
        - if the input signal has a half-period slower than FLOW_SENSOR_MAX_HALF_PERIOD 
        it is assumed that flow rate is zero. Output is then zero.
*/

`timescale 1ns/1ps

`include "config.sv"

module flow_sensor (
    input clk,

    input signal,

    output [`FP_NBITS-1:0] out
);
    localparam CLK_DIVIDIER_NBITS = $clog2(`FLOW_SENSOR_CLK_DIVIDER);
    reg[CLK_DIVIDIER_NBITS-1:0] clk_div_counter = 0;
    always @(posedge clk) begin
        clk_div_counter <= clk_div_counter + 1;
    end

    wire clk_slow;
    assign clk_slow = clk_div_counter[CLK_DIVIDIER_NBITS-1];

    reg [`FP_NBITS-1:0] counter = 0;
    reg [`FP_NBITS-1:0] out_reg = 0;

    reg signal_slow = 0, clk_slow_prev = 0, signal_slow_prev = 0;
    always @(posedge clk) begin
        if (clk_slow && !clk_slow_prev) begin
            signal_slow <= signal;

            if (signal_slow && !signal_slow_prev) begin
                counter <= 0;
            end
            else if (!signal_slow && signal_slow_prev) begin
                out_reg <= counter;
                counter <= 0;
            end
            else begin
                if (counter > `FLOW_SENSOR_MAX_HALF_PERIOD) begin
                    out_reg <= 0;
                    counter <= 0;
                end
                else begin
                    counter <= counter + 1;
                end
            end

            signal_slow_prev <= signal_slow;
        end

        clk_slow_prev <= clk_slow;
    end

    assign out = out_reg;
endmodule
