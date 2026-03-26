/*
    Module: modulation_to_relataive_phase
    Description:
    This module converts the desired envelope modulation signal in the target region in TI
    stimulation to the required phase difference between coil currents:
        relative_phase = 2 * arccos(modulation)
    where modulation is between 0 and 1.
    
    Output latency = 1 clk cycle

    Inputs:
    - clk: The main clock signal.
    - rst: Active-high reset signal.
    - input_ready: Pulse to indicate new input data is available.
    - modulation: desired modulation. signed non-negative number between 0 and 1   
    
    Outputs:
    - output_ready: Single-cycle pulse that indicates when output data is ready.
    - relative_phase: phase difference corresponding to given modulation. -pi to pi.
*/
`timescale 1ns/1ps

`include "config.sv"

module modulation_to_relative_phase(
    input clk,
    input rst,
    input input_ready,
    input signed [`FP_NBITS-1:0] modulation,

    output reg output_ready,
    output reg signed [`FP_NBITS-1:0] relative_phase
);
    reg signed [`FP_NBITS-1:0] modulation_to_relative_phase_table [0:(1<<`MODULATION_RESOLUTION_NBITS)-1];
    initial begin
        $readmemb("memfiles/modulation_to_relative_phase.mem", modulation_to_relative_phase_table);
        output_ready = 0;
        relative_phase = 0;
    end

    reg input_ready_z = 0; always @(posedge clk) input_ready_z <= input_ready;

    reg working = 0;
    reg [`MODULATION_RESOLUTION_NBITS-1:0] table_index = 0;
    always @(posedge clk) begin
        if (rst) begin
            output_ready <= 0;
            relative_phase <= 0;
        end
        else begin
            if (input_ready && !input_ready_z) begin
                table_index <= modulation[`FP_NBITS-2:`FP_NBITS-1-`MODULATION_RESOLUTION_NBITS];
                working <= 1;
            end
            else if (working) begin
                relative_phase <= modulation_to_relative_phase_table[table_index];
                output_ready <= 1;
                working <= 0;
            end
            else begin
                output_ready <= 0;
            end
        end
    end
endmodule

