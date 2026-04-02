@echo off
echo ==========================================
echo   OpenFOAM AI - Interactive GUI
echo ==========================================
echo.
echo Activating virtual environment...
call .venv\Scripts\activate.bat

echo Starting GUI server...
echo The browser will open automatically.
echo.
echo Features:
echo   - AI-powered case generation
echo   - Real-time simulation
echo   - Interactive zoom/pan
echo   - Screenshot capture
echo.
python launch_gui.py

pause
