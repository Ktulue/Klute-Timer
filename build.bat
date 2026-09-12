@echo off
REM Build Klute Timer: the app (dist\KluteTimer\KluteTimer.exe) and its
REM installer (dist\installer\KluteTimerSetup-<version>.exe).
cd /d "%~dp0"

set "KT_DATA=%APPDATA%\KluteTimer"

echo [1/4] Preserving settings from any older install...
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

echo [2/4] Reading the version from src\version.py...
set "KT_VERSION="
for /f "delims=" %%v in ('python -c "from src.version import __version__; print(__version__)"') do set "KT_VERSION=%%v"
if not defined KT_VERSION (
    echo.
    echo Build FAILED. Could not read the version from src\version.py.
    pause
    exit /b 1
)
echo     Version %KT_VERSION%

echo [3/4] Building KluteTimer.exe with PyInstaller...
python -m PyInstaller KluteTimer.spec --noconfirm
if errorlevel 1 (
    echo.
    echo Build FAILED. Is PyInstaller installed?  pip install -r requirements-dev.txt
    echo If KluteTimer.exe is running from dist\KluteTimer, close it and try again.
    pause
    exit /b 1
)

echo [4/4] Building the installer with Inno Setup...
set "ISCC="
for /f "delims=" %%i in ('where ISCC 2^>nul') do if not defined ISCC set "ISCC=%%i"
if not defined ISCC if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if not defined ISCC if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not defined ISCC (
    echo.
    echo Build FAILED. Inno Setup 6 was not found. Install it with:
    echo     winget install JRSoftware.InnoSetup
    pause
    exit /b 1
)
"%ISCC%" /Q /DAppVersion=%KT_VERSION% installer\KluteTimer.iss
if errorlevel 1 (
    echo.
    echo Installer build FAILED. See the Inno Setup output above.
    echo Klute Timer needs Inno Setup 6.3 or later:  winget upgrade JRSoftware.InnoSetup
    pause
    exit /b 1
)

echo.
echo Done.
echo.
echo App:       dist\KluteTimer\KluteTimer.exe
echo Installer: dist\installer\KluteTimerSetup-%KT_VERSION%.exe
echo Settings:  %KT_DATA%
echo.
echo Run the installer to install or upgrade Klute Timer. Nothing you own lives
echo in dist\, so rebuilding is always safe.
pause
