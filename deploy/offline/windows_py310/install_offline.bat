@echo off
setlocal
chcp 65001 >nul

set "ROOT=%~dp0"
set "APP_ROOT=%ROOT%app"
set "RUNTIME_ROOT=%ROOT%runtime\python"
set "PYTHON_EXE=%RUNTIME_ROOT%\python.exe"
set "SILENT=%~1"

if not exist "%PYTHON_EXE%" (
  echo 未找到内置 Python 运行时，请重新生成离线发布包。
  goto :failed
)

echo.
echo [1/3] 检查发布包目录
if not exist "%APP_ROOT%\backend\data" mkdir "%APP_ROOT%\backend\data"

echo [2/3] 初始化环境配置
if not exist "%APP_ROOT%\.env" (
  copy /Y "%ROOT%config\.env.offline.example" "%APP_ROOT%\.env" >nul
  echo 已自动生成 app\.env，请按实际情况补充邮件等配置。
) else (
  echo 检测到现有 app\.env，保留原配置不覆盖。
)

echo [3/3] 验证内置运行时
set PYTHONUTF8=1
"%PYTHON_EXE%" -c "import fastapi, uvicorn, sqlalchemy, openpyxl"
if errorlevel 1 (
  echo 内置运行时验证失败，请重新生成离线发布包。
  goto :failed
)

echo 内置运行时检查通过。
echo.
echo 离线安装完成。
echo 现在可直接双击 start_system.bat 启动系统。
if /I not "%SILENT%"=="/silent" pause
goto :end

:failed
echo 离线安装失败，请根据上方提示检查后重试。
if /I not "%SILENT%"=="/silent" pause
exit /b 1

:end
endlocal
