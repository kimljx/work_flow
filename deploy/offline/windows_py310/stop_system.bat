@echo off
setlocal
chcp 65001 >nul

set "SILENT=%~1"

echo 正在停止工作流系统服务...
taskkill /FI "WINDOWTITLE eq 工作流系统服务*" /T /F >nul 2>nul

if errorlevel 1 (
  echo 未找到正在运行的“工作流系统服务”窗口。
) else (
  echo 服务已停止。
)

if /I not "%SILENT%"=="/silent" pause
