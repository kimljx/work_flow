@echo off
setlocal
chcp 65001 >nul

set "ROOT=%~dp0"
set "PYTHON_EXE=%ROOT%runtime\python\python.exe"
set "SCRIPT_PATH=%ROOT%tools\install_offline.py"

if not exist "%PYTHON_EXE%" (
  echo 未找到内置 Python 运行时，请重新生成离线发布包。
  exit /b 1
)

if not exist "%SCRIPT_PATH%" (
  echo 未找到离线安装脚本，请重新生成离线发布包。
  exit /b 1
)

echo 正在执行离线初始化...
"%PYTHON_EXE%" "%SCRIPT_PATH%" %*
exit /b %ERRORLEVEL%
