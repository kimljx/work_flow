@echo off
setlocal

set "ROOT=%~dp0"
set "PYTHON_EXE=%ROOT%runtime\python\python.exe"
set "SCRIPT_PATH=%ROOT%tools\backup_data.py"

if not exist "%PYTHON_EXE%" (
  echo 未检测到离线运行环境，请先执行 install_offline.bat。
  exit /b 1
)

"%PYTHON_EXE%" "%SCRIPT_PATH%" %*
exit /b %ERRORLEVEL%
