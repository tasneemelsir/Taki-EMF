@echo off
rem Taki - double-click to start. The first run sets up its own Python
rem environment in the .venv folder (a few minutes); later runs start at once.
setlocal
cd /d "%~dp0"
title Taki

where py >nul 2>nul
if %errorlevel%==0 (set "PY=py -3") else (set "PY=python")
%PY% --version >nul 2>nul
if errorlevel 1 (
  echo.
  echo   Python 3.10 or newer is needed and was not found.
  echo   Get it from https://www.python.org/downloads/ and tick "Add python.exe to PATH"
  echo   during setup. Then run this file again.
  echo.
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo   Setting Taki up for the first time. This takes a few minutes...
  %PY% -m venv .venv
  if errorlevel 1 ( echo   Could not create the Python environment. & pause & exit /b 1 )
)

".venv\Scripts\python.exe" -c "import fastapi, uvicorn, numpy, matplotlib, reportlab, docx, psycopg" >nul 2>nul
if errorlevel 1 (
  echo   Installing what Taki needs...
  ".venv\Scripts\python.exe" -m pip install --quiet --upgrade pip
  ".venv\Scripts\python.exe" -m pip install --quiet -r requirements.txt
  if errorlevel 1 ( echo   Installation failed. Check the internet connection and run this again. & pause & exit /b 1 )
)

".venv\Scripts\python.exe" run.py %*
if errorlevel 1 pause
