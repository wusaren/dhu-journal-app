@echo off
chcp 65001 >nul
title Journal Management System
color 0A

echo ========================================
echo    Journal Management System
echo ========================================
echo.

echo [1/7] Checking virtual environment...
if not exist "%~dp0..\journal_venv\Scripts\activate.bat" (
    echo ERROR: Virtual environment not found
    echo Please create virtual environment at: %~dp0..\journal_venv
    pause
    exit /b 1
)
echo OK: Virtual environment found

echo.
echo [2/7] Activating virtual environment...
call "%~dp0..\journal_venv\Scripts\activate.bat"
if errorlevel 1 (
    echo ERROR: Failed to activate virtual environment
    pause
    exit /b 1
)
echo OK: Virtual environment activated

echo.
echo [3/7] Checking Python environment...
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not available in virtual environment
    echo Please check your virtual environment setup
    pause
    exit /b 1
)
echo OK: Python environment is ready

echo.
echo [4/7] Checking Node.js environment...
node --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Node.js not installed or not in PATH
    echo Please install Node.js 16+
    pause
    exit /b 1
)
echo OK: Node.js environment is ready

echo.
echo [6/7] Starting backend service...
start "Backend Service" cmd /k "call "%~dp0..\journal_venv\Scripts\activate.bat" && cd /d %~dp0backend && echo Virtual environment activated && echo Starting backend service... && python app.py"
echo OK: Backend service starting...

echo.
echo [7/7] Starting frontend service...
timeout /t 3 /nobreak >nul
start "Frontend Service" cmd /k "cd /d %~dp0front/dhu-Journal-app && echo Starting frontend service... && npm run dev"
echo OK: Frontend service starting...

echo.
echo ========================================
echo    System startup completed!
echo ========================================
echo.
echo Frontend URL: http://localhost:5173
echo Backend URL: http://localhost:5000
echo Default account: admin / admin123
echo.
echo Usage instructions:
echo    - Frontend service will open in browser automatically
echo    - Backend service provides API interfaces
echo    - Closing this window will not stop the services
echo    - To stop services, close the corresponding service windows
echo.
echo Press any key to exit...
pause >nul
