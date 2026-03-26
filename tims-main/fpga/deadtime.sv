/*
    Module: deadtime
    Description:
    This module adds a deadtime to a PWM signal for controlling a half-bridge driver. 
    The deadtime ensures that there is a delay between turning off one side of the bridge and turning on the other, 
    preventing both sides from being on at the same time and causing a short circuit.

    - The deadtime is controlled by the parameter `PWM_DEADTIME_NTICKS`, which specifies the number of clock ticks 
      for the deadtime period.
    - The module generates two output signals, `H` and `L`, which correspond to the high and low side drivers of the half-bridge.
    - The high side driver (`H`) and low side driver (`L`) are turned on with a deadtime inserted between the transitions.
    - `SIG` is the input PWM signal, and the deadtime ensures proper timing of the transitions between high and low sides.

    Inputs:
    - clk: The main clock signal.
    - rst: Active-high reset signal.
    - SIG: The PWM input signal for controlling the half-bridge.

    Outputs:
    - H: Output signal for the high side driver.
    - L: Output signal for the low side driver.

    Notes:
    - The deadtime is added to both the rising and falling edges of the PWM signal.
    - `PWM_DEADTIME_NTICKS` is the number of clock ticks that define the deadtime duration.
*/

`timescale 1ns/1ps

`include "config.sv"

module deadtime (
    input clk,
    input rst,
    input SIG,


    output reg H,
    output reg L
);
    parameter DEADTIME_NTICKS = `PWM_DEADTIME_NTICKS;
    
    reg SIG_prev = 0; // for detecting and falling edges

    reg [`FP_NBITS-1:0] counter = 0; // for timing low->high and high->low transitions

    reg pending_high = 0; // to signal that a low->high transition is pending
    reg pending_low = 0;  // to signal that a high->low transition is pending

    always @(posedge clk) begin
        if (rst) begin
            H <= 0;
            L <= 0;
            SIG_prev <= 0;
            counter <= 0;
            pending_high <= 0;
            pending_low <= 0;
        end
        else begin
            if (SIG && !SIG_prev) begin // rising edge
                L <= 0; H <= 0;     // turn off everything
                pending_high <= 1;  // need to turn on high side in PWM_DEADTIME_NUM_TICKS ticks
                pending_low <= 0;
                counter <= 0;       // accumulate ticks here to know when to turn on high side
            end

            if (pending_high) begin
                if (counter == DEADTIME_NTICKS-1) begin
                    L <= 0; H <= 1;     // turn on high side
                    pending_high <= 0;  // clear request to go high
                    counter <= 0;       // reset deadtime counter
                end
                else begin
                    L <= 0; H <= 0;     // still in deadtime; keep everything off
                    counter <= counter + 1; 
                end
            end

            if (!SIG && SIG_prev) begin
                L <= 0; H <= 0;         // turn off everything
                pending_low <= 1;       // need to turn on low side in PWM_DEADTIME_NUM_TICKS ticks
                pending_high <= 0;
                counter <= 0;           // accumulate ticks here to know when to turn on low side
            end

            if (pending_low) begin
                if (counter == DEADTIME_NTICKS-1) begin
                    L <= 1; H <= 0;     // turn on low side
                    pending_low <= 0;   // clear request to go low
                    counter <= 0;       // reset deadtime counter
                end
                else begin
                    L <= 0; H <= 0;     // still in deadtime; keep everything off
                    counter <= counter + 1;
                end
            end
            SIG_prev <= SIG;
        end
    end
endmodule
