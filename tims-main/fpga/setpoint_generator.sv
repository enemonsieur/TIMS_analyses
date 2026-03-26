/*
    Module: setpoint_generator
    Description:
    This module generate the instantaneous magnitude and phase setpoints for coil currents based on
    stimulation mode and the given input.

    Output has a latency of 3 cycles relative to rising edge of input_ready

    Inputs:
    - clk: clock signal
    - rst: active-high reset signal
    - input_ready: single-cycle pulse to indicate that inputs are ready
    - mode: stimulation mode (no modulation, amplitude modulation, or temporal interference)
    - ref_phase: reference instantaneous phase signal
    - amplitude1: required maximum current amplitude for coil 1 current
    - amplitude2: required maximum current amplitude for coil 2 current
    - modulation: modulation signal between 0 and 1. Controls instantaneous magnitude in amplitude modulation
                  mode and relative phase in temporal interference mode

    Outputs:
    - setpoint_mag1: instantaneous magnitude of setpoint signal for coil 1 current
    - setpoint_phase1: instantaneous phase of setpoint signal for coil 1 current
    - setpoint_mag2: instantaneous magnitude of setpoint signal for coil 2 current
    - setpoint_phase2: instantaneous phase of setpoint signal for coil 2 current
    - output_ready: single-cycle pulse to indicate that output signals are ready
*/

`timescale 1ns/1ps

`include "config.sv"

module setpoint_generator(
    input clk,
    input rst,
    input input_ready,
    input [`MODE_NBITS-1:0] mode,
    input signed [`FP_NBITS-1:0] amplitude1,
    input signed [`FP_NBITS-1:0] amplitude2,
    input signed [`FP_NBITS-1:0] modulation,
    
    output reg signed [`FP_NBITS-1:0] setpoint_mag1,
    output reg signed [`FP_NBITS-1:0] setpoint_phase1,
    output reg signed [`FP_NBITS-1:0] setpoint_mag2,
    output reg signed [`FP_NBITS-1:0] setpoint_phase2,
    output reg output_ready
);
    // Convert modulation signal to corresponding relative phase signal for phase modulation
    // in temporal interference mode
    wire signed [`FP_NBITS-1:0] relative_phase;
    wire relative_phase_ready;
    modulation_to_relative_phase mtrp_inst(
        .clk(clk), .rst(rst),
        .input_ready(input_ready),
        .modulation(modulation),
        .output_ready(relative_phase_ready),
        .relative_phase(relative_phase)
    );

    // Pipelined multipliers to calculate setpoint magnitude in amplitude modulation mode
    reg signed [`FP_NBITS-1:0] amplitude1_z, amplitude2_z, modulation1_z, modulation2_z; 
    reg signed [2*`FP_NBITS-1:0] mag1_scaled, mag2_scaled, mag1_scaled_z, mag2_scaled_z;
    
    // Delay to detect rising edges of input_ready
    reg input_ready_z = 0; always @(posedge clk) input_ready_z <= input_ready;

    reg [2:0] pipeline_counter = 0; reg working = 0;
    always @(posedge clk) begin
        if (rst) begin
            setpoint_mag1 <= 0;
            setpoint_mag2 <= 0;
            setpoint_phase1 <= 0;
            setpoint_phase2 <= 0;
            output_ready <= 0;
            pipeline_counter <= 0;
            working <= 0;
        end 
        else begin
            if (input_ready && !input_ready_z) begin
                pipeline_counter <= 0;
                working <= 1;
                
                // load inputs of the amplitude modulation multiplier
                amplitude1_z <= amplitude1;
                modulation1_z <= modulation;
                amplitude2_z <= amplitude2;
                modulation2_z <= modulation;
            end
            else begin
                if (working) begin
                    // Step 0: scale the amplitude by the modulation signal
                    mag1_scaled <= amplitude1_z * modulation1_z;
                    mag2_scaled <= amplitude2_z * modulation2_z;

                    // Step 1: load output registers of the multiplier
                    mag1_scaled_z <= mag1_scaled;
                    mag2_scaled_z <= mag2_scaled;

                    // Step 2: generate output signals
                    if (pipeline_counter == 2) begin
                        if (mode[`MODE_AM_VS_TI_BIT]) begin // TI stimulation
                            setpoint_mag1 <= amplitude1;
                            setpoint_mag2 <= amplitude2;
                            setpoint_phase1 <= (relative_phase>>>1);
                            setpoint_phase2 <= -(relative_phase>>>1);
                        end
                        else begin // AM stimulation
                            setpoint_mag1 <= mag1_scaled_z >>> (`FP_NBITS-1);
                            setpoint_mag2 <= mag2_scaled_z >>> (`FP_NBITS-1);
                            setpoint_phase1 <= 0;
                            setpoint_phase2 <= 0;
                        end
                        working <= 0;
                        output_ready <= 1;
                    end
                    else begin
                        pipeline_counter <= pipeline_counter + 1;
                    end
                end
                else begin
                    output_ready <= 0;
                end
            end
        end
    end
endmodule

