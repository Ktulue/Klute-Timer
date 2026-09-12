@echo off
REM Build Klute Timer: the app (dist\KluteTimer\KluteTimer.exe) and its
REM installer (dist\installer\KluteTimerSetup-<version>.exe).
REM
REM Inside a parenthesised block, a %VAR% that expands to text with a ) ends
REM the block early. Paths that can hold one, such as %APPDATA% with an
REM unusual user name, are only used quoted inside blocks and echoed after them.
cd /d "%~dp0"

set "KT_DATA=%APPDATA%\KluteTimer"

echo [1/4] Preserving settings from any older install...
REM Before user data moved to %APPDATA%, config.json lived beside the exe --
REM and PyInstaller deletes dist\KluteTimer before the new exe can migrate it.
REM Rescue it here, once. An existing %APPDATA% config is never overwritten.
set "KT_CARRIED="
if exist "dist\KluteTimer\config.json" (
    if not exist "%KT_DATA%\config.json" (
        if not exist "%KT_DATA%" mkdir "%KT_DATA%"
        copy /y "dist\KluteTimer\config.json" "%KT_DATA%\config.json" >nul
        set "KT_CARRIED=1"
    )
)
if defined KT_CARRIED echo     Carried your old settings over to %KT_DATA%

echo [2/4] Reading the version from src\version.py...
REM The one-liner prints nothing and exits non-zero unless __version__ is
REM exactly MAJOR.MINOR.PATCH, so nothing else reaches file names or ISCC.
set "KT_VERSION="
for /f "delims=" %%v in ('python -c "import re, sys; from src.version import __version__ as v; ok = isinstance(v, str) and re.fullmatch(r'\d+\.\d+\.\d+', v, re.ASCII); print(v) if ok else sys.exit('src/version.py: __version__ must be MAJOR.MINOR.PATCH, not ' + repr(v))"') do set "KT_VERSION=%%v"
if not defined KT_VERSION (
    echo.
    echo Build FAILED. Could not read a MAJOR.MINOR.PATCH version from src\version.py.
    pause
    exit /b 1
)
echo     Version %KT_VERSION%

REM A failed installer build must not leave an older installer behind under
REM the same name, where it would pass for the new one. del reports success
REM even when the file is open, so check again afterwards.
set "KT_SETUP=dist\installer\KluteTimerSetup-%KT_VERSION%.exe"
if exist "%KT_SETUP%" del /f /q "%KT_SETUP%"
if exist "%KT_SETUP%" (
    echo.
    echo Build FAILED. Could not delete the old installer, %KT_SETUP%
    echo Close anything that has it open, such as a running setup, and try again.
    pause
    exit /b 1
)

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
REM PATH first, looking only for ISCC.exe and never in the current folder,
REM then the machine-wide install, then the per-user install.
set "ISCC="
for /f "delims=" %%i in ('where "$PATH:ISCC.exe" 2^>nul') do if not defined ISCC set "ISCC=%%i"
if not defined ISCC if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not defined ISCC if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if not defined ISCC (
    echo.
    echo Build FAILED. Inno Setup 6 was not found. Install it with:
    echo     winget install JRSoftware.InnoSetup
    pause
    exit /b 1
)
echo     Using "%ISCC%"
"%ISCC%" /Q "/DAppVersion=%KT_VERSION%" installer\KluteTimer.iss
if errorlevel 1 (
    echo.
    echo Installer build FAILED. See the Inno Setup output above.
    echo Common causes: Inno Setup older than 6.7 ^(winget upgrade JRSoftware.InnoSetup^), or the installer file is open.
    pause
    exit /b 1
)

echo.
echo Done.
echo.
echo App:       dist\KluteTimer\KluteTimer.exe
echo Installer: %KT_SETUP%
echo Settings:  %KT_DATA%
echo.
echo Run the installer to install or upgrade Klute Timer. Nothing you own lives
echo in dist\, so rebuilding is always safe.
pause
