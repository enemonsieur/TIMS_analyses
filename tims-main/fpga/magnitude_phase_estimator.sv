/*
    Module: magnitude_phase_estimator
    Description:
    This module estimates the magnitude and phase of an input signal. Correlations with a sine and cosine reference
    signals are calculated to produce a 2D vector that indicates the instantaneous magnitude and the relative phase of the input signal.
    CORDIC is used to calculate the magnitude and phase of that vector.
    
    Inputs:
    - clk: The main clock signal.
    - rst: Active-high reset signal.
    - sample_ready: Pulse indicating a new sample is available.
    - sample: Signed fixed-point representation of the input signal sample.
    - ref_sin: References sine signal. Phase is calculated relative to that signal
    - ref_sin: References cosine
    
    Outputs:
    - x: x-coordinate of the input singal
    - y: y-coordinate of the input signale
    - mag: Computed magnitude of the input signal.
    - phase: Computed phase angle of the input signal, mapped from 0 to 2*pi.
    - output_ready: Single-cycle pulse that indicates when output data is available.
*/

`timescale 1ns/1ps

`include "config.sv"

`define SPC_NBITS $clog2(`SAMPLES_PER_CARRIER_PERIOD)

module magnitude_phase_estimator (
    input clk,
    input rst,
    input sample_ready,
    input signed [`FP_NBITS-1:0] sample,
    input signed [`FP_NBITS-1:0] ref_sin,
    input signed [`FP_NBITS-1:0] ref_cos,

    output signed [`FP_NBITS-1:0] x,
    output signed [`FP_NBITS-1:0] y,
    output xy_ready,

    output signed [`FP_NBITS-1:0] mag,
    output signed [`FP_NBITS-1:0] phase,
    output mag_phase_ready
); 
    localparam N = `SAMPLES_PER_CARRIER_PERIOD;

    wire signed [`FP_NBITS-1:0] x_raw, y_raw;
    wire xy_raw_ready;

    // cross correlation with a sine wave
    generate
        if (`MAG_PHASE_SPARSE == 1) begin : sprase_vs_dense_block
            cross_correlation_two_signals_sparse #(
            .N(N),
            .FP_FRACTION_BITS(`FP_NBITS-1),
            .SCALING_NBITS($clog2(N)-1)
            ) cc_sin_inst(
                .clk(clk), .rst(rst),
                .sample_ready(sample_ready),
                .sample1(sample),
                .sample2(ref_sin),
                .out(x_raw),
                .output_ready(xy_raw_ready)); 

            // cross correlation with a cosine wave
            cross_correlation_two_signals_sparse #(
            .N(N),
            .FP_FRACTION_BITS(`FP_NBITS-1),
            .SCALING_NBITS($clog2(N)-1)
            ) cc_cos_inst(
                .clk(clk), .rst(rst),
                .sample_ready(sample_ready),
                .sample1(sample),
                .sample2(ref_cos),
                .out(y_raw),
                .output_ready()); 
        end
        else begin : sprase_vs_dense_block
            cross_correlation_two_signals #(
            .N(N),
            .FP_FRACTION_BITS(`FP_NBITS-1),
            .SCALING_NBITS($clog2(N)-1)
            ) cc_sin_inst(
                .clk(clk), .rst(rst),
                .sample_ready(sample_ready),
                .sample1(sample),
                .sample2(ref_sin),
                .out(x_raw),
                .output_ready(xy_raw_ready)); 

            // cross correlation with a cosine wave
            cross_correlation_two_signals #(
            .N(N),
            .FP_FRACTION_BITS(`FP_NBITS-1),
            .SCALING_NBITS($clog2(N)-1)
            ) cc_cos_inst(
                .clk(clk), .rst(rst),
                .sample_ready(sample_ready),
                .sample1(sample),
                .sample2(ref_cos),
                .out(y_raw),
                .output_ready()); 
        end
    endgenerate

    generate
        if (`FB_LOWPASS_FILTER_TYPE != 0) begin : fb_lowpass_filter_block
            cross_correlation #(
            .N(`FB_LOWPASS_FILTER_NTAPS),
            .filter_filepath("memfiles/fb_lowpass_filter.mem"),
            .FP_FRACTION_BITS(`FP_NBITS-1),
            .SCALING_NBITS(0)
            ) fp_lowpass_filter_cc_x_inst(
                .clk(clk), .rst(rst),
                .sample_ready(xy_raw_ready),
                .sample(x_raw),
                .out(x),
                .output_ready(xy_ready));

            cross_correlation #(
            .N(`FB_LOWPASS_FILTER_NTAPS),
            .filter_filepath("memfiles/fb_lowpass_filter.mem"),
            .FP_FRACTION_BITS(`FP_NBITS-1),
            .SCALING_NBITS(0)
            ) fp_lowpass_filter_cc_y_inst(
                .clk(clk), .rst(rst),
                .sample_ready(xy_raw_ready),
                .sample(y_raw),
                .out(y),
                .output_ready());
        end
        else begin : fb_lowpass_filter_block
            assign x = x_raw;
            assign y = y_raw;
            assign xy_ready = xy_raw_ready;
        end
    endgenerate

    // Convert to polar to calculate the magnitude and phase
    cartesian_to_polar ctp_inst(
        .clk(clk), .rst(rst),
        .input_ready(xy_ready),
        .output_ready(mag_phase_ready),
        .x(x), .y(y),
        .mag(mag), .phase(phase));

endmodule
