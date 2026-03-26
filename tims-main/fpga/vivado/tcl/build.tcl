source tcl/config.tcl

create_project -force rtl ./build/rtl -part $fpga_part

set verilog_files [glob -directory .. -nocomplain -type f *.sv]

set mem_files [glob -directory ../memfiles -nocomplain -type f *.mem]

set xdc_files [glob -directory ./constraints -nocomplain -type f *]

set xci_files []
foreach subdir [glob -nocomplain -directory build/ip -type d *] { 
  set xci_files [concat $xci_files [glob -directory $subdir -nocomplain -type f *.xci]]
}

add_files $verilog_files
add_files $mem_files
add_files $xdc_files
read_ip $xci_files

set_property top main [current_fileset]
update_compile_order

launch_runs synth_1
wait_on_run synth_1

# set_property strategy Performance_ExtraTimingOpt [get_runs impl_1]
set_property strategy Performance_NetDelay_high [get_runs impl_1]
# set_property strategy Congestion_SpreadLogic_high [get_runs impl_1]
launch_runs impl_1
wait_on_run impl_1

open_run impl_1

write_bitstream -force ./bitstream/$project_name.bit
write_debug_probes -force ./bitstream/$project_name.ltx

