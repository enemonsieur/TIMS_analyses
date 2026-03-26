/*
    Module: reference_generator
    Description:
    This module generates a reference signal with the following characteristics:
    - The frequency of the reference signal equals the carrier frequency.
    - The phase signal can be interpreted as a signed number in the range -1 to 1, which maps to -pi to +pi
    - The carrier frequency is determined by FPGA_FCLK / (clk_ticks_per_sample * SAMPLES_PER_CARRIER_PERIOD).
    - A sampling clock signal is generated with a frequency of FPGA_FCLK / clk_ticks_per_sample

    Inputs:
    - clk: The main clock signal.
    - rst: Active-low reset signal.
    - clk_ticks_per_sample: The number of clock ticks per sampling period.
    - phase_step: Precomputed phase increment per clock tick.

    Outputs:
    - phase: The current phase of the reference signal, mapped from -pi to +pi.
    - sin: sin(phase)
    - cos: sin(phase)
    - sclk: The sampling clock with approximately a 50% duty cycle, generated based on the carrier frequency.

    Notes:
    - SAMPLES_PER_CARRIER_PERIOD must be a power of 2.
    - The phase_step should be precomputed as 2^(FP_NBITS + FP_EXTRA_BITS) / (clk_ticks_per_sample*SAMPLES_PER_CARRIER_PERIOD).
    - Output signals is valid 1 clock cycle after a falling edge on rst
*/

`timescale 1ns/1ps

`include "config.sv"

`define SPC `SAMPLES_PER_CARRIER_PERIOD
`define SPC_NBITS $clog2(`SAMPLES_PER_CARRIER_PERIOD)

module reference_generator(
    input clk,
    input rst,
    input [`FP_NBITS-1:0] clk_ticks_per_sample,
    input signed [`FP_NBITS+`FP_EXTRA_BITS-1:0] phase_step,

    output reg signed [`FP_NBITS-1:0] phase,
    output reg signed [`FP_NBITS-1:0] sin,
    output reg signed [`FP_NBITS-1:0] cos,
    output reg sclk
);
    // sine and cosine tables
    reg signed [`FP_NBITS-1:0] sine_table [0:`SPC-1];
    reg signed [`FP_NBITS-1:0] cosine_table [0:`SPC-1];
    initial begin
        $readmemb("memfiles/sine_table.mem", sine_table);
        $readmemb("memfiles/cosine_table.mem", cosine_table);
    end

    reg [`FP_NBITS-1:0] phase_counter = 0, sclk_counter = 0;
    reg [`SPC_NBITS-1:0] sample_index = 0;
    
    reg [`FP_NBITS-1:0] ctps = `MIN_CLK_TICKS_PER_SAMPLE;
    reg [`FP_NBITS-1:0] phase_counter_max = `MIN_CLK_TICKS_PER_SAMPLE-1;
    reg [`FP_NBITS-1:0] sclk_counter_max = `MIN_CLK_TICKS_PER_SAMPLE-1;

    reg signed [`FP_NBITS+`FP_EXTRA_BITS-1:0] phase_with_extra_bits = 0;

    always @(posedge clk) begin
        if (rst) begin
            ctps <= `MIN_CLK_TICKS_PER_SAMPLE;
            phase_counter_max <= `MIN_CLK_TICKS_PER_SAMPLE-1;
            sclk_counter_max <= `MIN_CLK_TICKS_PER_SAMPLE-1;
            phase_counter <= 0;
            sclk_counter <= 0;
            sample_index <= 0;
            phase_with_extra_bits <= 0;
            phase <= 0;
            sin <= sine_table[0];
            cos <= cosine_table[0];
            sclk <= 0;
        end
        else begin
            if (clk_ticks_per_sample != ctps) begin
                // update counter periods
                ctps <= clk_ticks_per_sample;
                phase_counter_max <= (clk_ticks_per_sample << `SPC_NBITS) - 1;
                sclk_counter_max <= clk_ticks_per_sample - 1;

                // reset everything
                phase_counter <= 0;
                sclk_counter <= 0;
                sample_index <= 0;
                phase_with_extra_bits <= 0;
                phase <= 0;
                sin <= sine_table[0];
                cos <= cosine_table[0];
                sclk <= 0;
            end
            else begin
                if (phase_counter == phase_counter_max) begin
                    phase_counter <= 0;
                    phase_with_extra_bits <= 0;
                end
                else begin
                    phase_counter <= phase_counter + 1;
                    phase_with_extra_bits <= phase_with_extra_bits + phase_step;
                end

                if (sclk_counter == sclk_counter_max) begin
                    sclk_counter <= 0;
                    sample_index <= sample_index + 1;
                end
                else begin
                    sclk_counter <= sclk_counter + 1; 
                end

                phase <= phase_with_extra_bits[`FP_NBITS+`FP_EXTRA_BITS-1:`FP_EXTRA_BITS];
                sin <= sine_table[sample_index];
                cos <= cosine_table[sample_index];
                sclk <= (sclk_counter < (clk_ticks_per_sample>>1));
            end
        end
    end
endmodule

