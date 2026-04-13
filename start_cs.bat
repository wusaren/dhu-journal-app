@echo off
chcp 65001 >nul
title 论文格式检测 - 一键启动

echo ======================================================
echo   论文格式检测系统 - 一键启动（Server + Client）
echo ======================================================
echo.

cd /d "%~dp0"

echo [1/5] 检查虚拟环境...
if not exist "%~dp0..\journal_venv\Scripts\activate.bat" (
    echo ERROR: 未找到虚拟环境
    echo 请确认虚拟环境存在于: %~dp0..\journal_venv
    pause
    exit /b 1
)
echo OK: 虚拟环境已找到

echo.
echo [2/5] 激活虚拟环境...
call "%~dp0..\journal_venv\Scripts\activate.bat"
if errorlevel 1 (
    echo ERROR: 虚拟环境激活失败
    pause
    exit /b 1
)
echo OK: 虚拟环境已激活

echo.
echo [3/5] 检查 Python 环境...
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python 不可用，请检查虚拟环境
    pause
    exit /b 1
)
echo OK: Python 环境正常

echo.
echo [4/5] 启动 Server（新窗口）...
start "论文格式检测 - 服务端" /D "%~dp0" cmd /k "call ""%~dp0..\journal_venv\Scripts\activate.bat"" && python ""%~dp0format_check_server.py"""
echo OK: Server 启动命令已发送

timeout /t 2 /nobreak >nul

echo.
echo [5/5] 启动 Client...
python format_check_client.py

pause
