/*
    Module: cross_correlation
    Description:
    This module implements a fixed-point PI Controller. Inputs, output, and parameters are represented
    as signed fixed-point number with FP_NBITS total number of bits with 1 sign bit and:
        - error signal and output signal have (FP_NBITS-1) fraction bits
        - parameters have a configurable PARAM_FRACTION_BITS fraction bits.

    Output is clamped between OUT_MAX and OUT_MIN.

    P and I parameters can be negative but both must have the same sign.

    Output has a latency of 6 clock cycles relative to the rising edge of input_ready  

    Inputs:
    - clk: The main clock signal.
    - rst: Active-high reset signal.
    - input_ready: Pulse indicating new inputs are available.
    - error: (setpoint - feedback).
    - p_factor: proportional factor
    - i_factor: integral factor
    
    Outputs:
    - out: output control signal
    - output_ready: Single-cycle pulse that indicates when output data is available.
*/

`timescale 1ns/1ps

`include "config.sv"

module pi_controller(
    clk, rst,
    input_ready, error,
    p_factor, i_factor,
    out, output_ready);

    localparam FP_NBITS = `FP_NBITS;
    localparam PP_NCYCLES = 7; // Number of cycles in processing pipeline (after sample acquisition)
    localparam PP_NBITS = $rtoi($ceil($clog2(PP_NCYCLES+1)));

    // Maximum and minimum values the output is allowed to take
    parameter bit signed [FP_NBITS-1:0] OUT_MAX = `FP_MAX;
    parameter bit signed [FP_NBITS-1:0] OUT_MIN = `FP_MIN;

    // Number of fraction bits in parameter representation
    parameter PARAM_FRACTION_BITS = `PI_CONTROLLER_PARAM_FRACTION_BITS;

    input clk;
    input rst;
    input input_ready;
    input signed [FP_NBITS-1:0] error;

    input signed [FP_NBITS-1:0] p_factor;
    input signed [FP_NBITS-1:0] i_factor;

    output reg signed [FP_NBITS-1:0] out;
    output reg output_ready;
 
    // Delay line to detect rising edges of input_ready
    reg input_ready_z = 0; 
    always @(posedge clk) input_ready_z <= input_ready;

    // Flag to indicate computation is in progress
    reg working = 0;

    // Counter for keeping track of processing pipeline
    reg [PP_NBITS:0] pipeline_index = 0;

    // Input registers for pipelining multipliers
    reg signed [FP_NBITS-1:0] p_factor_reg;
    reg signed [FP_NBITS-1:0] i_factor_reg;
    reg signed [FP_NBITS:0] error_for_p_multiplier;
    reg signed [FP_NBITS:0] error_for_i_multiplier;

    // Results of error multiplied by PI factors
    // 1 sign bit, (FP_NBITS - PARAM_FRACTION_BITS + 1) value bits, and (FP_NBITS-1+PARAM_FRACTION_BITS) fraction bits
    // a delay is added to pipeline multiplier output
    reg signed [2*FP_NBITS:0] error_times_p, error_times_p_z;
    reg signed [2*FP_NBITS:0] error_times_i, error_times_i_z;

    // Calculation results after removing the extra scaling bits due to multiplication
    // 1 sign bit, (FP_NBITS - PARAM_FRACTION_BITS + 1) value bits, and (FP_NBITS-1) fraction bits
    reg signed [2*FP_NBITS-PARAM_FRACTION_BITS:0] p_term = 0;
    reg signed [2*FP_NBITS-PARAM_FRACTION_BITS:0] i_term_uncapped = 0;
    reg signed [2*FP_NBITS-PARAM_FRACTION_BITS:0] i_term = 0;
    reg signed [2*FP_NBITS-PARAM_FRACTION_BITS:0] out_uncapped = 0;
    
    always @(posedge clk) begin
        if (rst) begin
            working <= 0;
            output_ready <= 0;
            pipeline_index <= 0;
            out <= 0;
            i_term <= 0;
        end
        else begin
            if (input_ready && !input_ready_z) begin // new input
                working <= 1;
                output_ready <= 0;
                pipeline_index <= 0;

                // Load error and factors into multiplier input registers
                error_for_p_multiplier <= error;
                error_for_i_multiplier <= error;
                p_factor_reg <= p_factor;
                i_factor_reg <= i_factor;
            end
            else if (working) begin
                // Step 0: multiply error by P and I factors
                error_times_p <= error_for_p_multiplier * p_factor_reg;
                error_times_i <= error_for_i_multiplier * i_factor_reg;

                // Step 1: output registers for multipliers
                error_times_p_z <= error_times_p;
                error_times_i_z <= error_times_i;

                // Step 2: Correct for scaling due to fraction bits
                p_term <= (error_times_p_z >>> PARAM_FRACTION_BITS);
                if (pipeline_index == 2)
                    i_term_uncapped <= i_term + (error_times_i_z >>> PARAM_FRACTION_BITS);

                // Step 3: cap the integral term to OUT_MAX and OUT_MIN
                if (pipeline_index == 3) begin
                    if (i_term_uncapped > OUT_MAX)
                        i_term <= OUT_MAX;
                    else if (i_term_uncapped < OUT_MIN)
                        i_term <= OUT_MIN;
                    else
                        i_term <= i_term_uncapped;
                end
                
                // Step 4: combine P and I terms  
                out_uncapped <= p_term + i_term;

                // Step 5: cap the output to OUT_MAX and OUT_MIN
                if (pipeline_index == 5) begin
                    if (out_uncapped > OUT_MAX)
                        out <= OUT_MAX;
                    else if (out_uncapped < OUT_MIN)
                        out <= OUT_MIN;
                    else
                        out <= out_uncapped;

                    output_ready <= 1;
                    working <= 0;
                end
                
                pipeline_index <= pipeline_index + 1;
            end
            else begin
                output_ready <= 0;
            end
        end
    end
endmodule
