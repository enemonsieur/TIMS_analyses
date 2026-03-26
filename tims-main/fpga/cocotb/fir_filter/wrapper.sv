`timescale 1ns/1ps
`include "config.sv"

module wrapper(clk, rst, sample_ready, sample, out, output_ready);
    input clk;
    input rst;
    input sample_ready;
    input signed [`FP_NBITS-1:0] sample;

    output signed [`FP_NBITS-1:0] out;
    output output_ready;

    cross_correlation #(
    .N(16),
    .filter_filepath("filter.mem"),
    .FP_FRACTION_BITS(`FP_NBITS-1),
    .SCALING_NBITS(0)
    ) cc_inst(
        .clk(clk), .rst(rst),
        .sample_ready(sample_ready),
        .sample(sample),
        .out(out),
        .output_ready(output_ready));
endmodule
