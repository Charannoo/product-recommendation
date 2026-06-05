@echo off
title SmartShop Launcher
echo ===================================================
echo             SmartShop Startup Launcher             
echo ===================================================
echo.

:: 1. Check if Python is installed globally
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Python was not found on your system.
    echo Please install Python 3.10+ (and add it to your PATH) to run this application.
    pause
    exit /b 1
)

:: 2. Check if .venv exists and if it is functional
set RECREATE_VENV=0

if not exist ".venv\Scripts\python.exe" (
    echo [INFO] Virtual environment (.venv) not found. Creating a new one...
    set RECREATE_VENV=1
) else (
    :: Test if the virtual environment python works (detect copy/path mismatch issues)
    ".venv\Scripts\python.exe" --version >nul 2>nul
    if %errorlevel% neq 0 (
        echo [WARNING] The existing virtual environment is broken or points to a different path.
        echo Recreating the virtual environment...
        set RECREATE_VENV=1
    )
)

if "%RECREATE_VENV%"=="1" (
    :: Clear and recreate virtual environment
    python -m venv .venv --clear
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
    echo [SUCCESS] Virtual environment created successfully.
)

:: 3. Install/Update dependencies
echo.
echo [INFO] Installing / verifying dependencies...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install dependencies.
    pause
    exit /b 1
)
echo [SUCCESS] Dependencies installed.

:: 4. Seed Database / Inject Lookbooks
echo.
echo [INFO] Seeding database and injecting lookbook items...
".venv\Scripts\python.exe" backend/inject_lookbooks.py
if %errorlevel% neq 0 (
    echo [WARNING] Lookbook injection script failed, but continuing...
) else (
    echo [SUCCESS] Database successfully seeded.
)

:: 5. Launch Application
echo.
echo [INFO] Starting the Flask server...
echo The application will be available at: http://127.0.0.1:5000/
echo.
echo Opening browser to http://127.0.0.1:5000/...
start http://127.0.0.1:5000/

".venv\Scripts\python.exe" backend/app.py
pause
