@echo off
cd /d "%~dp0"

if not exist "venv" (
    echo [INFO] Environment not found. Creating isolated environment...
    python -m venv venv
)

call venv\Scripts\activate.bat

if exist "requirements.txt" (
    echo [INFO] Scanning and installing requirements...
    pip install -r requirements.txt >nul 2>&1
)

python "desk_comps.py" -d "%~1"

deactivate
pause