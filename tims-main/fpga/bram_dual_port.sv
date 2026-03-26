`timescale 1ns/1ps

module bram_dual_port(clka, clkb, ena, enb, wea, web, addra, addrb, dia, dib, doa, dob);
    parameter WIDTH = 256;
    parameter DEPTH = 1024;

    localparam ADDRESS_NBITS = $rtoi($ceil($clog2(DEPTH)));

    input clka, clkb, ena, enb, wea, web;
    input [ADDRESS_NBITS-1:0] addra, addrb;
    input [WIDTH-1:0] dia, dib;
    output [WIDTH-1:0] doa, dob;

    reg [WIDTH-1:0] ram [DEPTH-1:0];
    reg [WIDTH-1:0] doa, dob;

    always @(posedge clka) begin
        if (ena) begin
            if (wea) ram[addra] <= dia;
            doa <= ram[addra];
        end
    end
    
    always @(posedge clkb) begin
        if (enb) begin
            if (web) ram[addrb] <= dib;
            dob <= ram[addrb];
        end
    end
endmodule
