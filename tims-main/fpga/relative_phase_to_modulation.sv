/*
    Module: relataive_phase_to_modulation
    Description:
    This module converts the relative phase between coil currents into the corresponding
    modulation in the target region in TI stimulation. The modulation output is scaled
    by the average coil currents
        modulation = (mag1 + mag2)/2 * cos((phase1 - phase2) / 2)

    Output latency = FP_NBITS + 6 clk cycles

    Inputs:
    - clk: The main clock signal.
    - rst: Active-high reset signal.
    - input_ready: Pulse to indicate new input data is available.
    - phase1: phase of coil 1 current. -pi to pi.
    - phase2: phase of coil 1 current. -pi to pi.
    - mag1: coil 1 current magnitude
    - mag2: coil 2 current magnitude
    
    Outputs:
    - modulation: modulation in the target region
    - output_ready: Single-cycle pulse that indicates when output data is ready.
*/
`timescale 1ns/1ps

`include "config.sv"

module relative_phase_to_modulation(
    input clk,
    input rst,
    input input_ready,
    input signed [`FP_NBITS-1:0] phase1,
    input signed [`FP_NBITS-1:0] phase2,
    input signed [`FP_NBITS-1:0] mag1,
    input signed [`FP_NBITS-1:0] mag2,

    output signed [`FP_NBITS-1:0] modulation
);
    reg signed [`FP_NBITS-1:0] mag_avg, relative_phase_halfed;
    reg relative_phase_ready = 0;
    always @(posedge clk) begin
        mag_avg <= (mag1>>>1) + (mag2>>>1);
        relative_phase_halfed <= (phase1>>>1) - (phase2>>>1);
        relative_phase_ready <= input_ready;
    end

    wire signed [`FP_NBITS-1:0] modulation_unscaled;
    polar_to_cartesian ptc_inst(
        .clk(clk), .rst(rst),
        .input_ready(relative_phase_ready),
        .mag(`FP_MAX), .phase(relative_phase_halfed),
        .x(modulation_unscaled), .y(),
        .output_ready()
    );

    multiplier multiplier_inst(.clk(clk), .rst(rst), .x(mag_avg), .y(modulation_unscaled), .out(modulation));
endmodule

