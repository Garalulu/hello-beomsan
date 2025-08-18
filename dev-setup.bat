@echo off
echo Setting up local development environment...

REM Copy environment file if it doesn't exist
if not exist .env (
    echo Creating .env file from example...
    copy .env.example .env
    echo.
    echo IMPORTANT: Edit .env file and add your osu! OAuth credentials!
    echo Get them from: https://osu.ppy.sh/home/account/edit
    echo.
    pause
)

REM Install dependencies
echo Installing Python dependencies...
if exist .venv (
    .venv\Scripts\activate.bat && uv pip install -r requirements.txt
) else (
    echo Creating virtual environment...
    python -m venv .venv
    .venv\Scripts\activate.bat && uv pip install -r requirements.txt
)

REM Run migrations
echo Running database migrations...
python manage.py migrate

REM Create superuser if needed
echo.
echo You can create a superuser account if needed:
echo python manage.py createsuperuser
echo.

echo Setup complete! Run 'dev-start.bat' to start the development server.
pause