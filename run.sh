#!/bin/bash

echo "==================================================="
echo "            SmartShop Startup Launcher             "
echo "==================================================="
echo

# 1. Determine python executable
if command -v python3 &>/dev/null; then
    PYTHON_CMD="python3"
elif command -v python &>/dev/null; then
    PYTHON_CMD="python"
else
    echo "[ERROR] Python was not found on your system."
    echo "Please install Python 3.10+ to run this application."
    exit 1
fi

# 2. Check if .venv exists and if it is functional
RECREATE_VENV=0

if [ ! -f ".venv/bin/python" ]; then
    echo "[INFO] Virtual environment (.venv) not found. Creating a new one..."
    RECREATE_VENV=1
else
    # Test if the virtual environment python works (detect path mismatch issues)
    .venv/bin/python --version &>/dev/null
    if [ $? -ne 0 ]; then
        echo "[WARNING] The existing virtual environment is broken or points to a different path."
        echo "Recreating the virtual environment..."
        RECREATE_VENV=1
    fi
fi

if [ "$RECREATE_VENV" -eq 1 ]; then
    # Clear and recreate virtual environment
    $PYTHON_CMD -m venv .venv --clear
    if [ $? -ne 0 ]; then
        echo "[ERROR] Failed to create virtual environment."
        exit 1
    fi
    echo "[SUCCESS] Virtual environment created successfully."
fi

# 3. Install/Update dependencies
echo
echo "[INFO] Installing / verifying dependencies..."
.venv/bin/python -m pip install -r requirements.txt
if [ $? -ne 0 ]; then
    echo "[ERROR] Failed to install dependencies."
    exit 1
fi
echo "[SUCCESS] Dependencies installed."

# 4. Seed Database / Inject Lookbooks
echo
echo "[INFO] Seeding database and injecting lookbook items..."
.venv/bin/python backend/inject_lookbooks.py
if [ $? -ne 0 ]; then
    echo "[WARNING] Lookbook injection script failed, but continuing..."
else
    echo "[SUCCESS] Database successfully seeded."
fi

# 5. Launch Application
echo
echo "[INFO] Starting the Flask server..."
echo "The application will be available at: http://127.0.0.1:5000/"
echo

# Try to open browser automatically
if [[ "$OSTYPE" == "darwin"* ]]; then
    open "http://127.0.0.1:5000/"
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    if command -v xdg-open &>/dev/null; then
        xdg-open "http://127.0.0.1:5000/"
    fi
fi

.venv/bin/python backend/app.py
