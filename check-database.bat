@echo off
rem Taki - show which database is in use and test that it answers. Double-click.
cd /d "%~dp0"
echo.
call start.bat check-db
echo.
echo   Press any key to close this window.
pause >nul
