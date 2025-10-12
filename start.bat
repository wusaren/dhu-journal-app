@echo off
chcp 65001 >nul
title Journal Management System
color 0A

echo ========================================
echo    Journal Management System
echo ========================================
echo.

echo [1/6] Checking Python environment...
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not installed or not in PATH
    echo Please install Python 3.8+
    pause
    exit /b 1
)
echo OK: Python environment is ready

echo.
echo [2/6] Checking Node.js environment...
node --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Node.js not installed or not in PATH
    echo Please install Node.js 16+
    pause
    exit /b 1
)
echo OK: Node.js environment is ready

echo.
echo [3/6] Rebuilding database...
cd /d %~dp0
python rebuild_database.py
if errorlevel 1 (
    echo ERROR: Database rebuild failed
    pause
    exit /b 1
)
echo OK: Database rebuild completed

echo.
echo [4/6] Checking upload files...
if exist "backend\uploads\*" (
    echo Found upload files, cleaning...
    call clean_uploads.bat
    echo OK: Upload files cleaned
) else (
    echo No upload files to clean
)

echo.
echo [5/6] Starting backend service...
start "Backend Service" cmd /k "cd /d %~dp0backend && echo Starting backend service... && python app.py"
echo OK: Backend service starting...

echo.
echo [6/6] Starting frontend service...
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