@echo off
title AEGIS - Google Account Authentication
echo ========================================================
echo        AEGIS AI COPILOT - GOOGLE ACCOUNT LINK
echo ========================================================
echo.
echo Opening Google Chrome with AEGIS persistent profile...
echo Please log into your Google Account in the browser window.
echo Once signed in, close the browser window.
echo.
"C:\Program Files\Google\Chrome\Application\chrome.exe" --user-data-dir="%~dp0data\google_profile" https://accounts.google.com
echo.
echo ========================================================
echo Google Account linked successfully!
echo You can now join any Google Meet call with AEGIS.
echo ========================================================
echo.
pause
