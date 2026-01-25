@echo off
setlocal

call .venv\Scripts\activate.bat
python -m backtesting_system.main

echo.
echo Backtest finished.
endlocal
