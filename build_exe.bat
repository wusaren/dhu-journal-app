@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

echo ================================================
echo  论文格式检测系统 - EXE 打包脚本
echo ================================================
echo.

echo 检查虚拟环境...
if not exist "%~dp0..\journal_venv\Scripts\activate.bat" (
    echo ERROR: Virtual environment not found
    echo Please create virtual environment at: %~dp0..\journal_venv
    pause
    exit /b 1
)
echo OK: Virtual environment found

echo.
echo 激活虚拟环境...
call "%~dp0..\journal_venv\Scripts\activate.bat"
if errorlevel 1 (
    echo ERROR: Failed to activate virtual environment
    pause
    exit /b 1
)
echo OK: Virtual environment activated

:: ── 检查 Python 环境 ──────────────────────────────
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Python，请先安装 Python 3.10+
    pause & exit /b 1
)

:: ── 安装 / 升级 PyInstaller ──────────────────────
echo [1/4] 检查 PyInstaller...
pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo   正在安装 PyInstaller...
    pip install pyinstaller
)
echo   PyInstaller 已就绪

:: ── 安装精简依赖 ────────────────────────────────
echo.
echo [2/4] 安装 C/S 精简依赖（requirements_cs.txt）...
pip install -r requirements_cs.txt
if errorlevel 1 (
    echo [警告] 部分依赖安装失败，继续尝试打包...
)

:: ── 清理旧构建产物 ────────────────────────────────
echo.
echo [3/4] 清理旧构建目录...
if exist build\论文格式检测系统 (
    rmdir /s /q build\论文格式检测系统
    echo   已清理 build\
)
if exist dist\论文格式检测系统 (
    rmdir /s /q dist\论文格式检测系统
    echo   已清理 dist\
)

:: ── 执行打包 ──────────────────────────────────────
echo.
echo [4/4] 开始打包，请耐心等待（可能需要 3~10 分钟）...
echo.
pyinstaller format_check_launcher.spec --noconfirm

if errorlevel 1 (
    echo.
    echo ================================================
    echo [失败] 打包过程中发生错误，请查看上方日志
    echo ================================================
    pause & exit /b 1
)

set DIST=dist\论文格式检测系统

:: 创建工作目录结构（首次运行会自动创建，这里预先建好）
mkdir "%DIST%\cs_data\temp"      2>nul
mkdir "%DIST%\cs_data\reports"   2>nul
mkdir "%DIST%\cs_data\annotated" 2>nul
mkdir "%DIST%\cs_data\logs"      2>nul

echo.
echo ================================================
echo  打包完成！
echo  输出目录：%CD%\dist\论文格式检测系统\
echo.
echo  分发方式：
echo  1. 将整个 "论文格式检测系统" 文件夹发给用户
echo  2. 用户双击 "论文格式检测系统.exe" 即可运行
echo  3. 无需安装 Python 或任何依赖
echo ================================================
echo.
pause
