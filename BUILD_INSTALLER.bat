@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Build JARVIS.exe
echo ==========================================================
echo   Building JARVIS.exe  (takes 5-15 minutes, needs internet)
echo ==========================================================
set "PYEXE="
for %%V in (3.13 3.12 3.11 3.10) do (
    if not defined PYEXE (
        py -%%V -c "import sys" >nul 2>nul
        if not errorlevel 1 set "PYEXE=py -%%V"
    )
)
if not defined PYEXE (
    echo [ERROR] Python 3.10 - 3.13 not found. Install Python 3.13 from python.org ^(tick "Add to PATH"^).
    pause & exit /b 1
)
if not exist ".venv\Scripts\python.exe" %PYEXE% -m venv .venv
set "VPY=%~dp0.venv\Scripts\python.exe"
"%VPY%" -m pip install --upgrade pip
"%VPY%" -m pip install -r requirements.txt -r requirements-voice.txt pyinstaller
if errorlevel 1 ( echo [ERROR] Install failed. & pause & exit /b 1 )

"%VPY%" -m PyInstaller --noconfirm --clean --windowed --name JARVIS --icon jarvis.ico ^
  --paths . ^
  --collect-all PySide6.QtMultimedia ^
  --collect-all imageio_ffmpeg ^
  --collect-all faster_whisper ^
  --collect-all ctranslate2 ^
  --collect-all edge_tts ^
  --collect-all sounddevice ^
  --collect-all pyttsx3 ^
  --hidden-import robotface ^
  --hidden-import mutagen ^
  --exclude-module tkinter ^
  jarvis_music.py
if errorlevel 1 ( echo [ERROR] Build failed. & pause & exit /b 1 )

copy /y pronunciations.json dist\JARVIS\ >nul
copy /y api_key.txt dist\JARVIS\ >nul
copy /y jarvis.ico dist\JARVIS\ >nul
rem ---- installer (Inno Setup) ----
set "ISCC="
for %%P in ("%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" "%ProgramFiles%\Inno Setup 6\ISCC.exe") do if exist %%P set "ISCC=%%~P"
if not defined ISCC (
    echo Installing Inno Setup ^(installer builder^)...
    winget install --id JRSoftware.InnoSetup -e --silent --accept-package-agreements --accept-source-agreements
    for %%P in ("%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" "%ProgramFiles%\Inno Setup 6\ISCC.exe") do if exist %%P set "ISCC=%%~P"
)
if not defined ISCC (
    echo [WARN] Inno Setup not found. Install it from https://jrsoftware.org/isdl.php and run this file again.
    echo        The portable app is still available in dist\JARVIS\JARVIS.exe
    pause & exit /b 1
)
"%ISCC%" jarvis_installer.iss
if errorlevel 1 ( echo [ERROR] Installer build failed. & pause & exit /b 1 )
echo.
echo ==========================================================
echo  DONE.  Installer:  installer\JARVIS_Setup.exe
echo  Double-click it to install JARVIS with its icon, Start Menu + Desktop shortcut.
echo ==========================================================
pause
