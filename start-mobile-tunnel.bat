@echo off
title Quick ATS Matcher - Mobile Anywhere Tunnel
cd /d "%~dp0"
echo =========================================================================
echo    QUICK ATS SCANNER - MOBILE TUNNEL (ACCESS FROM ANYWHERE / 5G / 4G)
echo =========================================================================
echo.
echo Starting secure public tunnel...
echo (You will see an HTTPS link below. Open that link on your mobile phone)
echo.
echo Press Ctrl+C at any time to stop the tunnel.
echo =========================================================================
echo.

ssh -o StrictHostKeyChecking=no -o ServerAliveInterval=30 -o ServerAliveCountMax=5 -R 80:127.0.0.1:5050 nokey@localhost.run
pause
