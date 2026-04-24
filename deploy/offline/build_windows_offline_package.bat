@echo off
setlocal
chcp 65001 >nul

cd /d %~dp0\..\..
py -3.11 deploy\offline\build_windows_offline_package.py

if errorlevel 1 (
  echo 离线发布包构建失败。
  pause
  exit /b 1
)

echo 离线发布包构建完成。
pause
