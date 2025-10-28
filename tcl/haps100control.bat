@echo off
chcp 65001 >nul 2>&1  :: Force UTF-8 encoding (no Chinese support)
setlocal enabledelayedexpansion

REM Define default values
SET DEFAULT_XACTORSCMD="C:\Synopsys\protocomp-rtV-2024.09\bin\xactorscmd.bat"
SET DEFAULT_TCL_SCRIPT="tcl\reset.tcl"

REM Receive parameters if provided
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

REM Check if xactorscmd exists
if not exist %XACTORSCMD% (
    echo Error: xactorscmd.bat not found - %XACTORSCMD%
    pause
    exit /b 1
)

REM Check if TCL script exists
if not exist %TCL_SCRIPT% (
    echo Error: TCL script not found - %TCL_SCRIPT%
    pause
    exit /b 1
)

REM Create temporary command file
set CMD_FILE=%temp%\haps_commands.txt
echo confprosh %TCL_SCRIPT% > "%CMD_FILE%"
echo exit >> "%CMD_FILE%" 

REM Execute xactorscmd with the command file
cmd /c "%XACTORSCMD% < "%CMD_FILE%""

REM Capture return code
set RETURN_CODE=%errorlevel%

REM Cleanup temporary file
del /f /q "%CMD_FILE%" >nul 2>&1

exit /b %RETURN_CODE%

endlocal