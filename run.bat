@echo off
echo ========================================
echo  Export Downstreaming DSS Launcher
echo ========================================
echo.

:: Check if virtual environment exists
if not exist "venv\" (
    echo [!] Virtual environment not found!
    echo [*] Creating virtual environment...
    python -m venv venv
    echo [+] Virtual environment created!
    echo.
)

:: Activate virtual environment
echo [*] Activating virtual environment...
call venv\Scripts\activate.bat

:: Check if dependencies are installed
echo [*] Checking dependencies...
pip show streamlit >nul 2>&1
if errorlevel 1 (
    echo [!] Dependencies not installed!
    echo [*] Installing dependencies...
    pip install -r requirements.txt
    echo [+] Dependencies installed!
)

echo.
echo [+] Starting application...
echo [*] Application will open in your browser
echo.

:: Run the Streamlit app
cd src
streamlit run app.py

:: Deactivate virtual environment on exit
cd ..
deactivate
