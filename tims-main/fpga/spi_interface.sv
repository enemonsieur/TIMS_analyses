/*
    Module: spi_interface
    Description: Interface module that allows the FPGA to be controlled and monitored over SPI
    
    Monitor data coming from the FPGA are input to the interface and sent over SPI, while 
    setpoint data received over SPI are output from the interface into the rest of the FPGA.

    Monitor and setpoint data are bit arrays of INTERFACE_WORD_NBITS size. They are sampled at
    a rate of INTERFACE_SAMPLING_RATE.

    Additionally, a number of status words in received as input to the interface and sent over 
    SPI, while the same number of config words are received from SPI and output to the rest of the 
    FPGA.
    
    Status and config data are sampled at a lower rate of INTERFACE_SAMPLING_RATE/INTERFACE_DATA_NUM_SAMPLES. 

    A communication packet is exchanged once every INTERFACE_DATA_NUM_SAMPLES/INTERFACE_SAMPLING_RATE 
    seconds. Packet exchange to be triggered by rising edge of the trig signal. Incoming packets
    are expected to contain config and setpoint data, while outgoing packets contain status and 
    monitor data.
*/

`timescale 1ns/1ps

`include "config.sv"

module spi_interface (
    input clk,

    // SPI lines
    input cs,
    input sck,
    input rx,
    output tx,
    output reg trig,

    // status input words
    input [`INTERFACE_WORD_NBITS-1:0] status0,
    input [`INTERFACE_WORD_NBITS-1:0] status1,
    input [`INTERFACE_WORD_NBITS-1:0] status2,
    input [`INTERFACE_WORD_NBITS-1:0] status3,
    
    // monitor input data
    input [`INTERFACE_WORD_NBITS-1:0] monitor_data,

    // configuration output words
    output reg [`INTERFACE_WORD_NBITS-1:0] config0,
    output reg [`INTERFACE_WORD_NBITS-1:0] config1,
    output reg [`INTERFACE_WORD_NBITS-1:0] config2,
    output reg [`INTERFACE_WORD_NBITS-1:0] config3,

    // setpoint output data
    output reg [`INTERFACE_WORD_NBITS-1:0] setpoint_data
);
    // parameter shorthands
    localparam W = `INTERFACE_WORD_NBITS;
    localparam N = `INTERFACE_DATA_NUM_SAMPLES;
    localparam C = `INTERFACE_CONFIG_NUM_WORDS;

    localparam BRAM_ADDRESS_NBITS = $rtoi($ceil($clog2(N)));
    reg [BRAM_ADDRESS_NBITS-1:0] addra0 = 0, addrb0 = 0, addra1 = 0, addrb1 = 0;
    reg [W-1:0] dia0 = 0, dib0 = 0, dia1 = 0, dib1 = 0;
    wire [W-1:0] doa0, dob0, doa1, dob1;
    reg wea0 = 0, web0 = 0, wea1 = 0, web1 = 0;
    
    bram_dual_port #(.WIDTH(W), .DEPTH(N)) bram_inst_0(clk, clk, 1, 1, wea0, web0, addra0, addrb0, dia0, dib0, doa0, dob0);
    bram_dual_port #(.WIDTH(W), .DEPTH(N)) bram_inst_1(clk, clk, 1, 1, wea1, web1, addra1, addrb1, dia1, dib1, doa1, dob1);
    
    initial begin
        config0 = 0; config1 = 0; config2 = 0; config3 = 0;
        setpoint_data = 0;
    end
    
    // indicates whether data is currently being written into / read from BRAM 0 or 1
    // 0: reading and writing from BRAM 0; SPI data transfer from BRAM 1
    // 1: reading and writing from BRAM 0; SPI data transfer from BRAM 1
    reg current_buffer = 0;

    // counter to count clk ticks between samples
    localparam SAMPLING_COUNTER_NBITS = $rtoi($ceil($clog2(`FPGA_FCLK / `INTERFACE_SAMPLING_RATE)));
    localparam bit [SAMPLING_COUNTER_NBITS-1:0] SAMPLING_PERIOD =
        SAMPLING_COUNTER_NBITS'(`FPGA_FCLK / `INTERFACE_SAMPLING_RATE);
    reg [SAMPLING_COUNTER_NBITS-1:0] sampling_counter = 0;
    reg sampling_clk = 0, sampling_clk_z = 0;
    always @(posedge clk) begin
        sampling_counter <= (sampling_counter == SAMPLING_PERIOD-1)? 0 : sampling_counter + 1;
        sampling_clk <= (sampling_counter > SAMPLING_PERIOD/2);
        sampling_clk_z <= sampling_clk;
    end
        
    reg [W-1:0] monitor_packed_sample, setpoint_packed_sample;

    reg[3:0] sampling_pipeline_index = 0;
    reg sampling_pipeline_active = 0;
    
    // counter to count number of samples taken in the current buffer
    reg [BRAM_ADDRESS_NBITS-1:0] sample_index = 0;

    always @(posedge clk) begin
        if (sampling_clk && !sampling_clk_z) begin
            sampling_pipeline_index <= 0;
            sampling_pipeline_active <= 1;
        end
        else begin
            if (sampling_pipeline_active) begin
                sampling_pipeline_index <= sampling_pipeline_index + 1;
                
                if (sampling_pipeline_index == 0) begin
                    // read setpoint data from BRAM
                    if (current_buffer == 0) begin
                        wea0 <= 0;
                        addra0 <= sample_index;
                    end
                    else begin
                        wea1 <= 0;
                        addra1 <= sample_index;
                    end
                end
                else if (sampling_pipeline_index == 2) begin
                    // store setpoint data in register
                    if (current_buffer == 0)
                        setpoint_packed_sample <= doa0;
                    else
                        setpoint_packed_sample <= doa1;
                end
                else if (sampling_pipeline_index == 3) begin
                    // output setpoint data
                    setpoint_data <= setpoint_packed_sample;

                    // latch monitor data
                    monitor_packed_sample <= monitor_data;
                end
                else if (sampling_pipeline_index == 4) begin
                    // store monitor data in BRAM
                    if (current_buffer == 0) begin
                        wea0 <= 1;
                        addra0 <= sample_index;
                        dia0 <= monitor_packed_sample;
                    end
                    else begin
                        wea1 <= 1;
                        addra1 <= sample_index;
                        dia1 <= monitor_packed_sample;
                    end
                end
                else if (sampling_pipeline_index == 5) begin
                    sampling_pipeline_active <= 0; // last step

                    // disable BRAM writing
                    wea0 <= 0;
                    wea1 <= 0;
                    
                    // update sample_index
                    if (sample_index == N-1) begin
                        sample_index <= 0;
                        current_buffer <= !current_buffer; // swap buffers
                    end
                    else begin
                        sample_index <= sample_index + 1;
                    end
                end
            end
        end
    end

    wire spi_data_out_ready;
    reg spi_data_in_ready = 0;
    reg [W-1:0] spi_data_in;
    wire [W-1:0] spi_data_out;
    spi_receiver #(.WORD_NBITS(W)) spi_receiver_inst (
        .clk(clk), .sck(sck), .rx(rx), .cs(cs), .tx(tx),
        .data_in_ready(spi_data_in_ready), .data_out_ready(spi_data_out_ready),
        .data_in(spi_data_in), .data_out(spi_data_out)
    );

    // generate data transfer trigger signal
    reg trig_z = 0;
    always @(posedge clk) begin
        trig <= (sample_index < N/2); // rising edge when N samples are done
        trig_z <= trig; // delay to detect rising edges
    end
    
    // counter to count number of words received from SPI so far
    localparam WORD_INDEX_NBITS = $rtoi($ceil($clog2(N+C)));
    reg [WORD_INDEX_NBITS:0] rx_word_index = 0, tx_word_index;

    // delay to detect rising edges of spi_data_ready
    reg spi_data_out_ready_z = 0;
    always @(posedge clk) spi_data_out_ready_z <= spi_data_out_ready;

    reg packet_valid = 0;

    reg processing_spi_data_out = 0;
    reg preparing_spi_data_in = 0;

    reg [3:0] spi_input_pipeline_index = 0;
    
    always @(posedge clk) begin
        if (trig && !trig_z) begin
            rx_word_index <= 0;
            tx_word_index <= 0;
            preparing_spi_data_in <= 1;
            spi_input_pipeline_index <= 0;
        end
        else if (spi_data_out_ready && !spi_data_out_ready_z) begin
            preparing_spi_data_in <= 1;

            processing_spi_data_out <= 1;
            spi_input_pipeline_index <= 0;
        end
        else begin
            if (preparing_spi_data_in) begin
                spi_input_pipeline_index <= spi_input_pipeline_index + 1;
                
                if (spi_input_pipeline_index == 0) begin
                    tx_word_index <= tx_word_index + 1;
                    
                    if (tx_word_index < N) begin // data word
                        // request monitor data from BRAM
                        if (current_buffer == 0) begin
                            web1 <= 0;
                            addrb1 <= tx_word_index;
                        end
                        else begin
                            web0 <= 0;
                            addrb0 <= tx_word_index;
                        end
                    end
                    else if (tx_word_index == N) begin
                        // first status word
                        spi_data_in <= status0;
                        spi_data_in_ready <= 1;
                        preparing_spi_data_in <= 0;
                    end
                    else if (tx_word_index == N+1) begin
                        // second status word
                        spi_data_in <= status1;
                        spi_data_in_ready <= 1;
                        preparing_spi_data_in <= 0;
                    end
                    else if (tx_word_index == N+2) begin
                        // third status word
                        spi_data_in <= status2;
                        spi_data_in_ready <= 1;
                        preparing_spi_data_in <= 0;
                    end
                    else if (tx_word_index == N+3) begin
                        // fourth status word
                        spi_data_in <= status3;
                        spi_data_in_ready <= 1;
                        preparing_spi_data_in <= 0;
                    end
                    else begin
                        preparing_spi_data_in <= 0;
                    end
                end
                else if (spi_input_pipeline_index == 2) begin
                    // retrieve monitor data from BRAM
                    if (current_buffer == 0)
                        spi_data_in <= dob1;
                    else
                        spi_data_in <= dob0;

                    spi_data_in_ready <= 1;

                    preparing_spi_data_in <= 0;
                end
            end
            else begin
                spi_data_in_ready <= 0;
            end

            if (processing_spi_data_out && !preparing_spi_data_in) begin
                processing_spi_data_out <= 0;
                rx_word_index <= rx_word_index + 1;
                
                if (rx_word_index < N) begin // data word
                    if (current_buffer == 0) begin
                        web1 <= 1;
                        addrb1 <= rx_word_index;
                        dib1 <= spi_data_out;
                    end
                    else begin
                        web0 <= 1;
                        addrb0 <= rx_word_index;
                        dib0 <= spi_data_out;
                    end
                end
                else if (rx_word_index == N + 0) begin
                    // output first config word
                    config0 <= spi_data_out;
                end
                else if (rx_word_index == N + 1) begin
                    // output second config word
                    config1 <= spi_data_out;
                end
                else if (rx_word_index == N + 2) begin
                    // output second config word
                    config2 <= spi_data_out;
                end
                else if (rx_word_index == N + 3) begin
                    // output second config word
                    config3 <= spi_data_out;
                end
            end
            else begin
                // disable BRAM writing
                web0 <= 0;
                web1 <= 0;
            end
        end
    end
    
endmodule
    
