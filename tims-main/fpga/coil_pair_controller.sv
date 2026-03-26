/*
    Module: coil_pair_controller
    Description: 
        Collection of module to control a pair of coils in various stimulation modes
        The channel_enable input controls the magnitude setpoint filters, the PI 
        controller and the H-Bridge drivers for both coils, while the rst input resets 
        everything.
*/

`timescale 1ns/1ps

`include "config.sv"

module coil_pair_controller(
    input clk,
    input rst,
    input channel_enable,

    input signed [`FP_NBITS-1:0] amplitude1,
    input signed [`FP_NBITS-1:0] amplitude2,
    input signed [`FP_NBITS-1:0] modulation,

    input [`FP_NBITS-1:0] clk_ticks_per_sample,
    input signed [`FP_NBITS+`FP_EXTRA_BITS-1:0] phase_step,

    input sample_ready,
    input signed [`FP_NBITS-1:0] sample1,
    input signed [`FP_NBITS-1:0] sample2,
    
    input signed [`FP_NBITS-1:0] p_factor,
    input signed [`FP_NBITS-1:0] i_factor,

    output sclk,
    output pwm_ch1a,
    output pwm_ch1b,
    output pwm_ch1c,
    output pwm_ch1d,
    output driver_needed_ch1,
    
    output pwm_ch2a,
    output pwm_ch2b,
    output pwm_ch2c,
    output pwm_ch2d,
    output driver_needed_ch2,
    
    output signed [`FP_NBITS-1:0] mag1,
    output signed [`FP_NBITS-1:0] phase1,
    output signed [`FP_NBITS-1:0] mag2,
    output signed [`FP_NBITS-1:0] phase2,
    output mag_phase_ready
);
    parameter DEADTIME_NTICKS = `PWM_DEADTIME_NTICKS;
    
    wire signed [`FP_NBITS-1:0] ref_phase, ref_cos, ref_sin;
    reference_generator refgen_inst (
        .clk(clk), .rst(rst),
        .clk_ticks_per_sample(clk_ticks_per_sample),
        .phase_step(phase_step),
        .phase(ref_phase),
        .sin(ref_sin),
        .cos(ref_cos),
        .sclk(sclk));


    // Convert modulation signal to corresponding relative phase signal for phase modulation
    // in temporal interference mode
    wire signed [`FP_NBITS-1:0] relative_phase;
    wire relative_phase_ready;
    modulation_to_relative_phase mtrp_inst(
        .clk(clk), .rst(rst),
        .input_ready(sclk),
        .modulation(modulation),
        .output_ready(relative_phase_ready),
        .relative_phase(relative_phase)
    );

    reg signed [`FP_NBITS-1:0] setpoint_mag1, setpoint_phase1, setpoint_mag2, setpoint_phase2;
    reg setpoint_ready;
    always @(posedge clk) begin
        if (rst) begin
            setpoint_mag1 <= 0;
            setpoint_mag2 <= 0;
            setpoint_phase1 <= 0;
            setpoint_phase2 <= 0;
            setpoint_ready <= 0;
        end
        else begin
            setpoint_mag1 <= amplitude1;
            setpoint_mag2 <= amplitude2;
            setpoint_phase1 <= (relative_phase>>>1);
            setpoint_phase2 <= -(relative_phase>>>1);
            setpoint_ready <= relative_phase_ready;
        end
    end

    wire signed [`FP_NBITS-1:0] pwm_duty1, pwm_phase1;
    wire pwm1_ready;
    coil_controller coil1_controller_inst(
        .clk(clk), .rst(rst), .enable(channel_enable),
        .input_ready(sample_ready),
        .setpoint_mag(setpoint_mag1),
        .setpoint_phase(setpoint_phase1),
        .sample(sample1),
        .ref_sin(ref_sin), .ref_cos(ref_cos),
        .p_factor(p_factor), .i_factor(i_factor),
        .pwm_duty(pwm_duty1), .pwm_phase(pwm_phase1),
        .pwm_ready(pwm1_ready),
        .driver_needed(driver_needed_ch1),
        .mag(mag1), .phase(phase1), .mag_phase_ready(mag_phase_ready)
    );
    
    full_bridge_driver #(.DEADTIME_NTICKS(DEADTIME_NTICKS)) ch1_driver(
        .clk(clk), .rst(rst || !channel_enable),
        .ref_phase(ref_phase),
        .duty_cycle(pwm_duty1),
        .phase_offset(pwm_phase1),
        .A(pwm_ch1a), .B(pwm_ch1b),
        .C(pwm_ch1c), .D(pwm_ch1d));


    wire signed [`FP_NBITS-1:0] pwm_duty2, pwm_phase2;
    wire pwm2_ready;
    coil_controller coil2_controller_inst(
        .clk(clk), .rst(rst), .enable(channel_enable),
        .input_ready(sample_ready),
        .setpoint_mag(setpoint_mag2),
        .setpoint_phase(setpoint_phase2),
        .sample(sample2),
        .ref_sin(ref_sin), .ref_cos(ref_cos),
        .p_factor(p_factor), .i_factor(i_factor),
        .pwm_duty(pwm_duty2), .pwm_phase(pwm_phase2),
        .pwm_ready(pwm2_ready),
        .driver_needed(driver_needed_ch2),
        .mag(mag2), .phase(phase2), .mag_phase_ready()
    );
    
    full_bridge_driver #(.DEADTIME_NTICKS(DEADTIME_NTICKS)) ch2_driver(
        .clk(clk), .rst(rst || !channel_enable),
        .ref_phase(ref_phase),
        .duty_cycle(pwm_duty2),
        .phase_offset(pwm_phase2),
        .A(pwm_ch2a), .B(pwm_ch2b),
        .C(pwm_ch2c), .D(pwm_ch2d));
     
endmodule

