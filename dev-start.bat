@echo off
echo Starting Django development server...

REM Check if .env exists
if not exist .env (
    echo ERROR: .env file not found!
    echo Please run dev-setup.bat first
    pause
    exit /b 1
)

REM Run Django development server
python manage.py runserver

pause