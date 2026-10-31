@echo off
setlocal
set "PET_PYTHON=%LocalAppData%\Programs\Python\Python314\pythonw.exe"
if not exist "%PET_PYTHON%" (
    echo Python 3.14 was not found at: %PET_PYTHON%
    pause
    exit /b 1
)
start "" "%PET_PYTHON%" "%~dp0pet.py"
