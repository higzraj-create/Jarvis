@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title J.A.R.V.I.S - Robot Face Music Reactor

set "VENV=%~dp0.venv"
set "VPY=%VENV%\Scripts\python.exe"
set "OK=%VENV%\jarvis_ready.txt"

rem ---- already installed? then just start --------------------------------
if not exist "%VPY%" goto :setup
if not exist "%OK%" goto :setup
"%VPY%" -c "import PySide6, numpy, edge_tts, mutagen, imageio_ffmpeg" >nul 2>nul
if errorlevel 1 goto :setup
goto :run

:setup
echo ==========================================================
echo   J.A.R.V.I.S  -  first-time setup  (only happens once)
echo ==========================================================
set "PYEXE="
for %%V in (3.13 3.12 3.11 3.10) do (
    if not defined PYEXE (
        py -%%V -c "import sys" >nul 2>nul
        if not errorlevel 1 set "PYEXE=py -%%V"
    )
)
if not defined PYEXE (
    python -c "import sys; sys.exit(0 if (3,10) <= sys.version_info[:2] <= (3,13) else 1)" >nul 2>nul
    if not errorlevel 1 set "PYEXE=python"
)
if not defined PYEXE (
    echo [ERROR] Python 3.10 - 3.13 was not found.
    echo         Install Python 3.13 from https://www.python.org/downloads/
    echo         and tick "Add python.exe to PATH" in the installer, then run this file again.
    goto :fail
)
echo Using Python: %PYEXE%

if not exist "%VPY%" (
    echo Creating virtual environment...
    %PYEXE% -m venv "%VENV%"
    if errorlevel 1 (
        echo [ERROR] Could not create the virtual environment.
        goto :fail
    )
)

echo Upgrading pip...
"%VPY%" -m pip install --upgrade pip --disable-pip-version-check >nul 2>nul

echo.
echo Installing core packages (PySide6 is about 200 MB, please wait)...
"%VPY%" -m pip install -r requirements.txt --disable-pip-version-check
if errorlevel 1 (
    echo [ERROR] Core installation failed. Check your internet connection and run this file again.
    goto :fail
)

echo.
echo Installing microphone / voice-command packages (optional)...
"%VPY%" -m pip install -r requirements-voice.txt --disable-pip-version-check
if errorlevel 1 (
    echo [WARNING] Voice packages could not be installed. JARVIS will still work with typed commands.
)

> "%OK%" echo ready
echo.
echo Setup complete.

:run
echo.
echo Starting J.A.R.V.I.S ...
"%VPY%" jarvis_music.py
if errorlevel 1 (
    echo.
    echo [ERROR] J.A.R.V.I.S closed with an error. Read the messages above.
    echo         Tip: delete the .venv folder and run this file again for a clean reinstall.
    pause
    exit /b 1
)
exit /b 0

:fail
echo.
echo Setup failed. See the messages above.
pause
exit /b 1
