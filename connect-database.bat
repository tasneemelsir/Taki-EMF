@echo off
rem Taki - connect an online database (Supabase, Neon, ...). Double-click and follow the questions.
cd /d "%~dp0"
call start.bat setup-db
echo.
echo   Done. This window can be closed.
echo   To test the connection at any time, double-click check-database.bat
echo.
echo   Press any key to close this window.
pause >nul
