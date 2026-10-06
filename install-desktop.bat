@echo off
rem Taki - install the desktop version on this computer. Double-click to run it.
rem
rem It needs no administrator rights and changes nothing outside two folders:
rem     AppData\Local\Programs\Taki    the program
rem     AppData\Local\Taki             your projects (made by Taki itself)
rem
rem What it does:
rem   1. fetches Python from python.org into the program folder, for Taki alone
rem      (a Python that is already on the computer is not touched and not needed)
rem   2. hands over to tools\desktop_setup.py, which copies Taki beside it, installs
rem      the libraries it needs from pypi.org and makes the Taki shortcuts.
rem
rem Run it again at any time to repair the installation or to update it from a
rem newer download. Your projects are kept.
rem
rem This file is kept deliberately plain: no blocks in brackets, so folder names
rem with brackets or ampersands in them do no harm.
setlocal EnableExtensions DisableDelayedExpansion
title Install Taki
set "RC=1"

set "HERE=%~dp0"
set "SRC=%HERE%app"
if not exist "%SRC%\desktop.py" set "SRC=%HERE:~0,-1%"
if not exist "%SRC%\tools\desktop_setup.py" goto not_extracted
if not exist "%SRC%\server\main.py" goto not_extracted

set "BASE=%LOCALAPPDATA%"
if not defined BASE set "BASE=%USERPROFILE%\AppData\Local"
set "DEST=%BASE%\Programs\Taki"
set "PYDIR=%DEST%\python"
set "PY=%PYDIR%\python.exe"
set "PYSERIES=3.13"
set "PYVERSIONS=3.13.16 3.13.15 3.13.9"
set "TMPZIP=%TEMP%\taki-python-embed.zip"
set "CURLEXE=%SystemRoot%\System32\curl.exe"
set "TAREXE=%SystemRoot%\System32\tar.exe"

if /i "%PROCESSOR_ARCHITECTURE%"=="x86" if not defined PROCESSOR_ARCHITEW6432 goto too_old

echo.
echo   Installing Taki. This takes a few minutes and needs the internet.
echo.
if not exist "%DEST%" mkdir "%DEST%"
if not exist "%DEST%" goto no_folder

rem ---- 1. a Python of Taki's own ------------------------------------------
if not exist "%PY%" goto get_python
rem (a copy of Taki that is running is asked to stop first, so its files are free)
if exist "%DEST%\app\desktop.py" "%PY%" "%DEST%\app\desktop.py" --quit >nul 2>nul
"%PY%" -c "import sys; sys.exit(0 if sys.version_info[:2] == (3, 13) else 1)" >nul 2>nul
if not errorlevel 1 goto have_python
echo   Replacing the Python of an earlier installation ...
rmdir /s /q "%PYDIR%" >nul 2>nul
if exist "%PY%" goto in_use

:get_python
set "PYZIP="
for %%F in ("%HERE%python-%PYSERIES%.*-embed-amd64.zip") do set "PYZIP=%%~fF"
if defined PYZIP goto unpack
if exist "%TMPZIP%" del "%TMPZIP%"
if exist "%TMPZIP%.part" del "%TMPZIP%.part"
for %%V in (%PYVERSIONS%) do call :download %%V
if not exist "%TMPZIP%" goto system_python
set "PYZIP=%TMPZIP%"

:unpack
echo   Unpacking Python ...
if not exist "%PYDIR%" mkdir "%PYDIR%"
if exist "%TAREXE%" "%TAREXE%" -xf "%PYZIP%" -C "%PYDIR%" >nul 2>nul
if exist "%PY%" goto unpacked
set "TAKI_ZIP=%PYZIP%"
set "TAKI_DIR=%PYDIR%"
powershell -NoProfile -ExecutionPolicy Bypass -Command "Expand-Archive -LiteralPath $env:TAKI_ZIP -DestinationPath $env:TAKI_DIR -Force" >nul 2>nul
:unpacked
if exist "%TMPZIP%" del "%TMPZIP%"
if not exist "%PY%" goto system_python
"%PY%" -c "import sys" >nul 2>nul
if errorlevel 1 goto bad_python

:have_python
"%PY%" "%SRC%\tools\desktop_setup.py" install --source "%SRC%" --dest "%DEST%" %*
if errorlevel 1 goto failed
goto done

rem ---- no Python of its own could be fetched: use one that is already here ----
:system_python
echo   Python could not be fetched from python.org.
echo   Looking for a Python that is already on this computer ...
if exist "%PYDIR%" rmdir /s /q "%PYDIR%"
py -3 -c "import sys; sys.exit(0 if sys.version_info[:2] >= (3, 10) else 1)" >nul 2>nul
if not errorlevel 1 goto with_py
python -c "import sys; sys.exit(0 if sys.version_info[:2] >= (3, 10) else 1)" >nul 2>nul
if not errorlevel 1 goto with_python
goto no_python

:with_py
py -3 "%SRC%\tools\desktop_setup.py" install --source "%SRC%" --dest "%DEST%" %*
if errorlevel 1 goto failed
goto done

:with_python
python "%SRC%\tools\desktop_setup.py" install --source "%SRC%" --dest "%DEST%" %*
if errorlevel 1 goto failed
goto done

rem ---- fetch one version of Python; does nothing once a download has succeeded ----
rem (a version that python.org does not carry is passed over quietly, and the next is tried)
:download
if exist "%TMPZIP%" exit /b 0
set "TAKI_URL=https://www.python.org/ftp/python/%1/python-%1-embed-amd64.zip"
set "TAKI_OUT=%TMPZIP%.part"
echo   Fetching Python %1 from python.org ...
if not exist "%CURLEXE%" goto download_ps
"%CURLEXE%" --fail --location --silent --retry 2 --connect-timeout 20 --output "%TAKI_OUT%" "%TAKI_URL%" 2>nul
if not errorlevel 1 goto download_ok
:download_ps
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { [Net.ServicePointManager]::SecurityProtocol = 'Tls12'; $ProgressPreference = 'SilentlyContinue'; Invoke-WebRequest -UseBasicParsing -Uri $env:TAKI_URL -OutFile $env:TAKI_OUT } catch { exit 1 }" >nul 2>nul
if errorlevel 1 goto download_failed
:download_ok
if not exist "%TAKI_OUT%" goto download_failed
move /y "%TAKI_OUT%" "%TMPZIP%" >nul
if errorlevel 1 goto download_failed
exit /b 0
:download_failed
if exist "%TAKI_OUT%" del "%TAKI_OUT%"
exit /b 1

rem ---- how it ended ---------------------------------------------------------
:done
set "RC=0"
echo.
echo   Done. Start Taki with the Taki icon on the desktop or in the Start menu.
echo   You can delete the folder you installed from.
goto end

:in_use
echo.
echo   Taki's files are in use. Close Taki and run this file again.
goto end

:failed
echo.
echo   The installation did not finish. Nothing is broken: fix what the lines
echo   above say and run this file again.
echo   The details are in "%DEST%\install.log"
goto end

:not_extracted
echo.
echo   The Taki files were not found beside this installer.
echo.
echo   If you opened it from inside the zip: close this window, right-click the
echo   zip, choose Extract All, and run "Install Taki" from the folder that makes.
goto end

:too_old
echo.
echo   Taki needs 64-bit Windows 10 or newer.
goto end

:no_folder
echo.
echo   The folder "%DEST%" could not be made.
goto end

:bad_python
echo.
echo   The Python that was fetched does not run on this computer.
echo   Taki needs 64-bit Windows 10 or newer.
goto end

:no_python
echo.
echo   Python could not be fetched, and none was found on this computer.
echo.
echo   Check the internet connection and run this file again. If python.org is
echo   blocked here, either install Python 3.13 from the Microsoft Store, or put
echo   the file python-3.13.x-embed-amd64.zip beside this installer, and run it again.
goto end

:end
echo.
echo   Press any key to close this window.
pause >nul
endlocal & exit /b %RC%
