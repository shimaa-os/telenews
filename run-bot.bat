@echo off
REM Double-click to start the private bot listener.
REM Leave this window open, then send "news" in Telegram and it replies.
REM Press Ctrl+C to stop.
cd /d "%~dp0"
python -m app.run_bot
pause
