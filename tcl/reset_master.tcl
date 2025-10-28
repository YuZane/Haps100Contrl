package require proto_rt

#Get tsd file path parameter
set CFG_PRJ_NAME system/targetsystem.tsd
if { $argc > 1} {
	set CFG_PRJ_NAME [lindex $argv 1]
}
puts "================================="
puts "tsd file path is $CFG_PRJ_NAME "
puts "================================="

puts "Scaning HW attached"
puts "================================="
set HAPS_SCAN [cfg_scan]
puts $HAPS_SCAN
array set HAPS_STATUS [lindex $HAPS_SCAN 0]

# 从数组中获取DEVICE和SERIAL的值
set HAPS_DEVICE [lindex [array get HAPS_STATUS DEVICE] 1]
set HAPS_SERIAL [lindex [array get HAPS_STATUS SERIAL] 1]
puts "HAPS_DEVICE:$HAPS_DEVICE"
puts "HAPS_SERIAL:$HAPS_SERIAL"

if { [array get HAPS_STATUS STATE] != "STATE available" } {
	puts [array get HAPS_STATUS STATE]
	exit
} else {
	puts "Starting to connect HAPS HW"
	puts "================================="
	puts "getting Handler"
	#method 1, directly open handler
	puts "Select HAPS $HAPS_DEVICE"
	set handle [cfg_open $HAPS_DEVICE]
	puts $handle

	#release reset
	puts "release reset......"
	cfg_reset_set $handle FB1.uA 0
	cfg_reset_set $handle FB1.uA 1
	cfg_close $handle
}
#
##cfg_reset_set/cfg_reset_pulse/cfg_reset_toggle
##cfg_status_get_done $handle
##cfg_config_clear $handle FB5.uA
##cfg_config_get_fpga_id $handle FB5.uA
##cfg_config_data $handle FB5.Ua ./FB5.uA.bit
##cfg_project_clear $handle
##cfg_clock_set_frequency $handle $FPGA_BOARD ${FPGA_BOARD}.PLL1.CLK1 25M 
##cfg_clock_set_pll_enable $handle $FPGA_BOARD  ${FPGA_BOARD}.PLL1 1
##puts [cfg_clock_get_pll_enable $handle $FPGA_BOARD  ${FPGA_BOARD}.PLL1]
##cfg_clock_set_frequency $handle $FPGA_BOARD ${FPGA_BOARD}.PLL1.CLK1 10M 
##puts [cfg_clock_get_frequency $handle $FPGA_BOARD ${FPGA_BOARD}.PLL1.CLK1]
##cfg_clock_set_enable $handle $FPGA_BOARD  ${FPGA_BOARD}.PLL1.CLK1 1
##puts [cfg_clock_get_enable $handle $FPGA_BOARD  ${FPGA_BOARD}.PLL1.CLK1]
##Generating verbose reports:
##proto_rt::run_ipinfra -hmf hmf_file.hmf -report_verbose all
##proto_rt::run_ipinfra -hmf hmf_file.hmf -report_verbose all -file report.txt
##Generating reports:
##proto_rt::run_ipinfra -hmf hmf_file.hmf -report all
##proto_rt::run_ipinfra -hmf hmf_file.hmf -report all -file report.txt