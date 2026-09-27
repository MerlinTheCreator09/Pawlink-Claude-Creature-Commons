@echo off
rem Starts the PawLink dashboard and opens it in the browser.
rem Close the Arduino IDE Serial Monitor first - only one program can use the COM port.
cd /d "%~dp0"
start "" http://localhost:8000
python server.py %*
pause
