/*
    Module: cartesian_to_polar
    Description:
    This module converts Cartesian coordinates (x, y) into polar coordinates (magnitude and phase)
    using the CORDIC (COordinate Rotation DIgital Computer) algorithm. It operates iteratively to
    compute the vector magnitude and phase angle efficiently using shift-add operations.

    Output latency = FP_NBITS + 1 clk cycles

    Inputs:
    - clk: The main clock signal.
    - rst: Active-high reset signal.
    - input_ready: Pulse to indicate new input data is available.
    - x: Signed fixed-point representation of the x-coordinate.
    - y: Signed fixed-point representation of the y-coordinate.

    Magnitude output is clamped to FP_MAX
    
    Outputs:
    - mag: Computed magnitude of the input vector. Same units as the inputs x and y.
    - phase: Computed phase angle of the input vector, maps from -pi to pi
    - output_ready: Single-cycle pulse that indicates when output data is ready.
*/

`timescale 1ns/1ps

`include "config.sv"

module cartesian_to_polar (
    input clk,
    input rst,
    input input_ready,
    input signed [`FP_NBITS-1:0] x,
    input signed [`FP_NBITS-1:0] y,

    output reg signed [`FP_NBITS-1:0] mag,
    output reg signed [`FP_NBITS-1:0] phase,
    output reg output_ready
);
    localparam bit signed [`FP_NBITS-1:0] FP_MAX = `FP_MAX;

    // Read atan lookup table
    reg signed [`FP_NBITS-1:0] atan_table [0:`CORDIC_NUM_ITERATIONS-1];
    initial begin
        $readmemb("memfiles/cordic_atan_table.mem", atan_table);
    end
    
    // Add a delay to detect rising edges of input_ready
    reg input_ready_z = 0; always @(posedge clk) input_ready_z <= input_ready;

    // Flag to indicate computation is in progress
    reg working = 0;

    // Intermediate computation results. An extra bit is added to x and
    // y registers to handle inputs close to the bounds of the fixed-point
    // range
    reg signed [`FP_NBITS:0] x_i, y_i;
    reg signed [`FP_NBITS-1:0] phase_i;

    // Indicates if input vector had an angle of -pi/2 to pi/2
    reg x_positive;

    // Iteration counter
    reg [$rtoi($ceil($clog2(`CORDIC_NUM_ITERATIONS+2))):0] i = 0;

    // Pipelined multiplier to correct CORDIC gain of the magnitude result
    reg signed [`FP_NBITS:0] x_i_z;
    reg signed [2*`FP_NBITS:0] x_i_scaled, x_i_scaled_z;
    always @(posedge clk) begin
        x_i_z <= x_i;
        x_i_scaled <= x_i_z * `CORDIC_K;
        x_i_scaled_z <= x_i_scaled;
    end

    always @(posedge clk) begin
        if (rst) begin
            i <= 0;
            working <= 0;
            output_ready <= 0;
            mag <= 0;
            phase <= 0;
        end
        else begin
            // Input rising edge; input data is ready
            if (input_ready && !input_ready_z) begin
                working <= 1;
                output_ready <= 0;
                i <= 0;

                // CORDIC only works for vectors where x is non-negative
                // reflect input vector around y axis
                x_i <= (x<0)? -x : x;
                y_i <= y;
                x_positive <= (x>0); // store the sign to apply angle correction later
                phase_i <= 0;
            end
            else if (working) begin
                if (i <= `CORDIC_NUM_ITERATIONS + 1) begin // 2 extra iterations to wait for result from gain multiplier
                    output_ready <= 0;
                    i <= i + 1;

                    if (i < `CORDIC_NUM_ITERATIONS) begin
                        if (y_i >= 0) begin
                            x_i <= x_i + (y_i >>> i);
                            y_i <= y_i - (x_i >>> i);
                            phase_i <= phase_i + atan_table[i];
                        end
                        else begin
                            x_i <= x_i - (y_i >>> i);
                            y_i <= y_i + (x_i >>> i);
                            phase_i <= phase_i - atan_table[i];
                        end
                    end
                end
                else begin // done
                    working <= 0;
                    output_ready <= 1;
                    // Output the gain-corrected magnitude
                    if (x_i_scaled_z[2*`FP_NBITS-1:`FP_NBITS] > FP_MAX)
                        mag <= FP_MAX;
                    else
                        mag <= x_i_scaled_z[2*`FP_NBITS-1:`FP_NBITS];

                    // Correct the phase angle if the input vector was
                    // reflected earlier (x was negative)
                    if (x_positive) begin // no correction needed
                        phase <= phase_i;
                    end
                    else begin // phase = pi - phase_i
                        phase <= FP_MAX - phase_i;
                    end
                end
            end
            else begin
                output_ready <= 0;
            end
        end
    end
endmodule
