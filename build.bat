@echo off
REM Build the standalone Klute Timer app (dist\KluteTimer\KluteTimer.exe)
cd /d "%~dp0"

echo [1/3] Building KluteTimer.exe with PyInstaller...
python -m PyInstaller KluteTimer.spec --noconfirm
if errorlevel 1 (
    echo.
    echo Build FAILED. Is PyInstaller installed?  pip install -r requirements-dev.txt
    pause
    exit /b 1
)

echo [2/3] Staging editable files next to the exe...
REM COLLECT --noconfirm recreates dist\KluteTimer, so these are re-copied each build.
if not exist "dist\KluteTimer\config.json" copy /y "config.json" "dist\KluteTimer\config.json" >nul
if not exist "dist\KluteTimer\output" mkdir "dist\KluteTimer\output"
if not exist "dist\KluteTimer\sounds" mkdir "dist\KluteTimer\sounds"

echo [3/3] Done.
echo.
echo Built:  dist\KluteTimer\KluteTimer.exe
echo Shortcut: run  powershell -ExecutionPolicy Bypass -File scripts\create_shortcut.ps1
pause
