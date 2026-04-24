@echo off
setlocal
chcp 65001 >nul

set "ROOT=%~dp0"
set "APP_ROOT=%ROOT%app"
set "PYTHON_EXE=%ROOT%runtime\python\python.exe"
set "INSTALL_SCRIPT=%ROOT%tools\install_offline.py"
set "LOCAL_ROOT=%ROOT%local"
set "LOCAL_HOME=%LOCAL_ROOT%\home"
set "LOCAL_TMP=%LOCAL_ROOT%\temp"
set "LOCAL_CACHE=%LOCAL_ROOT%\cache"
set "LOCAL_PY_CACHE=%LOCAL_CACHE%\pycache"
set "LOCAL_APPDATA=%LOCAL_ROOT%\appdata"
set "LOCAL_PROGRAMDATA=%LOCAL_ROOT%\programdata"

if not exist "%PYTHON_EXE%" (
  echo 未找到内置 Python 运行时，请重新生成离线发布包。
  exit /b 1
)

if not exist "%INSTALL_SCRIPT%" (
  echo 未找到离线安装脚本，请重新生成离线发布包。
  exit /b 1
)

echo 正在检查本地运行环境...
"%PYTHON_EXE%" "%INSTALL_SCRIPT%" /silent
if errorlevel 1 (
  echo 本地初始化失败，请先执行 install_offline.bat 查看详细错误信息。
  exit /b 1
)

echo 正在启动工作流系统服务...
start "工作流系统服务" cmd /k "cd /d ""%APP_ROOT%"" && set ""PYTHONUTF8=1"" && set ""PYTHONPYCACHEPREFIX=%LOCAL_PY_CACHE%"" && set ""PYTHONUSERBASE=%LOCAL_HOME%"" && set ""TMP=%LOCAL_TMP%"" && set ""TEMP=%LOCAL_TMP%"" && set ""HOME=%LOCAL_HOME%"" && set ""USERPROFILE=%LOCAL_HOME%"" && set ""APPDATA=%LOCAL_APPDATA%"" && set ""LOCALAPPDATA=%LOCAL_APPDATA%"" && set ""PROGRAMDATA=%LOCAL_PROGRAMDATA%"" && ""%PYTHON_EXE%"" -m uvicorn app.main:app --app-dir ""%APP_ROOT%\backend"" --host 0.0.0.0 --port 8000"

timeout /t 3 /nobreak >nul
start "" "http://127.0.0.1:8000/"

echo 已发起启动，浏览器会自动打开系统首页。
echo 运行期缓存、临时文件和用户环境目录均固定在发布包 local 目录中。
echo 如需关闭服务，请运行 stop_system.bat。
exit /b 0
