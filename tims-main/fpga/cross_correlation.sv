/*
    Module: cross_correlation
    Description:
    This module calculates the 1D cross-correlation of an input signal with a filter and
    scales the output down by dividing by a power of 2:
    
        out[i] = sum((filter[j] * sample[i+j]) / (2**SCALING_NBITS)

    Inputs and outputs are signed fixed-point numbers with FP_NBITS total number of bits
    and FP_FRACTION_BITS fraction bits
    
    Output latency = N+3 from the rising edge of sample_ready

    Output is only accurate after at least N samples have been obtained.
    Samples before the falling edge of rst are treated as zero.

    Output is clamped to FP_MAX and FP_MIN on overflow.

    Inputs:
    - clk: The main clock signal.
    - rst: Active-high reset signal.
    - sample_ready: Pulse indicating a new sample is available.
    - sample: Signed fixed-point representation of the input signal sample.

    Outputs:
    - out: Computed correlation.
    - output_ready: Single-cycle pulse that indicates when output data is available.
*/

`timescale 1ns/1ps

`include "config.sv"

module cross_correlation(clk, rst, sample_ready, sample, out, output_ready);
    parameter filter_filepath = "filter.mem";
    parameter N = `SAMPLES_PER_CARRIER_PERIOD;
    parameter SCALING_NBITS = $clog2(`SAMPLES_PER_CARRIER_PERIOD)-1;
    parameter FP_FRACTION_BITS = `FP_NBITS-1;

    localparam FP_NBITS = `FP_NBITS;
    localparam N_NBITS = $clog2(N);
    localparam PP_NCYCLES = N + 2; // Number of cycles in processing pipeline (after sample acquisition)
    localparam PP_NBITS = $rtoi($ceil($clog2(PP_NCYCLES+1)));

    // Maximum and minimum values the output is allowed to take
    // to avoid overflow
    localparam bit signed [FP_NBITS-1:0] FP_MAX = `FP_MAX;
    localparam bit signed [FP_NBITS-1:0] FP_MIN = `FP_MIN;
    // Corresponding values for sum_scaled
    localparam bit signed [2*FP_NBITS+SCALING_NBITS:0] SUM_SCALED_MAX =
        FP_MAX <<< (FP_FRACTION_BITS + SCALING_NBITS);
    localparam bit signed [2*FP_NBITS+SCALING_NBITS:0] SUM_SCALED_MIN =
        FP_MIN <<< (FP_FRACTION_BITS + SCALING_NBITS);
            
    input clk;
    input rst;
    input sample_ready;
    input signed [FP_NBITS-1:0] sample;

    output reg signed [FP_NBITS-1:0] out;
    output reg output_ready;
  
    reg signed [FP_NBITS-1:0] filter_coefficients [0:N-1];
    initial begin
        $readmemb(filter_filepath, filter_coefficients);
        out = 0;
        output_ready = 0;
    end

    // Delay line to detect rising edges of sample_ready
    reg sample_ready_z = 0; 
    always @(posedge clk) sample_ready_z <= sample_ready;

    // Registers for pipelining multiplier input and output
    reg signed [FP_NBITS-1:0] sample_reg = 0;
    reg signed [FP_NBITS-1:0] coefficient_reg = 0;
    reg signed [2*FP_NBITS-1:0] sample_times_coefficient_reg = 0;

    // Memory for storing last N samples
    reg signed [FP_NBITS-1:0] samples [0:N-1];

    // Registers for storing sum(filter_coefficient * sample). Extra bits to avoid overflow
    reg signed [2*FP_NBITS+SCALING_NBITS:0] sum_scaled;

    // Flag to indicate computation is in progress
    reg working = 0;

    // Counter for keeping track of processing pipeline
    reg [PP_NBITS:0] pipeline_index = 0;

    // Samples and coefficients are pulled into multiplier inputs to be multiplied and summed over
    // in the first N cycles of the pipeline
    wire [N_NBITS-1:0] sum_index = pipeline_index[N_NBITS-1:0];
    
    // Each bit indices whether the corresponding sample in memory is valid (not an old
    // sample from before rst was pulled low)
    reg [N-1:0] sample_valid = 0;

    always @(posedge clk) begin
        if (rst) begin
            working <= 0;
            output_ready <= 0;
            pipeline_index <= 0;
            sum_scaled <= 0;
            sample_valid <= 0;
            out <= 0;
        end
        else begin
            if (sample_ready && !sample_ready_z) begin // new sample
                working <= 1;
                output_ready <= 0;
                pipeline_index <= 0;
                sum_scaled <= 0;

                // Shift all samples back by one and add the latest sample
                for (integer i=0; i<N-1; i++)
                    samples[i] <= samples[i+1];
                samples[N-1] <= sample;
                 
                // indicate that a new valid sample has been stored in memory
                sample_valid <= {1'b1, sample_valid[N-1:1]};
            end
            else if (working) begin
                // Step 0: pull sample and coefficient into multiplier input registers
                // only if the sample is valid
                sample_reg <= sample_valid[sum_index] ? samples[sum_index] : 0;
                coefficient_reg <= filter_coefficients[sum_index];

                // Step 1: multiply and store output in a register
                sample_times_coefficient_reg <= sample_reg * coefficient_reg;

                // Step 2: accumulate multiplication results
                if (pipeline_index >= 2)
                    sum_scaled <= sum_scaled + sample_times_coefficient_reg;

                // Step 3: output result
                if (pipeline_index == PP_NCYCLES) begin
                    working <= 0;
                    output_ready <= 1;
                    // Scale sum down to and correct for scaling due to fraction bits
                    if (sum_scaled > SUM_SCALED_MAX)
                        out <= FP_MAX;
                    else if (sum_scaled < SUM_SCALED_MIN)
                        out <= FP_MIN;
                    else
                        out <= (sum_scaled >>> (FP_FRACTION_BITS + SCALING_NBITS));
                    
                end
                pipeline_index <= pipeline_index + 1;
            end
            else begin
                output_ready <= 0;
            end
        end
    end
endmodule
