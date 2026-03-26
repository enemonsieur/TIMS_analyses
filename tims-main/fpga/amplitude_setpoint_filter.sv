/*
    Module: amplitude_setpoint_filter
    Description:
        Simple low pass filter to be applied to the coil current amplitude setpoint before it
        is passed to the current control algorithm. The purpose of the filter is to 
        smooth sharp changes in amplitude setpoint and so prevent oscillations in the 
        LC filter of the coil driver circuit.

        The filter operates at the same sampling rate of the FPGA interface (remote or SPI).
*/

`timescale 1ns/1ps

`include "config.sv"

module amplitude_setpoint_filter (
    input clk,
    input rst,
    input signed [`FP_NBITS-1:0] setpoint,
    output signed [`FP_NBITS-1:0] setpoint_filtered
);
    // generate a clock with the sampling rate of the filter (sampe as the
    // fpga interface sampling rate)
    localparam SAMPLING_COUNTER_NBITS = $rtoi($ceil($clog2(`FPGA_FCLK / `INTERFACE_SAMPLING_RATE)));
    localparam bit [SAMPLING_COUNTER_NBITS-1:0] SAMPLING_PERIOD =
        SAMPLING_COUNTER_NBITS'(`FPGA_FCLK / `INTERFACE_SAMPLING_RATE);
    reg [SAMPLING_COUNTER_NBITS-1:0] sampling_counter = 0;
    reg sampling_clk = 0, sampling_clk_z = 0;
    always @(posedge clk) begin
        sampling_counter <= (sampling_counter == SAMPLING_PERIOD-1)? 0 : sampling_counter + 1;
        sampling_clk <= (sampling_counter > SAMPLING_PERIOD/2);
        sampling_clk_z <= sampling_clk;
    end

    // generate a single pulse every time a new sample can be take by the
    // filter
    wire sample_ready;
    assign sample_ready = sampling_clk && !sampling_clk_z;

    cross_correlation #(
    .N(`AMP_SETPOINT_FILTER_NTAPS),
    .filter_filepath("memfiles/amp_setpoint_filter.mem"),
    .FP_FRACTION_BITS(`FP_NBITS-1),
    .SCALING_NBITS(0)
    ) filter_cc_inst(
        .clk(clk), .rst(rst),
        .sample_ready(sample_ready),
        .sample(setpoint),
        .out(setpoint_filtered),
        .output_ready());
endmodule
