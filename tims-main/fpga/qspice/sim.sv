`timescale 1ns/1ps

`include "config.sv"
`include "params.sv"
`include "reference_generator.sv"

module sim(
    input clk,
    input rst,

    input integer current1_in,
    input integer current2_in,

    input integer mag1_setpoint_in,
    input integer mag2_setpoint_in,
    input integer modulation_in,

    output pwm_ch1a,
    output pwm_ch1b,
    output pwm_ch1c,
    output pwm_ch1d,
    
    output pwm_ch2a,
    output pwm_ch2b,
    output pwm_ch2c,
    output pwm_ch2d,

    output integer mag1_out,
    output integer phase1_out,
    output integer mag2_out,
    output integer phase2_out
);
    reg [`FP_NBITS-1:0] clk_ticks_per_sample = `CLK_TICKS_PER_SAMPLE;
    reg [`FP_NBITS+`FP_EXTRA_BITS-1:0] phase_step = `PHASE_STEP;
  
    reg signed [`FP_NBITS-1:0] current1, current2;
    reg signed [`FP_NBITS-1:0] mag1_setpoint, mag2_setpoint, modulation;
    always @(posedge sclk) begin
        if (current1_in > `FP_MAX) current1 <= `FP_MAX;
        else if (current1_in < `FP_MIN) current1 <= `FP_MIN;
        else current1 <= current1_in[`FP_NBITS-1:0] & {{(`SIM_ADC_NBITS){1'b1}}, {(`FP_NBITS-`SIM_ADC_NBITS){1'b0}}};

        if (current2_in > `FP_MAX) current2 <= `FP_MAX;
        else if (current2_in < `FP_MIN) current2 <= `FP_MIN;
        else current2 <= current2_in[`FP_NBITS-1:0] & {{(`SIM_ADC_NBITS){1'b1}}, {(`FP_NBITS-`SIM_ADC_NBITS){1'b0}}};

        mag1_setpoint <= mag1_setpoint_in[`FP_NBITS-1:0];
        mag2_setpoint <= mag2_setpoint_in[`FP_NBITS-1:0];
        modulation <= modulation_in[`FP_NBITS-1:0];
    end

    reg signed [`FP_NBITS-1:0] mag1, phase1;
    reg signed [`FP_NBITS-1:0] mag2, phase2;

    wire sclk;
    reg [9:0] sclk_zline = 0; always @(posedge clk) sclk_zline <= {sclk_zline[8:0], sclk};
    wire sample_ready = sclk_zline[9];
    
    coil_pair_controller #(.DEADTIME_NTICKS(`SIM_DEADTIME_NTICKS)) controller_inst(
        .clk(clk),
        .rst(rst),
        .channel_enable(1),

        .mode(`MODE),
        .amplitude1(mag1_setpoint),
        .amplitude2(mag2_setpoint),
        .modulation(modulation),

        .clk_ticks_per_sample(clk_ticks_per_sample),
        .phase_step(phase_step),

        .sample_ready(sample_ready),
        .sample1(current1),
        .sample2(current2),
    
        .p_factor(`KP),
        .i_factor(`KI),

        .sclk(sclk),
        .pwm_ch1a(pwm_ch1a),
        .pwm_ch1b(pwm_ch1b),
        .pwm_ch1c(pwm_ch1c),
        .pwm_ch1d(pwm_ch1d),
    
        .pwm_ch2a(pwm_ch2a),
        .pwm_ch2b(pwm_ch2b),
        .pwm_ch2c(pwm_ch2c),
        .pwm_ch2d(pwm_ch2d),
    
        .mag1(mag1),
        .phase1(phase1),
        .mag2(mag2),
        .phase2(phase2),
        .mag_phase_ready()
    );
    
    assign mag1_out = mag1;
    assign mag2_out = mag2;
    assign phase1_out = phase1;
    assign phase2_out = phase2;
endmodule
