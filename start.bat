@echo off
chcp 65001 >nul
REM A1 设备检修智能系统 - Windows 一键启动脚本

echo ============================================
echo   A1 设备检修智能系统 - 一键启动
echo ============================================
echo.

REM 检查 Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未安装 Python，请先安装 Python 3.11+
    pause
    exit /b 1
)

REM 检查 Node
node --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未安装 Node.js，请先安装 Node.js 20+
    pause
    exit /b 1
)

REM 检查 .env
if not exist ".env" (
    echo [提示] 未找到 .env，正在从 .env.example 复制...
    copy .env.example .env
    echo.
    echo [警告] 请编辑 .env 文件，填入 DASHSCOPE_API_KEY
    echo.
    notepad .env
)

echo [1/3] 安装后端依赖...
cd backend
if not exist ".venv" (
    python -m venv .venv
)
call .venv\Scripts\activate
pip install -q -r requirements.txt
cd ..

echo [2/3] 安装前端依赖...
cd frontend
if not exist "node_modules" (
    call npm install
)
cd ..

echo [3/3] 启动服务...
echo.
echo 启动后端: http://localhost:8000
echo 启动前端: http://localhost:5173
echo 启动文档: http://localhost:8000/docs
echo.

REM 后端启动
start "A1-Backend" cmd /k "cd backend && .venv\Scripts\activate && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"

REM 前端启动
start "A1-Frontend" cmd /k "cd frontend && npm run dev"

echo.
echo 服务已启动！关闭对应窗口即可停止。
echo.
pause
