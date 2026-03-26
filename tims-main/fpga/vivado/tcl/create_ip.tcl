source tcl/config.tcl

create_project ip ./build/ip/proj -part $fpga_part -ip -force
update_ip_catalog -rebuild

# CLOCKING WIZARD: SYSCLK->FPGA_FCLK
create_ip -name clk_wiz -vendor xilinx.com -library ip -version 6.0 -module_name clk_wiz -dir ./build/ip -force
set_property -dict [list \
    CONFIG.CLKOUT1_REQUESTED_OUT_FREQ $fpga_fclk \
    CONFIG.CLK_OUT1_PORT {clk} \
    CONFIG.PRIMARY_PORT {sysclk} \
    CONFIG.PRIM_IN_FREQ $board_clk_freq \
    CONFIG.USE_LOCKED {false} \
    CONFIG.USE_RESET {false}
] [get_ips clk_wiz]

# create_ip -name vio -vendor xilinx.com -library ip -version 3.0 -module_name vio -dir ./build/ip -force
# set_property -dict [list \
#     CONFIG.C_NUM_PROBE_IN {0} \
#     CONFIG.C_NUM_PROBE_OUT {8} \
#     CONFIG.C_PROBE_OUT0_INIT_VAL {0x1} \
#     CONFIG.C_PROBE_OUT1_WIDTH $fp_nbits \
#     CONFIG.C_PROBE_OUT2_WIDTH [expr $fp_nbits+$fp_extra_bits] \
#     CONFIG.C_PROBE_OUT3_WIDTH $fp_nbits \
#     CONFIG.C_PROBE_OUT4_WIDTH $fp_nbits \
#     CONFIG.C_PROBE_OUT5_WIDTH $fp_nbits \
#     CONFIG.C_PROBE_OUT6_WIDTH $fp_nbits \
#     CONFIG.C_PROBE_OUT7_WIDTH $fp_nbits
# ] [get_ips vio]

# INTEGRATED LOGIC ANALYZER # CONFIG.C_PROBE2_WIDTH {16}
# create_ip -name ila -vendor xilinx.com -library ip -version 6.2 -module_name ila -dir ./build/ip -force
# set_property -dict [list \
#   CONFIG.C_DATA_DEPTH {16384} \
#   CONFIG.C_NUM_OF_PROBES {8} \
#   CONFIG.C_PROBE4_WIDTH $fp_nbits \
#   CONFIG.C_PROBE5_WIDTH $fp_nbits \
#   CONFIG.C_PROBE6_WIDTH $fp_nbits \
#   CONFIG.C_PROBE7_WIDTH $fp_nbits \
# ] [get_ips ila]

# # XADC
# create_ip -name xadc_wiz -vendor xilinx.com -library ip -version 3.3 -module_name xadc_wiz -dir ./build/ip -force
# set_property -dict [list \
#   CONFIG.DCLK_FREQUENCY ${MCLK_FREQ} \
#   CONFIG.ADC_CONVERSION_RATE {1000} \
#   CONFIG.ADC_OFFSET_AND_GAIN_CALIBRATION {true} \
#   CONFIG.ENABLE_CONVST {true} \
#   CONFIG.OT_ALARM {false} \
#   CONFIG.SINGLE_CHANNEL_SELECTION {VAUXP4_VAUXN4} \
#   CONFIG.TIMING_MODE {Event} \
#   CONFIG.USER_TEMP_ALARM {false} \
#   CONFIG.VCCAUX_ALARM {false} \
#   CONFIG.VCCINT_ALARM {false} \
# ] [get_ips xadc_wiz]
#

# synth all IPs
foreach ip_name [get_ips] {
  generate_target {instantiation_template} ${ip_name}
  create_ip_run ${ip_name}
  launch_runs ${ip_name}_synth_1
  wait_on_run ${ip_name}_synth_1
}
