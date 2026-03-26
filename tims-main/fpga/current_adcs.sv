/*
    Module: current_adcs
    Description: 
        SPI driver for a two pairs of MAX11105 ADCs (4 in total). All ADCs share the
        same SCK signal. Within each pair, both ADCs are connected to the same CS in 
        order to sample concurrently.
        
        Output data is shifted to center around 0 and signed-extended to FP_NBITS (i.e. 
        scaled to the -1 to 1 range).

        Samples are triggered by a rising edges on the TRIG lines.
*/

`timescale 1ns/1ps

`include "config.sv"

module current_adcs(
    input clk,
    input rst,
    input trig_a,
    input trig_b,
    input sdl1, 
    input sdl2, 
    input sdl3, 
    input sdl4,

    output reg sck,
    output cs_a,
    output cs_b,

    output sample_ready_a,
    output sample_ready_b,
    output signed [`FP_NBITS-1:0] sample1,
    output signed [`FP_NBITS-1:0] sample2,
    output signed [`FP_NBITS-1:0] sample3,
    output signed [`FP_NBITS-1:0] sample4
); 
    localparam SCL_COUNTER_PERIOD = `FPGA_FCLK / `ADC_SPI_FREQ; 
    localparam SCL_COUNTER_NBITS = $rtoi($ceil($clog2(SCL_COUNTER_PERIOD))) + 1;
    
    initial begin
        sck = 0;
    end

    // Generate SCK signal
    reg [SCL_COUNTER_NBITS-1:0] scl_counter = 0;
    always @(posedge clk) begin
        if (rst) begin
            scl_counter <= 0;
            sck <= 0;
        end
        else begin
            scl_counter <= (scl_counter == SCL_COUNTER_PERIOD-1)? 0 : scl_counter + 1;  
            sck <= (scl_counter < SCL_COUNTER_PERIOD/2);
        end
    end
        
    adc_driver adc_a(
        .clk(clk), 
        .rst(rst),
        .trig(trig_a),
        .sdl1(sdl1), 
        .sdl2(sdl2), 
        .sck(sck), 
        .cs(cs_a), 
        .sample_ready(sample_ready_a), 
        .sample1(sample1),
        .sample2(sample2));

    adc_driver adc_b(
        .clk(clk), 
        .rst(rst),
        .trig(trig_b),
        .sdl1(sdl3), 
        .sdl2(sdl4), 
        .sck(sck), 
        .cs(cs_b), 
        .sample_ready(sample_ready_b), 
        .sample1(sample3),
        .sample2(sample4));

endmodule
