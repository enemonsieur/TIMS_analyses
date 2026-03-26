
/*
    Module: remote_io
*/

`timescale 1ns/1ps

`include "config.sv"

module remote_io (
    input clk,

    input cs,
    input sck,
    input rx,
    output tx,

    input [`FP_NBITS-1:0] aout1, aout2,

    output [`FP_NBITS-1:0] ain1, ain2,
    output [`FP_NBITS-1:0] ain3, ain4,
    output [`FP_NBITS-1:0] ain5, ain6
);
    // Number of bits per word
    localparam W = 8 * `FP_NBITS;

    wire spi_data_out_ready;
    reg spi_data_in_ready = 0;
    wire [W-1:0] spi_data_in;
    wire [W-1:0] spi_data_out;
    spi_receiver #(.WORD_NBITS(W)) spi_receiver_inst (
        .clk(clk), .sck(sck), .rx(rx), .cs(cs), .tx(tx),
        .data_in_ready(spi_data_in_ready), .data_out_ready(spi_data_out_ready),
        .data_in(spi_data_in), .data_out(spi_data_out)
    );

    assign ain1 = spi_data_out[8*`FP_NBITS-1:7*`FP_NBITS];
    assign ain2 = spi_data_out[7*`FP_NBITS-1:6*`FP_NBITS];
    assign ain3 = spi_data_out[6*`FP_NBITS-1:5*`FP_NBITS];
    assign ain4 = spi_data_out[5*`FP_NBITS-1:4*`FP_NBITS];
    assign ain5 = spi_data_out[4*`FP_NBITS-1:3*`FP_NBITS];
    assign ain6 = spi_data_out[3*`FP_NBITS-1:2*`FP_NBITS]; 

    assign spi_data_in[8*`FP_NBITS-1:7*`FP_NBITS] = aout1;
    assign spi_data_in[7*`FP_NBITS-1:6*`FP_NBITS] = aout2;
    assign spi_data_in[6*`FP_NBITS-1:5*`FP_NBITS] = 1234;
    assign spi_data_in[5*`FP_NBITS-1:4*`FP_NBITS] = 1234;
    assign spi_data_in[4*`FP_NBITS-1:3*`FP_NBITS] = 1234;
    assign spi_data_in[3*`FP_NBITS-1:2*`FP_NBITS] = 1234; 
    assign spi_data_in[2*`FP_NBITS-1:1*`FP_NBITS] = 1234; 
    assign spi_data_in[1*`FP_NBITS-1:0*`FP_NBITS] = 1234; 

endmodule
