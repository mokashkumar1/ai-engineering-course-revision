@echo off
setlocal enabledelayedexpansion

title AI Engineering Course Revision
echo ============================================================
echo       AI ENGINEERING COURSE REVISION ASSISTANT
echo ============================================================
echo.

:: 1. Check for .env file
if not exist ".env" (
    if exist ".env.example" (
        echo [*] Initializing .env from .env.example...
        copy ".env.example" ".env" >nul
        echo [!] Notice: Remember to add your GROQ_API_KEY to .env for AI answers.
    ) else (
        echo [!] Warning: .env.example not found.
    )
)

:: 2. Check for uv package manager first
where uv >nul 2>nul
if %ERRORLEVEL% equ 0 (
    echo [*] Detected 'uv' - syncing virtual environment...
    call uv sync
    if %ERRORLEVEL% neq 0 (
        echo [!] uv sync encountered an issue, trying standard run...
    )
    echo [*] Starting web application on http://127.0.0.1:8000 ...
    start "" http://127.0.0.1:8000
    call uv run uvicorn app:app --host 127.0.0.1 --port 8000 --reload
    goto :end
)

:: 3. Fallback to standard Python
where python >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Neither 'uv' nor 'python' was found on your system.
    echo Please install Python 3.10+ or Astral uv:
    echo   - uv: https://astral.sh/uv
    echo   - Python: https://www.python.org/
    echo.
    pause
    exit /b 1
)

:: Create .venv if not present
if not exist ".venv\Scripts\python.exe" (
    echo [*] Creating virtual environment in .venv ...
    python -m venv .venv
    if %ERRORLEVEL% neq 0 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
    echo [*] Installing dependencies from requirements.txt ...
    call .venv\Scripts\activate.bat
    python -m pip install --upgrade pip
    pip install -r requirements.txt
) else (
    call .venv\Scripts\activate.bat
)

echo [*] Starting web application on http://127.0.0.1:8000 ...
start "" http://127.0.0.1:8000
python -m uvicorn app:app --host 127.0.0.1 --port 8000 --reload

:end
pause
