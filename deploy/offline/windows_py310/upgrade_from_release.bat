@echo off
setlocal
chcp 65001 >nul

set "NEW_ROOT=%~dp0"
set "OLD_ROOT=%~1"

if "%OLD_ROOT%"=="" (
  set /p OLD_ROOT=请输入旧版发布包目录完整路径：
)

if "%OLD_ROOT%"=="" (
  echo 未输入旧版发布包目录，已取消升级。
  exit /b 1
)

if not exist "%OLD_ROOT%\backup_data.bat" (
  echo 旧版目录无效，未找到 backup_data.bat。
  exit /b 1
)

if not exist "%OLD_ROOT%\stop_system.bat" (
  echo 旧版目录无效，未找到 stop_system.bat。
  exit /b 1
)

echo.
echo [1/6] 停止旧版服务
call "%OLD_ROOT%\stop_system.bat" /silent

echo [2/6] 备份旧版数据
call "%OLD_ROOT%\backup_data.bat"
if errorlevel 1 (
  echo 旧版数据备份失败，升级已中止。
  exit /b 1
)

set "LATEST_BACKUP="
for /f "delims=" %%i in ('dir /b /ad /o-n "%OLD_ROOT%\backup" ^| findstr /v /b "_restore_guard_"') do (
  if not defined LATEST_BACKUP set "LATEST_BACKUP=%%i"
)

if not defined LATEST_BACKUP (
  echo 未找到旧版备份目录，升级已中止。
  exit /b 1
)

echo [3/6] 初始化新版环境
call "%NEW_ROOT%\install_offline.bat" /silent
if errorlevel 1 (
  echo 新版环境初始化失败，升级已中止。
  exit /b 1
)

echo [4/6] 复制备份数据到新版目录
if not exist "%NEW_ROOT%\backup" mkdir "%NEW_ROOT%\backup"
xcopy "%OLD_ROOT%\backup\%LATEST_BACKUP%" "%NEW_ROOT%\backup\%LATEST_BACKUP%\" /E /I /Y >nul
if errorlevel 1 (
  echo 复制备份目录失败，升级已中止。
  exit /b 1
)

echo [5/6] 恢复备份到新版
echo YES| call "%NEW_ROOT%\restore_data.bat" %LATEST_BACKUP%
if errorlevel 1 (
  echo 新版恢复失败，升级已中止。
  exit /b 1
)

echo [6/6] 启动新版服务
call "%NEW_ROOT%\start_system.bat"

echo.
echo 升级完成。
echo 已从旧版目录导入备份批次：%LATEST_BACKUP%
exit /b 0
