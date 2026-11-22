@echo off
title Quick ATS Matcher
cd /d "%~dp0"
echo =========================================================================
echo Starting Quick ATS Matcher...
echo - On this PC: http://localhost:5050
echo - On your Mobile Phone (Same Wi-Fi): http://192.168.1.13:5050
echo - On Mobile from Anywhere (5G/Cellular): Double-click start-mobile-tunnel.bat
echo =========================================================================
start http://localhost:5050
.\.venv\Scripts\python.exe -m uvicorn app:app --host 0.0.0.0 --port 5050 --reload
pause
