/*
    Module: coil_controller
    Description: 
        Closed-loop controller for coil current. 
        The enable input controls the magnitude setpoint filter and the PI controller,
        while the rst input resets everything.
*/

`timescale 1ns/1ps

`include "config.sv"

module coil_controller(
    input clk,
    input rst,
    input enable,

    input input_ready,
    input signed [`FP_NBITS-1:0] setpoint_mag,
    input signed [`FP_NBITS-1:0] setpoint_phase,
    input signed [`FP_NBITS-1:0] sample,
    input signed [`FP_NBITS-1:0] ref_sin,
    input signed [`FP_NBITS-1:0] ref_cos,
    
    input signed [`FP_NBITS-1:0] p_factor,
    input signed [`FP_NBITS-1:0] i_factor,
    
    output signed [`FP_NBITS-1:0] pwm_duty,
    output signed [`FP_NBITS-1:0] pwm_phase,
    output pwm_ready,
    output driver_needed,

    output signed [`FP_NBITS-1:0] mag,
    output signed [`FP_NBITS-1:0] phase,
    output mag_phase_ready
);
    // Setpoint filter to smooth sharp transitions in amplitude setpoint
    // signal and prevent oscillation in H-Bridge LC filter
    wire signed [`FP_NBITS-1:0] setpoint_mag_filtered;
    amplitude_setpoint_filter sp_filter_inst(
        .clk(clk), 
        .rst(rst || !enable), 
        .setpoint(setpoint_mag), 
        .setpoint_filtered(setpoint_mag_filtered));

    assign driver_needed = (setpoint_mag_filtered > 0);

    // Convert setpoint instantaneous magnitude and phase to cartesian coordinates
    wire signed [`FP_NBITS-1:0] setpoint_x, setpoint_y;
    wire setpoint_xy_ready;
    polar_to_cartesian setpoint_ptc_inst(
        .clk(clk), .rst(rst),
        .input_ready(input_ready),
        .mag(setpoint_mag_filtered), .phase(setpoint_phase),
        .x(setpoint_x), .y(setpoint_y),
        .output_ready(setpoint_xy_ready)
    );

    // Convert current sensor sample from time domain to instantaneous cartesian and polar coordinates
    wire signed [`FP_NBITS-1:0] feedback_x, feedback_y;
    wire feedback_xy_ready;
    magnitude_phase_estimator feedback_mpe_inst(
      .clk(clk), .rst(rst),
        .sample_ready(input_ready), .sample(sample),
        .ref_sin(ref_sin), .ref_cos(ref_cos),
        .x(feedback_x), .y(feedback_y), .xy_ready(feedback_xy_ready),
        .mag(mag), .phase(phase), .mag_phase_ready(mag_phase_ready)    
    );

    // Calculate error signal in cartesian coordinates
    // error = (setpoint - feedback)/2; divided by 2 to avoid overflow
    reg signed [`FP_NBITS-1:0] error_x, error_y;
    reg error_xy_ready = 0;
    always @(posedge clk) begin
        error_x <= (setpoint_x>>>1) - (feedback_x>>>1);
        error_y <= (setpoint_y>>>1) - (feedback_y>>>1);
        error_xy_ready <= feedback_xy_ready; // ready one cycle after feedback is ready
    end

    // Convert error signal from cartesian to polar coordinates
    // wire signed [`FP_NBITS-1:0] error_mag, error_phase;
    // wire error_mag_phase_ready;
    // cartesian_to_polar error_ctp_inst(
    //     .clk(clk), .rst(rst),
    //     .input_ready(error_xy_ready),
    //     .x(error_x), .y(error_y),
    //     .mag(error_mag), .phase(error_phase),
    //     .output_ready(error_mag_phase_ready)
    //
    // );
    // // Control the output PWM duty cycle using a PI controllers
    // pi_controller pi_controller_inst(
    //     .clk(clk), .rst(rst || !enable),
    //     .input_ready(error_mag_phase_ready),
    //     .error(error_mag),
    //     .p_factor(p_factor), .i_factor(i_factor),
    //     .out(pwm_duty),
    //     .output_ready(pwm_ready)
    //     );
    // assign pwm_phase = error_phase;

    // Control the output PWM in cartesian coordinates using a PI controllers
    wire signed [`FP_NBITS-1:0] pwm_x, pwm_y;
    wire pwm_x_ready, pwm_y_ready;
    pi_controller pi_controller_x_inst(
        .clk(clk), .rst(rst || !enable || !driver_needed),
        .input_ready(error_xy_ready),
        .error(error_x),
        .p_factor(p_factor), .i_factor(i_factor),
        .out(pwm_x),
        .output_ready(pwm_x_ready)
        );
    pi_controller pi_controller_y_inst(
        .clk(clk), .rst(rst || !enable || !driver_needed),
        .input_ready(error_xy_ready),
        .error(error_y),
        .p_factor(p_factor), .i_factor(i_factor),
        .out(pwm_y),
        .output_ready(pwm_y_ready)
        );

    // Convert PWM signal from cartesian to polar coordinates
    cartesian_to_polar error_ctp_inst(
        .clk(clk), .rst(rst),
        .input_ready(pwm_x_ready),
        .x(pwm_x), .y(pwm_y),
        .mag(pwm_duty), .phase(pwm_phase),
        .output_ready(pwm_ready)
    );

endmodule

