#!/bin/bash

echo "========================================"
echo " Export Downstreaming DSS Launcher"
echo "========================================"
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "[!] Virtual environment not found!"
    echo "[*] Creating virtual environment..."
    python3 -m venv venv
    echo "[+] Virtual environment created!"
    echo ""
fi

# Activate virtual environment
echo "[*] Activating virtual environment..."
source venv/bin/activate

# Check if dependencies are installed
echo "[*] Checking dependencies..."
if ! pip show streamlit > /dev/null 2>&1; then
    echo "[!] Dependencies not installed!"
    echo "[*] Installing dependencies..."
    pip install -r requirements.txt
    echo "[+] Dependencies installed!"
fi

echo ""
echo "[+] Starting application..."
echo "[*] Application will open in your browser"
echo ""

# Run the Streamlit app
cd src
streamlit run app.py

# Deactivate virtual environment on exit
cd ..
deactivate
