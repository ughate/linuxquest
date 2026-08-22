@echo off
REM Launcher for LinuxQuest on Windows.
cd /d "%~dp0"

where python >nul 2>nul
if %errorlevel% neq 0 (
    echo Python was not found on PATH. Install it from https://python.org
    echo and make sure to check "Add python.exe to PATH" during setup.
    pause
    exit /b 1
)

python -c "import colorama" >nul 2>nul
if %errorlevel% neq 0 (
    echo Installing required package "colorama"...
    pip install -r requirements.txt --quiet
)

python main.py %*
pause
