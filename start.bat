@echo off
chcp 65001 >nul
echo Starting Journal Management System...

echo Rebuilding database...
python rebuild_database.py

echo Cleaning uploads directory...
call clean_uploads.bat

echo Starting backend service...
start "Backend Service" cmd /k "cd /d %~dp0backend && python app.py"

echo Waiting for backend to start...
timeout /t 3 /nobreak >nul

echo Starting frontend service...
start "Frontend Service" cmd /k "cd /d %~dp0front/dhu-Journal-app && npm run dev"

echo System startup completed!
echo Frontend URL: http://localhost:5173
echo Backend URL: http://localhost:5000
echo Default account: admin / admin123

pause