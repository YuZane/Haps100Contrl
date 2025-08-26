@echo off
setlocal enabledelayedexpansion

REM 定义默认值
SET DEFAULT_XACTORSCMD="C:\Synopsys\protocomp-rtV-2024.09\bin\xactorscmd.bat"
SET DEFAULT_TCL_SCRIPT="tcl\reset.tcl"

REM 接收参数（如果有传递）
REM 第一个参数：xactorscmd.bat路径
REM 第二个参数：TCL脚本路径
if not "%~1"=="" (
    SET XACTORSCMD="%~1"
) else (
    SET XACTORSCMD=%DEFAULT_XACTORSCMD%
)

if not "%~2"=="" (
    SET TCL_SCRIPT="%~2"
) else (
    SET TCL_SCRIPT=%DEFAULT_TCL_SCRIPT%
)

REM 检查xactorscmd是否存在
if not exist %XACTORSCMD% (
    echo 错误：未找到xactorscmd.bat - %XACTORSCMD%
    pause
    exit /b 1
)

REM 检查TCL脚本是否存在
if not exist %TCL_SCRIPT% (
    echo 错误：未找到TCL脚本 - %TCL_SCRIPT%
    pause
    exit /b 1
)

REM 创建临时命令文件，包含要执行的confprosh命令
set CMD_FILE=%temp%\haps_commands.txt
echo confprosh %TCL_SCRIPT% > "%CMD_FILE%"
echo exit >> "%CMD_FILE%" 

REM 启动xactorscmd.bat，并将临时命令文件作为输入注入
REM 使用/c参数确保执行后自动退出
cmd /c "%XACTORSCMD% < "%CMD_FILE%""

REM 记录返回代码
set RETURN_CODE=%errorlevel%

REM 清理临时文件
del /f /q "%CMD_FILE%" >nul 2>&1

exit /b %RETURN_CODE%

endlocal