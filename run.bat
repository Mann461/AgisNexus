@echo off
cd /d "%~dp0"
title SolarShield AI Demo Suite Launcher
echo =======================================================
echo  SolarShield AI - Autonomous Policing Network Launcher
echo =======================================================
echo Checking Python installation...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in your system PATH!
    echo Please install Python 3.10+ and check the "Add Python to PATH" box.
    pause
    exit /b 1
)

echo Starting Demo Suite orchestrator...
python run_demo.py
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] The demo orchestrator exited with an error.
    pause
)
