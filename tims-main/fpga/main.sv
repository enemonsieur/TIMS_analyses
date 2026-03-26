`timescale 1ns/1ps

`include "config.sv"

module main(
    input sysclk,
    output coil1_a, coil1_b, coil1_en1, coil1_c, coil1_d, coil1_en2,
    output coil2_a, coil2_b, coil2_en1, coil2_c, coil2_d, coil2_en2,
    output coil3_a, coil3_b, coil3_en1, coil3_c, coil3_d, coil3_en2,
    output coil4_a, coil4_b, coil4_en1, coil4_c, coil4_d, coil4_en2,

    input pi_cs, pi_sck, pi_mosi,
    output pi_trig, pi_miso,

    input remote_cs, remote_sck, remote_mosi,
    output remote_miso,

    output current_adc_sck,
    output current_adc_cs_a, current_adc_cs_b,
    input current1_adc_dout, current2_adc_dout,
    input current3_adc_dout, current4_adc_dout,

    input flow1, flow2, flow3, flow4,

    output pmod_1, pmod_2, pmod_3, pmod_4,
    output pmod_5, pmod_6, pmod_7, pmod_8
);    
    localparam Q = `FP_NBITS;
    localparam W = `INTERFACE_WORD_NBITS;
    localparam V = `INTERFACE_CONFIG_BIT_ALIGNMENT;

    // CLK GENERATION
    wire clk;
    clk_wiz clocking_wizard (.clk(clk), .sysclk(sysclk));
    
    // general control signals coming from the SPI interface
    reg system_enabled = 0, controller_enabled_a = 0, controller_enabled_b = 0;
    reg [Q-1:0] clk_ticks_per_sample_a = 100, clk_ticks_per_sample_b = 100;
    reg [Q+`FP_EXTRA_BITS-1:0] phase_step_a = 0, phase_step_b = 0;
    reg [Q-1:0] p_factor = 0, i_factor = 0;
    reg [Q-1:0] power1 = 0, power2 = 0, power3 = 0, power4 = 0; 
    reg [2:0] amplitude1_source, amplitude2_source;
    reg [2:0] amplitude3_source, amplitude4_source;
    reg [2:0] modulation_a_source, modulation_b_source;

    // desired current amplitude and modulation signals generated internally
    // and received over the SPI interface
    wire [Q-1:0] amplitude1, amplitude2;
    wire [Q-1:0] amplitude3, amplitude4;
    wire [Q-1:0] modulation_a, modulation_b;

    // remote analog inputs
    wire [Q-1:0] ain1, ain2;
    wire [Q-1:0] ain3, ain4;
    wire [Q-1:0] ain5, ain6;

    // desired current amplitude and modulation
    // these signals are wired to the internal or external sources depending
    // on configuration  
    reg [Q-1:0] setpoint_amplitude1_raw, setpoint_amplitude2_raw;
    reg [Q-1:0] setpoint_amplitude3_raw, setpoint_amplitude4_raw;
    reg [Q-1:0] setpoint_amplitude1, setpoint_amplitude2;
    reg [Q-1:0] setpoint_amplitude3, setpoint_amplitude4;
    reg [Q-1:0] setpoint_modulation_a, setpoint_modulation_b;

    // actual current magnitudes and phases
    wire [Q-1:0] mag1, phase1, mag2, phase2;
    wire [Q-1:0] mag3, phase3, mag4, phase4;
    wire [Q-1:0] actual_modulation_a, actual_modulation_b;
    wire [Q-1:0] ref_phase_a, ref_phase_b;
    wire mag_phase_ready_a, mag_phase_ready_b;
    
    // calculate actual TI modulation
    relative_phase_to_modulation relative_phase_to_modulation_inst_a(
        .clk(clk), .rst(rst), .input_ready(mag_phase_ready_a),
        .phase1(phase1), .phase2(phase2),
        .mag1(mag1), .mag2(mag2),
        .modulation(actual_modulation_a));
    relative_phase_to_modulation relative_phase_to_modulation_inst_b(
        .clk(clk), .rst(rst), .input_ready(mag_phase_ready_b),
        .phase1(phase3), .phase2(phase4),
        .mag1(mag3), .mag2(mag4),
        .modulation(actual_modulation_b)); 

    remote_io remote_io_inst(
        .clk(clk), 
        .cs(remote_cs), .sck(remote_sck), 
        .rx(remote_mosi), .tx(remote_miso),
        .ain1(ain1),
        .ain2(ain2),
        .ain3(ain3),
        .ain4(ain4),
        .ain5(ain5),
        .ain6(ain6),
        .aout1(actual_modulation_a),
        .aout2(actual_modulation_b)
    );

    // flow rate sensors
    wire [Q-1:0] flow1_out, flow2_out, flow3_out, flow4_out;
    flow_sensor flow_sensor_inst1(.clk(clk), .signal(flow1), .out(flow1_out));
    flow_sensor flow_sensor_inst2(.clk(clk), .signal(flow2), .out(flow2_out));
    flow_sensor flow_sensor_inst3(.clk(clk), .signal(flow3), .out(flow3_out));
    flow_sensor flow_sensor_inst4(.clk(clk), .signal(flow4), .out(flow4_out));
    
    // SPI interface
    wire [W-1:0] monitor_data, setpoint_data;
    wire [W-1:0] config0, config1, config2, config3;
    wire [W-1:0] status0, status1, status2, status3;
    spi_interface spi_interface_inst(
        .clk(clk), .cs(pi_cs), .sck(pi_sck), .rx(pi_mosi), .tx(pi_miso), .trig(pi_trig),
        .status0(status0), .status1(status1), .status2(status2), .status3(status3),
        .monitor_data(monitor_data),
        .config0(config0), .config1(config1), .config2(config2), .config3(config3),
        .setpoint_data(setpoint_data)
    );
 
    // apply configuration received from spi only if data is valid
    reg spi_data_valid = 0;
    always @(posedge clk) begin
        spi_data_valid <= config0 == `INTERFACE_PACKET_VALID_KEY;
        
        if (spi_data_valid) begin
            system_enabled          <= config1[7*V+`SYSTEM_ENABLE_BIT];
            controller_enabled_a    <= config1[7*V+`CHA_CONTROLLER_ENABLE_BIT];
            controller_enabled_b    <= config1[7*V+`CHB_CONTROLLER_ENABLE_BIT];
            clk_ticks_per_sample_a  <= config1[6*V+Q-1:6*V];
            clk_ticks_per_sample_b  <= config1[5*V+Q-1:5*V];
            phase_step_a            <= config1[4*V+Q+`FP_EXTRA_BITS-1:4*V];
            phase_step_b            <= config1[3*V+Q+`FP_EXTRA_BITS-1:3*V];
            p_factor                <= config1[2*V+Q-1:2*V];
            i_factor                <= config1[1*V+Q-1:1*V]; 

            power1                  <= config2[7*V+Q-1:7*V];
            power2                  <= config2[6*V+Q-1:6*V]; 
            power3                  <= config2[5*V+Q-1:5*V];
            power4                  <= config2[4*V+Q-1:4*V]; 

            amplitude1_source       <= config3[7*V+2:7*V];
            amplitude2_source       <= config3[6*V+2:6*V]; 
            amplitude3_source       <= config3[5*V+2:5*V];
            amplitude4_source       <= config3[4*V+2:4*V]; 
            modulation_a_source     <= config3[3*V+2:3*V]; 
            modulation_b_source     <= config3[2*V+2:2*V]; 
        end
        else begin
            system_enabled <= 0;
            controller_enabled_a <= 0;
            controller_enabled_b <= 0;
        end 
    end
    
    // unpack setpoint data
    assign amplitude1   = setpoint_data[16*Q-1:15*Q];
    assign amplitude2   = setpoint_data[15*Q-1:14*Q];
    assign amplitude3   = setpoint_data[14*Q-1:13*Q];
    assign amplitude4   = setpoint_data[13*Q-1:12*Q];
    assign modulation_a = setpoint_data[12*Q-1:11*Q];
    assign modulation_b = setpoint_data[11*Q-1:10*Q]; 

    // pack monitor data
    assign monitor_data[16*Q-1:15*Q] = actual_modulation_a;
    assign monitor_data[15*Q-1:14*Q] = setpoint_modulation_a;
    assign monitor_data[14*Q-1:13*Q] = mag1;
    assign monitor_data[13*Q-1:12*Q] = setpoint_amplitude1;
    assign monitor_data[12*Q-1:11*Q] = mag2;
    assign monitor_data[11*Q-1:10*Q] = setpoint_amplitude2;
    assign monitor_data[10*Q-1:09*Q] = actual_modulation_b;
    assign monitor_data[09*Q-1:08*Q] = setpoint_modulation_b;
    assign monitor_data[08*Q-1:07*Q] = mag3;
    assign monitor_data[07*Q-1:06*Q] = setpoint_amplitude3;
    assign monitor_data[06*Q-1:05*Q] = mag4;
    assign monitor_data[05*Q-1:04*Q] = setpoint_amplitude4;
    assign monitor_data[04*Q-1:03*Q] = flow1 << 14;
    assign monitor_data[03*Q-1:02*Q] = flow2 << 14;
    assign monitor_data[02*Q-1:01*Q] = flow3 << 14;
    assign monitor_data[01*Q-1:00*Q] = flow4 << 14;

    // pack status0 data
    assign status0 = `INTERFACE_PACKET_VALID_KEY;

    // pack status1 data
    assign status1[7*V+Q-1:7*V] = flow1_out;
    assign status1[6*V+Q-1:6*V] = flow2_out;
    assign status1[5*V+Q-1:5*V] = flow3_out;
    assign status1[4*V+Q-1:4*V] = flow4_out;

    // rst signal for all FPGA logic except SPI interfance 
    wire rst;
    assign rst = !system_enabled;

    // mux to select the setpoint signals
    mux_3bit sp_mux_inst1(
        .clk(clk), .rst(rst), .control(amplitude1_source), .in0(amplitude1), .out(setpoint_amplitude1_raw),
        .in1(ain1), .in2(ain2), .in3(ain3), .in4(ain4), .in5(ain5), .in6(ain6), .in7(0));
    mux_3bit sp_mux_inst2(
        .clk(clk), .rst(rst), .control(amplitude2_source), .in0(amplitude2), .out(setpoint_amplitude2_raw),
        .in1(ain1), .in2(ain2), .in3(ain3), .in4(ain4), .in5(ain5), .in6(ain6), .in7(0));
    mux_3bit sp_mux_inst3(
        .clk(clk), .rst(rst), .control(amplitude3_source), .in0(amplitude3), .out(setpoint_amplitude3_raw),
        .in1(ain1), .in2(ain2), .in3(ain3), .in4(ain4), .in5(ain5), .in6(ain6), .in7(0));
    mux_3bit sp_mux_inst4(
        .clk(clk), .rst(rst), .control(amplitude4_source), .in0(amplitude4), .out(setpoint_amplitude4_raw),
        .in1(ain1), .in2(ain2), .in3(ain3), .in4(ain4), .in5(ain5), .in6(ain6), .in7(0));
    mux_3bit sp_mux_inst5(
        .clk(clk), .rst(rst), .control(modulation_a_source), .in0(modulation_a), .out(setpoint_modulation_a),
        .in1(ain1), .in2(ain2), .in3(ain3), .in4(ain4), .in5(ain5), .in6(ain6), .in7(0));
    mux_3bit sp_mux_inst6(
        .clk(clk), .rst(rst), .control(modulation_b_source), .in0(modulation_b), .out(setpoint_modulation_b),
        .in1(ain1), .in2(ain2), .in3(ain3), .in4(ain4), .in5(ain5), .in6(ain6), .in7(0));


    // scale amplitude setpoints according to selected power level
    multiplier pwr_mult_inst1(.clk(clk), .rst(rst), .x(setpoint_amplitude1_raw), .y(power1), .out(setpoint_amplitude1));
    multiplier pwr_mult_inst2(.clk(clk), .rst(rst), .x(setpoint_amplitude2_raw), .y(power2), .out(setpoint_amplitude2));
    multiplier pwr_mult_inst3(.clk(clk), .rst(rst), .x(setpoint_amplitude3_raw), .y(power3), .out(setpoint_amplitude3));
    multiplier pwr_mult_inst4(.clk(clk), .rst(rst), .x(setpoint_amplitude4_raw), .y(power4), .out(setpoint_amplitude4));

    wire sclk_a, sample_ready_a;
    wire sclk_b, sample_ready_b;
    wire [`FP_NBITS-1:0] sample1, sample2, sample3, sample4;
    
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

    wire driver_needed_ch1, driver_needed_ch2;
    coil_pair_controller controller_inst1(
        .clk(clk),
        .rst(rst),
        .channel_enable(controller_enabled_a),

        .amplitude1(setpoint_amplitude1),
        .amplitude2(setpoint_amplitude2),
        .modulation(setpoint_modulation_a),
        .clk_ticks_per_sample(clk_ticks_per_sample_a),
        .phase_step(phase_step_a),

        .sample_ready(sample_ready_a),
        .sample1(sample1),
        .sample2(sample2),
    
        .p_factor(p_factor),
        .i_factor(i_factor),

        .sclk(sclk_a),
        .pwm_ch1a(coil1_a),
        .pwm_ch1b(coil1_b),
        .pwm_ch1c(coil1_c),
        .pwm_ch1d(coil1_d),
        .driver_needed_ch1(driver_needed_ch1),
    
        .pwm_ch2a(coil2_a),
        .pwm_ch2b(coil2_b),
        .pwm_ch2c(coil2_c),
        .pwm_ch2d(coil2_d),
        .driver_needed_ch2(driver_needed_ch2),
    
        .mag1(mag1),
        .phase1(phase1),
        .mag2(mag2),
        .phase2(phase2),
        .mag_phase_ready(mag_phase_ready_a)
    );
        
    wire driver_needed_ch3, driver_needed_ch4;
    coil_pair_controller controller_inst2(
        .clk(clk),
        .rst(rst),
        .channel_enable(controller_enabled_b),

        .amplitude1(setpoint_amplitude3),
        .amplitude2(setpoint_amplitude4),
        .modulation(setpoint_modulation_b),
        .clk_ticks_per_sample(clk_ticks_per_sample_b),
        .phase_step(phase_step_b),

        .sample_ready(sample_ready_b),
        .sample1(sample3),
        .sample2(sample4),
    
        .p_factor(p_factor),
        .i_factor(i_factor),

        .sclk(sclk_b),
        .pwm_ch1a(coil3_a),
        .pwm_ch1b(coil3_b),
        .pwm_ch1c(coil3_c),
        .pwm_ch1d(coil3_d),
        .driver_needed_ch1(driver_needed_ch3),
    
        .pwm_ch2a(coil4_a),
        .pwm_ch2b(coil4_b),
        .pwm_ch2c(coil4_c),
        .pwm_ch2d(coil4_d),
        .driver_needed_ch2(driver_needed_ch4),
    
        .mag1(mag3),
        .phase1(phase3),
        .mag2(mag4),
        .phase2(phase4),
        .mag_phase_ready(mag_phase_ready_b)
    );

    // ila ila_inst (
    //     .clk(clk), // input wire clk
    //     .probe0(remote_cs), // input wire [0:0]  probe0  
    //     .probe1(remote_mosi), // input wire [0:0]  probe1 
    //     .probe2(remote_miso), // input wire [0:0]  probe2 
    //     .probe3(remote_sck), // input wire [0:0]  probe3 
    //     .probe4(remote_amplitude1), // input wire [15:0]  probe4 
    //     .probe5(remote_amplitude2), // input wire [15:0]  probe5 
    //     .probe6(remote_amplitude3), // input wire [15:0]  probe6 
    //     .probe7(remote_amplitude4) // input wire [15:0]  probe7
    // );

    assign coil1_en1 = driver_needed_ch1 & controller_enabled_a;
    assign coil1_en2 = driver_needed_ch1 & controller_enabled_a;
    assign coil2_en1 = driver_needed_ch2 & controller_enabled_a;
    assign coil2_en2 = driver_needed_ch2 & controller_enabled_a;
    assign coil3_en1 = driver_needed_ch3 & controller_enabled_b;
    assign coil3_en2 = driver_needed_ch3 & controller_enabled_b;
    assign coil4_en1 = driver_needed_ch4 & controller_enabled_b;
    assign coil4_en2 = driver_needed_ch4 & controller_enabled_b;

    assign pmod_1 = remote_cs;
    assign pmod_2 = remote_sck;
    assign pmod_3 = remote_mosi;
    assign pmod_4 = remote_miso;
endmodule
