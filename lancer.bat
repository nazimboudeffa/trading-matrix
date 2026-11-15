@echo off
REM Lance Trading Matrix avec l'environnement virtuel local
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Environnement virtuel introuvable. Lancez d'abord :
    echo   python -m venv .venv
    echo   .venv\Scripts\python.exe -m pip install -r requirements.txt
    pause
    exit /b 1
)
".venv\Scripts\python.exe" main.py
if errorlevel 1 pause
