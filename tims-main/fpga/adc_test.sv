`timescale 1ns/1ps

`include "config.sv"

module adc_test(
    input sysclk,
    output coil1_a, coil1_b, coil1_en1, coil1_c, coil1_d, coil1_en2,
    output coil2_a, coil2_b, coil2_en1, coil2_c, coil2_d, coil2_en2,
    output coil3_a, coil3_b, coil3_en1, coil3_c, coil3_d, coil3_en2,
    output coil4_a, coil4_b, coil4_en1, coil4_c, coil4_d, coil4_en2,

    input pi_cs, pi_sck, pi_mosi,
    output pi_trig, pi_miso,

    output current_adc_sck,
    output current_adc_cs_a, current_adc_cs_b,
    input current1_adc_dout, current2_adc_dout,
    input current3_adc_dout, current4_adc_dout,

    output pmod_1, pmod_2, pmod_3, pmod_4,
    output pmod_5, pmod_6, pmod_7, pmod_8
);    
    localparam Q = `FP_NBITS;

    wire rst = 0;

    // CLK GENERATION
    wire clk;
    clk_wiz clocking_wizard (.clk(clk), .sysclk(sysclk));
    
    reg [Q-1:0] clk_ticks_per_sample_a = 81;
    reg [Q+`FP_EXTRA_BITS-1:0] phase_step_a = 1000;

    wire sclk_a, sample_ready_a;
    wire [`FP_NBITS-1:0] sample1, sample2;
    
    wire signed [`FP_NBITS-1:0] ref_phase_a;
    reference_generator refgen_inst_a (
        .clk(clk), .rst(rst),
        .clk_ticks_per_sample(clk_ticks_per_sample_a),
        .phase_step(phase_step_a),
        .phase(ref_phase_a),
        .sclk(sclk_a));
 
    reg [Q-1:0] clk_ticks_per_sample_b = 101;
    reg [Q+`FP_EXTRA_BITS-1:0] phase_step_b = 1200;

    wire sclk_b, sample_ready_b;
    wire [`FP_NBITS-1:0] sample3, sample4;
    
    wire signed [`FP_NBITS-1:0] ref_phase_b;
    reference_generator refgen_inst_b (
        .clk(clk), .rst(rst),
        .clk_ticks_per_sample(clk_ticks_per_sample_b),
        .phase_step(phase_step_b),
        .phase(ref_phase_b),
        .sclk(sclk_b));

    current_adcs current_adcs_inst(
        .clk(clk),
        .rst(rst),
        .trig_a(sclk_a),
        .trig_b(sclk_b),
        .sdl1(current1_adc_dout),
        .sdl2(current2_adc_dout),
        .sdl3(current3_adc_dout),
        .sdl4(current4_adc_dout),
        .sck(current_adc_sck),
        .cs_a(current_adc_cs_a),
        .cs_b(current_adc_cs_b),
        .sample_ready_a(sample_ready_a),
        .sample_ready_b(sample_ready_b),
        .sample1(sample1),
        .sample2(sample2),
        .sample3(sample3),
        .sample4(sample4));

    ila ila_inst (
        .clk(clk), // input wire clk
        .probe0(sclk_a), // input wire [0:0]  probe0  
        .probe1(current_adc_cs), // input wire [0:0]  probe1 
        .probe2(current_adc_sck), // input wire [0:0]  probe2 
        .probe3(current1_adc_dout), // input wire [0:0]  probe3 
        .probe4(sample_ready_a), // input wire [15:0]  probe4 
        .probe5(current2_adc_dout), // input wire [15:0]  probe5 
        .probe6(sample1), // input wire [15:0]  probe6 
        .probe7(sample2) // input wire [15:0]  probe7
    );
endmodule
