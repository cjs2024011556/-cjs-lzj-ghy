@echo off
echo 正在启动 MotoEngine 服务...
echo.

:: 用你当前的虚拟环境 Python 启动 FastAPI
.\.venv\Scripts\python.exe -m uvicorn main:app --reload --host 0.0.0.0 --port 8000

pause