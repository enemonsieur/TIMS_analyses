/*
    Module: full_bridge_driver
    Description:
    A driver for an H-Bridge circuit based on phase shift PWM with deadtime
*/

`timescale 1ns/1ps

`include "config.sv"

module full_bridge_driver (
    input clk,
    input rst,
    input signed [`FP_NBITS-1:0] ref_phase,
    input signed [`FP_NBITS-1:0] duty_cycle,
    input signed [`FP_NBITS-1:0] phase_offset,

    output reg A,
    output reg B,
    output reg C,
    output reg D
);
    parameter DEADTIME_NTICKS = `PWM_DEADTIME_NTICKS;
    
    wire S1, S2;
    phase_shift_pwm pwm_inst(
        .clk(clk),
        .rst(rst),
        .ref_phase(ref_phase),
        .duty_cycle(duty_cycle),
        .phase_offset(phase_offset),
        .S1(S1),
        .S2(S2)
    );

    deadtime #(.DEADTIME_NTICKS(DEADTIME_NTICKS)) deadtime_inst1 (
        .clk(clk),
        .rst(rst),
        .SIG(S1),
        .H(A),
        .L(B)
    );

    deadtime #(.DEADTIME_NTICKS(DEADTIME_NTICKS)) deadtime_inst2 (
        .clk(clk),
        .rst(rst),
        .SIG(S2),
        .H(C),
        .L(D)
    );

  endmodule
