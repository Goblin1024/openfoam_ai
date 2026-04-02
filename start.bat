@echo off
chcp 65001 >nul
echo ==========================================
echo   OpenFOAM AI Agent - Interactive Mode
echo ==========================================
echo.
echo Activating virtual environment...
call .venv\Scripts\activate.bat

echo.
echo Starting interactive session...
echo Type 'help' for available commands
echo.
python interactive_openfoam_ai.py
pause
