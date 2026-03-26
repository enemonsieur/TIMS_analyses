/*
    Module: adc_driver
    Description: 
        SPI driver for a pair of MAX11105 ADCs. Both ADCs are connected to the same CS
        and SCK lines in order to sample concurrently.

        Output data is shifted to center around 0 and signed-extended to FP_NBITS (i.e. 
        scaled to the -1 to 1 range).

        Samples are triggered by a rising edge on the TRIG line.
*/

`timescale 1ns/1ps

`include "config.sv"

module adc_driver(
    input clk,
    input rst,
    input trig,
    input sdl1, 
    input sdl2, 
    input sck, 
    output reg cs,
    output reg sample_ready,
    output reg signed [`FP_NBITS-1:0] sample1,
    output reg signed [`FP_NBITS-1:0] sample2
); 
    localparam  bit [`ADC_NBITS-1:0] ADC_OFFSET = (1 << (`ADC_NBITS-1));
    
    // Number of SCK cycles from the falling edge of CS (conversion start
    // signal) to the first falling edge of SCK on which valid data can be read
    localparam TRANSMISSON_START_OFFSET = 3;

    initial begin
        cs = 1;
        sample_ready = 0;
        sample1 = 0;
        sample2 = 0;
    end
    
    // Counter to keep track of how many bits were received
    localparam BIT_COUNTER_NBITS = $rtoi($ceil($clog2(`ADC_NBITS))) + 1;
    reg [BIT_COUNTER_NBITS-1:0] bit_counter = 0;
    
    // Registers to hold samples as data is shifted in
    reg [`ADC_NBITS-1:0] sample1_temp = 0, sample2_temp = 0;

    // Delays to detect edges
    reg sck_z = 0; always @(posedge clk) sck_z <= sck;
    reg trig_z = 0; always @(posedge clk) trig_z <= trig;
    
    reg transmission_start_pending = 0;
    reg transmission_active = 0;
    always @(posedge clk) begin
        if (rst) begin
            cs <= 1;
            sample_ready <= 0;
            sample1 <= 0;
            sample2 <= 0;
            bit_counter <= 0;
            transmission_start_pending <= 0;
            transmission_active <= 0;
        end
        else begin
            if (trig && !trig_z) begin // rising edge
                // Reset relevant registers
                bit_counter <= 0;
                sample1_temp <= 0;
                sample2_temp <= 0;
                sample_ready <= 0;

                // Signal that ADC conversion and data transmission should start
                // soon
                transmission_start_pending <= 1;
                bit_counter <= 0;
            end
            else begin
                if (transmission_start_pending && !sck && sck_z) begin
                    // Start conversion at the first falling edge of sck after
                    // trigger signal was received
                    cs <= 0;

                    if (bit_counter < TRANSMISSON_START_OFFSET-1) begin
                        // bit_counter is reused here to count until
                        // transmission start
                        bit_counter <= bit_counter + 1;
                    end
                    else begin
                        bit_counter <= 0;
                        transmission_active <= 1;
                        transmission_start_pending <= 0; // clear pending flag
                    end
                end
                else if (transmission_active) begin
                    if (!sck && sck_z) begin // falling edge
                        // Shift data in
                        sample2_temp <= {sample2_temp[`ADC_NBITS-2:0], sdl2}; 
                        sample1_temp <= {sample1_temp[`ADC_NBITS-2:0], sdl1};
                        bit_counter <= bit_counter + 1;
                        sample_ready <= 0;
                    end
                    else if (bit_counter == `ADC_NBITS) begin
                        // Done, output data
                        transmission_active <= 0;
                        sample_ready <= 1;
                        cs <= 1;
                        bit_counter <= 0;
                        sample1_temp <= sample1_temp - ADC_OFFSET;
                        sample1 <= (sample1_temp - ADC_OFFSET) <<< (`FP_NBITS-`ADC_NBITS);
                        sample2 <= (sample2_temp - ADC_OFFSET) <<< (`FP_NBITS-`ADC_NBITS);
                    end
                end
                else begin
                    sample_ready <= 0;
                end
            end
        end
    end
    
endmodule
