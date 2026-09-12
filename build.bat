@echo off
REM Build the standalone Klute Timer app (dist\KluteTimer\KluteTimer.exe)
cd /d "%~dp0"

set "KT_DATA=%APPDATA%\KluteTimer"

echo [1/3] Preserving settings from any older install...
REM Before user data moved to %APPDATA%, config.json lived beside the exe --
REM and PyInstaller deletes dist\KluteTimer before the new exe can migrate it.
REM Rescue it here, once. An existing %APPDATA% config is never overwritten.
if exist "dist\KluteTimer\config.json" (
    if not exist "%KT_DATA%\config.json" (
        if not exist "%KT_DATA%" mkdir "%KT_DATA%"
        copy /y "dist\KluteTimer\config.json" "%KT_DATA%\config.json" >nul
        echo     Carried your old settings over to %KT_DATA%
    )
)

echo [2/3] Building KluteTimer.exe with PyInstaller...
python -m PyInstaller KluteTimer.spec --noconfirm
if errorlevel 1 (
    echo.
    echo Build FAILED. Is PyInstaller installed?  pip install -r requirements-dev.txt
    pause
    exit /b 1
)

echo [3/3] Done.
echo.
echo Built:    dist\KluteTimer\KluteTimer.exe
echo Settings: %KT_DATA%
echo.
echo Nothing you own lives in dist\KluteTimer, so rebuilding is always safe.
echo Shortcut: run  powershell -ExecutionPolicy Bypass -File scripts\create_shortcut.ps1
pause
