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

# 定义 hmf.txt 的内容模板，使用获取到的 HAPS_SERIAL 替换 serial 字段
set hmf_content "{
\"tsdmaphaps\": {
\"FB1\": {\"serial\": \"$HAPS_SERIAL\"}
}
}"

# 在当前目录创建并写入 hmf.txt
set hmf_file [open "hmf.txt" w]  ;# 以写入模式打开文件（若存在则覆盖）
puts $hmf_file $hmf_content     ;# 将内容写入文件
close $hmf_file                 ;# 关闭文件
puts "================================="
puts "gen hmf.txt："
puts $hmf_content               ;# 打印生成的内容
puts "================================="

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
	#method 2, open handler according to HMF file(HMF file can imply HAPS level or FPGA level)
	#puts [cfg_open "" -map hmf.txt]
	puts "Firmware Version is:"
	puts [cfg_status_get_firmware_version $handle]
	puts "================================="
	puts "Get haps FPGA temp:"
	puts "FPGA_A temperature : [cfg_temp_get $handle {FB1_A}]"
	puts "FPGA_B temperature : [cfg_temp_get $handle {FB1_B}]"
	puts "FPGA_C temperature : [cfg_temp_get $handle {FB1_C}]"
	puts "FPGA_D temperature : [cfg_temp_get $handle {FB1_D}]"
	puts "================================="
	puts "Clear previous FPGA images"
	cfg_project_clear $handle
	puts "================================="
	puts "System Serial Number is:"
	puts [cfg_status_get_serial_number $handle]
	puts "================================="
	set FPGA_BOARD [cfg_status_get_fpga_boards $handle]
	puts "FPGA Board nane is: $FPGA_BOARD"
	set FPGA_BOARD_TYPE [cfg_status_get_board_type $handle $FPGA_BOARD]
	puts "FPGA Board TYPE is: $FPGA_BOARD_TYPE"
	set FPGA_USER_NAME [cfg_status_get_user_fpgas $handle]
	puts "FPGA User Name is: $FPGA_USER_NAME"
	
	puts ""
	puts "Starting to Configue HAPS with project -> $CFG_PRJ_NAME"
	puts [cfg_project_configure $handle $CFG_PRJ_NAME]
	foreach fpga $FPGA_USER_NAME {
		if {[ cfg_status_get_done $handle $fpga]} {
			puts "$fpga cfg Done!"
		} else {
			puts "$fpga NOT configured!"
		}
	}
	puts "Close Handler......"
	cfg_close $handle
	
	puts "Start HSTDM Training......"
	#doing HSTDM training, you must have "package require proto_rt", and hmf.txt file
	proto_rt::run_ipinfra -hmf hmf.txt -train all
	proto_rt::run_ipinfra -hmf hmf.txt -report_global_status all
	#proto_rt::run_ipinfra -hmf hmf.txt -report_verbose all
	#Re-open handle to enable clock and issue reset
	puts "HSTDM Training Done...."
	puts "getting Handler......"
	puts [cfg_open $HAPS_DEVICE]
	#  puts [cfg_project_configure $handle $CFG_PRJ_NAME -none -clockenable]
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