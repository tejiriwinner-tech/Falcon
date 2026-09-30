@echo off
title Falcon MT5 Exness Auto-Bridge
color 0A
cls
echo ============================================================
echo       FALCON METATRADER 5 (EXNESS) AUTOMATIC BRIDGE
echo ============================================================
echo.
echo [1/3] Checking Python installation...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not found in PATH!
    echo Please install Python from https://www.python.org/downloads/
    echo and make sure to check "Add Python to PATH" during installation.
    pause
    exit /b
)
echo [OK] Python is available.

echo.
echo [2/3] Checking MetaTrader5 and Requests libraries...
pip install MetaTrader5 requests --quiet
echo [OK] Dependencies verified.

echo.
echo [3/3] Launching Falcon MT5 Bridge...
echo Connecting to your active Exness MetaTrader 5 terminal...
echo.
python falcon_mt5_bridge.py

if %errorlevel% neq 0 (
    echo.
    echo [NOTICE] Bridge stopped. If MT5 failed to connect:
    echo 1. Open MetaTrader 5 on your PC and log into your Exness Demo account.
    echo 2. Click the "Algo Trading" button on top toolbar (Make sure it turns GREEN).
    echo 3. Run this file again.
    echo.
)
pause
