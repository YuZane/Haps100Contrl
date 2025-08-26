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
}
puts "Starting to connect HAPS HW"
puts "================================="
puts "getting Handler"
#method 1, directly open handler
puts "Select HAPS $HAPS_DEVICE"
set HAPS_HANDLE [cfg_open $HAPS_DEVICE]


