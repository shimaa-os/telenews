@echo off
REM Double-click to send the Top-10 morning brief to your Telegram.
REM Uses .env for keys. Keeps window open so you can see the result.
cd /d "%~dp0"
python -m app.run_once
pause
