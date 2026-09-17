@echo off
chcp 65001 > nul
setlocal

REM 一键启动 IndustrialMap：两个终端窗口分别拉起后端和前端
REM 需要：Python 3.10+、Node.js 18+、已安装依赖（首次需手动执行 install）

echo ==============================================
echo  IndustrialMap 启动脚本
echo  - 后端: http://127.0.0.1:8000
echo  - 前端: http://127.0.0.1:5173
echo ==============================================
echo.

set ROOT=%~dp0

REM 启动后端
start "IndustrialMap-Backend" cmd /k "cd /d %ROOT%backend && if exist .venv (call .venv\Scripts\activate) && uvicorn app.main:app --reload --host 127.0.0.1 --port 8000"

REM 启动前端
start "IndustrialMap-Frontend" cmd /k "cd /d %ROOT%frontend && npm run dev"

echo 两个终端已打开。
echo 关闭对应窗口即可停止对应服务。
endlocal