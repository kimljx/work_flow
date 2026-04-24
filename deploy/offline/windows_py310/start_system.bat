@echo off
setlocal
chcp 65001 >nul

set "ROOT=%~dp0"
set "APP_ROOT=%ROOT%app"
set "PYTHON_EXE=%ROOT%runtime\python\python.exe"

if not exist "%PYTHON_EXE%" (
  echo 未找到内置 Python 运行时，请先执行 install_offline.bat。
  exit /b 1
)

if not exist "%APP_ROOT%\.env" (
  copy /Y "%ROOT%config\.env.offline.example" "%APP_ROOT%\.env" >nul
)

if not exist "%APP_ROOT%\backend\data" mkdir "%APP_ROOT%\backend\data"

echo 正在启动工作流系统服务...
start "工作流系统服务" cmd /k "cd /d ""%APP_ROOT%"" && set ""PYTHONUTF8=1"" && ""%PYTHON_EXE%"" -m uvicorn app.main:app --app-dir ""%APP_ROOT%\backend"" --host 0.0.0.0 --port 8000"

timeout /t 3 /nobreak >nul
start "" "http://127.0.0.1:8000/"

echo 已发起启动，浏览器会自动打开系统首页。
echo 如需关闭服务，请运行 stop_system.bat。
exit /b 0
