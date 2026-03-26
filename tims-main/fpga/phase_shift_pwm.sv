/*
    Module: phase_shift_pwm
    Description:
    This module generates a phase-shifted PWM signal based on a reference phase signal. 
    The characteristics are as follows:

    - Phase is represented as a signed number that ranges from -1 to 1 (mapping from -pi to pi)
    - `phase_offset` is the phase shift applied to the phase-shifted PWM signal.
    - The output signal S1 and S2 are phase-shifted versions of the reference phase signal.
    - The difference between the signals (S = S1 - S2) has a duty cycle determined by the input `duty_cycle`.
    - `duty_cycle` is a signed non-negative fixed-point number in the range 0 to 1 (2^(FP_NBITS-1)-1 maps to 1.0)
    - The duty cycle is defined as the ratio of the duration of the non-zero signal to the total period.
    - Output has a latency of 2 clk cycles relative to ref_phase
    - Output S=S1-S2 is in-phase with sin(phase_ref + phase_offset)

    Inputs:
    - clk: The main clock signal.
    - rst: Active-high reset signal.
    - ref_phase: The reference phase signal used for generating the PWM.
    - duty_cycle: The desired duty cycle of the PWM signal, in the range 0 to 1.
    - phase_offset: The phase offset to shift the PWM signal relative to the reference phase.

    Outputs:
    - S1: The first (positive) phase-shifted PWM signal.
    - S2: The second (negative) phase-shifted PWM signal.
*/

`timescale 1ns/1ps

`include "config.sv"

module phase_shift_pwm (
    input clk,
    input rst,
    input signed [`FP_NBITS-1:0] ref_phase,
    input signed [`FP_NBITS-1:0] duty_cycle,
    input signed [`FP_NBITS-1:0] phase_offset,

    output reg S1,
    output reg S2
);
    reg signed [`FP_NBITS-1:0] phase_1 = 0;
    reg signed [`FP_NBITS-1:0] phase_2 = 0;
    reg signed [`FP_NBITS-1:0] phase_shift = 0;

    always @(posedge clk) begin
        if (rst) begin
            S1 <= 0;
            S2 <= 0;
        end else begin
            phase_shift <= (duty_cycle >>> 1);

            phase_1 <= ref_phase + phase_offset + phase_shift;
            phase_2 <= ref_phase + phase_offset - phase_shift;

            S1 <= (phase_1 >= `FP_MAX/2) || (phase_1 < `FP_MIN/2);
            S2 <= (phase_2 >= `FP_MAX/2) || (phase_2 < `FP_MIN/2);
        end
    end
endmodule
