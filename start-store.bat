@echo off
cd /d "%~dp0"
where py >nul 2>&1
if %errorlevel%==0 (
    py store_server.py
) else (
    python store_server.py
)
pause
