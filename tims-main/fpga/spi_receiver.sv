/*
    Module: spi_receiver
    Description: SPI receiver with configurable word length

    SPI MODE 1: CPOL = 0, CHPA = 1. Data sampled on the falling edge and shifted out on the rising edge
    CS active low
    
    Ports:
    - clk: The main clock signal.
    - sck: Serial clock line
    - rx: serial data input line
    - cs: chip select - active low
    - tx: serial data output line
    - data_ready: brought high for one cycle when a word has been received and is available of data_out
    - data_out: received word
    - data_in: next word to send. latched on CS and data_ready falling edges
*/

`timescale 1ns/1ps

`include "config.sv"

module spi_receiver(clk, sck, rx, cs, tx, data_in_ready, data_in, data_out_ready, data_out);
    parameter WORD_NBITS = `INTERFACE_WORD_NBITS;
    
    input clk;

    input sck;
    input rx;
    input cs;
    output reg tx;

    input data_in_ready;
    input [WORD_NBITS-1:0] data_in;
    
    output reg data_out_ready;
    output reg [WORD_NBITS-1:0] data_out;
    
    // Delay lines to sync input signal to internal clock and detect edges    
    reg [2:0] sck_zline = 0;
    reg [2:0] cs_zline = 0;
    reg [1:0] rx_zline = 0;
    always @(posedge clk) begin
        sck_zline <= {sck_zline[1:0], sck};

        cs_zline <= {cs_zline[1:0], cs};
        rx_zline <= {rx_zline[0], rx};
    end

    // transmission bit counter - extra bit to detect overflow
    reg [$clog2(WORD_NBITS):0] bit_counter = 0;

    // scratch registers to shift data into/from
    reg [WORD_NBITS-1:0] data_out_temp, data_in_temp;

    // Delay line to detect edges of data_in_ready
    reg data_in_ready_z = 0; always @(posedge clk) data_in_ready_z <= data_in_ready;

    initial begin
        tx = 0;
        data_out_ready = 0;
        data_out = 0;
    end
    
    always @(posedge clk) begin
        if (!cs_zline[1]) begin // transmission active
            if (cs_zline[2] || (data_in_ready_z && !data_in_ready)) begin
                // falling edge of CS or falling edge of data_in_ready
                // word transmission just done (or started); ready for new word
                // latch input data and bit reset counter
                data_in_temp <= data_in;
                bit_counter <= 0;
                data_out_ready <= 0;
            end 
            else if (sck_zline[2:1] == 2'b01) begin // SCK rising edge
                // shift data out on tx
                tx <= data_in_temp[WORD_NBITS-1];
                data_in_temp <= {data_in_temp[WORD_NBITS-2:0], 1'b0};
            end
            else if (sck_zline[2:1] == 2'b10) begin // SCK falling edge
                // shift rx data in
                data_out_temp <= {data_out_temp[WORD_NBITS-2:0], rx_zline[1]};
                bit_counter <= bit_counter + 1;
            end
            else if (bit_counter[$clog2(WORD_NBITS)]) begin // all bits done
                bit_counter <= 0;
                data_out_ready <= 1;
                data_out <= data_out_temp;
            end
            else begin
                data_out_ready <= 0;
            end
        end
    end
endmodule
