# Creates a "Klute Timer" shortcut on the desktop pointing at the built exe.
# Run after build.bat:
#   powershell -ExecutionPolicy Bypass -File scripts\create_shortcut.ps1
$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
$exe  = Join-Path $root 'dist\KluteTimer\KluteTimer.exe'
$icon = Join-Path $root 'assets\KluteTimer.ico'

if (-not (Test-Path $exe)) {
    Write-Error "Not built yet: $exe`nRun build.bat first."
    exit 1
}

$desktop = [Environment]::GetFolderPath('Desktop')
$lnkPath = Join-Path $desktop 'Klute Timer.lnk'

$shell = New-Object -ComObject WScript.Shell
$sc = $shell.CreateShortcut($lnkPath)
$sc.TargetPath       = $exe
$sc.WorkingDirectory = Split-Path $exe
$sc.IconLocation     = $icon
$sc.Description       = 'Klute Timer - stream timer'
$sc.Save()

Write-Host "Desktop shortcut created: $lnkPath"
