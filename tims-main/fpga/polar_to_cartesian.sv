/*
    Module: cartesian_to_polar
    Description:
    This module converts polar coordinates (mag, phase) into cartesian coordinates (x and y)
    using the CORDIC (COordinate Rotation DIgital Computer) algorithm.

    Output latency = FP_NBITS + 1 clk cycles

    x and y outputs are clamped to FP_MAX and FP_MIN.

    Inputs:
    - clk: The main clock signal.
    - rst: Active-high reset signal.
    - input_ready: Pulse to indicate new input data is available.
    - mag: Magnitude of the input vector.
    - phase: Phase angle of the input vector, mapped from -pi to pi
    
    Outputs:
    - x: Signed fixed-point representation of the x-coordinate.
    - y: Signed fixed-point representation of the y-coordinate.
    - output_ready: Single-cycle pulse that indicates when output data is ready.
*/

`timescale 1ns/1ps

`include "config.sv"

module polar_to_cartesian (
    input clk,
    input rst,
    input input_ready,
    input signed [`FP_NBITS-1:0] mag,
    input signed [`FP_NBITS-1:0] phase,

    output reg signed [`FP_NBITS-1:0] x,
    output reg signed [`FP_NBITS-1:0] y,
    output reg output_ready
);
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
    reg signed [`FP_NBITS-1:0] phase_i, phase_in;

    // Indicates if input vector had an angle of -pi/2 to pi/2
    reg reflected;

    // Iteration counter
    reg [$rtoi($ceil($clog2(`CORDIC_NUM_ITERATIONS+2))):0] i = 0;

    // Pipelined multiplier to correct CORDIC gain of the x and y results
    reg signed [`FP_NBITS:0] x_i_z, y_i_z;
    reg signed [2*`FP_NBITS:0] x_i_scaled, x_i_scaled_z, y_i_scaled, y_i_scaled_z;
    always @(posedge clk) begin
        x_i_z <= x_i;
        x_i_scaled <= x_i_z * `CORDIC_K;
        x_i_scaled_z <= x_i_scaled;
        
        y_i_z <= y_i;
        y_i_scaled <= y_i_z * `CORDIC_K;
        y_i_scaled_z <= y_i_scaled;
    end

    // Maximum and minimum values the output is allowed to take
    // to avoid overflow
    localparam bit signed [`FP_NBITS-1:0] FP_MAX = `FP_MAX;
    localparam bit signed [`FP_NBITS-1:0] FP_MIN = `FP_MIN;
    // Corresponding values for (x,y)_i_scaled
    localparam bit signed [2*`FP_NBITS:0] FP_SCALED_MAX = FP_MAX <<< `FP_NBITS;
    localparam bit signed [2*`FP_NBITS:0] FP_SCALED_MIN = FP_MIN <<< `FP_NBITS;

    always @(posedge clk) begin
        if (rst) begin
            i <= 0;
            working <= 0;
            output_ready <= 0;
            x <= 0;
            y <= 0;
        end
        else begin
            // Input rising edge; input data is ready
            if (input_ready && !input_ready_z) begin
                working <= 1;
                output_ready <= 0;
                i <= 0;

                // Start with the vector mag*(1, 0)
                x_i <= mag;
                y_i <= 0;
                phase_i <= 0;
                
                // CORDIC only works for vectors where phase is between -pi/2 and pi/2
                // reflect input vector around y axis
                if (phase > `FP_MAX/2 || phase < `FP_MIN/2) begin
                    reflected <= 1;
                    phase_in <= `FP_MAX - phase;
                end
                else begin
                    reflected <= 0;
                    phase_in <= phase;
                end
            end
            else if (working) begin
                if (i <= `CORDIC_NUM_ITERATIONS + 1) begin // 2 extra iterations to wait for result from gain multiplier
                    output_ready <= 0;
                    i <= i + 1;

                    if (i < `CORDIC_NUM_ITERATIONS) begin
                        if (phase_i >= phase_in) begin
                            x_i <= x_i + (y_i >>> i);
                            y_i <= y_i - (x_i >>> i);
                            phase_i <= phase_i - atan_table[i];
                        end
                        else begin
                            x_i <= x_i - (y_i >>> i);
                            y_i <= y_i + (x_i >>> i);
                            phase_i <= phase_i + atan_table[i];
                        end
                    end
                end
                else begin // done
                    working <= 0;
                    output_ready <= 1;
                    // Output the gain-corrected x. Reflect aroud y axis if the input was reflected earlier
                    if (x_i_scaled_z > FP_SCALED_MAX)
                        x <= reflected? FP_MIN : FP_MAX;
                    else if (x_i_scaled_z < FP_SCALED_MIN)
                        x <= reflected? FP_MAX : FP_MIN;
                    else
                        x <= reflected? -x_i_scaled_z[2*`FP_NBITS-1:`FP_NBITS] : x_i_scaled_z[2*`FP_NBITS-1:`FP_NBITS];

                    // Output the gain-corrected y
                    if (y_i_scaled_z > FP_SCALED_MAX)
                        y <= FP_MAX;
                    if (y_i_scaled_z < FP_SCALED_MIN)
                        y <= FP_MIN;
                    else
                        y <= y_i_scaled_z[2*`FP_NBITS-1:`FP_NBITS];
                end
            end
            else begin
                output_ready <= 0;
            end
        end
    end
endmodule
