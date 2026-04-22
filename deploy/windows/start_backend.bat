@echo off
set PYTHONUTF8=1
if not exist ..\..\backend\data mkdir ..\..\backend\data
set PYTHONPATH=%~dp0..\..\backend
py -3.8 -m uvicorn app.main:app --app-dir ..\..\backend --host 0.0.0.0 --port 8000
