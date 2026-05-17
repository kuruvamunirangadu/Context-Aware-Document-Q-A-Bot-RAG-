@echo off
REM Start the FastAPI backend server

echo Navigating to backend folder...
cd backend

echo Installing dependencies...
pip install -r requirements.txt

echo.
echo ========================================
echo Backend server starting on port 8000
echo ========================================
echo.

uvicorn app:app --reload --port 8000

pause
