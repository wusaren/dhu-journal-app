@echo off
cd /d %~dp0backend\uploads
del /q *.* 2>nul
rmdir /s /q excel 2>nul
rmdir /s /q pdfs 2>nul
rmdir /s /q weibo 2>nul
echo Uploads directory cleaned