; Inno Setup script for Klute Timer.
;
; Build with build.bat, which reads the version from src\version.py and passes
; it here as /DAppVersion. Paths below are relative to this file's folder.
;
; Per-user install: no UAC prompt, files in %LOCALAPPDATA%\Programs\KluteTimer,
; uninstall entry under HKCU. User data lives in %APPDATA%\KluteTimer and is
; deleted on uninstall only if the user answers Yes to the prompt in [Code].

#ifndef AppVersion
  #error AppVersion is not defined. Build with build.bat, which passes /DAppVersion from src\version.py.
#endif

[Setup]
; AppId ties upgrades and the uninstall entry together. Never change it.
AppId={{32085ADC-A6C1-4CF4-A9CE-7DAD72791E68}
AppName=Klute Timer
AppVersion={#AppVersion}
AppVerName=Klute Timer {#AppVersion}
AppPublisher=Ktulue
AppPublisherURL=https://github.com/Ktulue/Klute-Timer
AppSupportURL=https://github.com/Ktulue/Klute-Timer
VersionInfoVersion={#AppVersion}
VersionInfoCompany=Ktulue
VersionInfoProductName=Klute Timer
PrivilegesRequired=lowest
DefaultDirName={autopf}\KluteTimer
DisableDirPage=yes
DefaultGroupName=Klute Timer
DisableProgramGroupPage=yes
; The app holds this mutex while running (src\single_instance.py). Setup and
; uninstall wait for the user to close it instead of killing a live timer.
AppMutex=KluteTimer-AppMutex
CloseApplications=no
SetupIconFile=..\assets\KluteTimer.ico
UninstallDisplayIcon={app}\KluteTimer.exe
UninstallDisplayName=Klute Timer
OutputDir=..\dist\installer
OutputBaseFilename=KluteTimerSetup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[InstallDelete]
Type: filesandordirs; Name: "{app}\_internal"

[Files]
Source: "..\dist\KluteTimer\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"

[Icons]
Name: "{autoprograms}\Klute Timer"; Filename: "{app}\KluteTimer.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\Klute Timer"; Filename: "{app}\KluteTimer.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\KluteTimer.exe"; Description: "Launch Klute Timer"; Flags: postinstall nowait skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"; Check: IsDefaultInstallDir

[Code]
function IsDefaultInstallDir: Boolean;
begin
  Result := CompareText(ExpandConstant('{app}'), ExpandConstant('{autopf}\KluteTimer')) = 0;
end;

// Setup calls this before it copies a single file. It runs while the app may
// still be open, so it is where a running Klute Timer must be caught: without
// it, [InstallDelete] can remove unlocked parts of {app}\_internal out from
// under a live timer before AppMutex gets another chance to check.
function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  if CheckForMutexes('KluteTimer-AppMutex') then
    Result := 'Klute Timer is running. Close it (including from the tray), then click Back and Next to try again.'
  else
    Result := '';
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  DataDir: String;
begin
  if (CurUninstallStep = usUninstall) and (not UninstallSilent) then
  begin
    DataDir := ExpandConstant('{userappdata}\KluteTimer');
    if DirExists(DataDir) then
    begin
      if MsgBox('Also delete your Klute Timer settings, presets, logs, and timer text files?' + #13#10 + #13#10 +
                DataDir + #13#10 + #13#10 +
                'Choose No to keep them for a future reinstall. A custom output folder you chose somewhere else is never deleted.',
                mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
        if not DelTree(DataDir, True, True, True) then
          MsgBox('Some files in ' + DataDir + ' could not be deleted, possibly because another program (such as OBS) has them open. You can delete that folder by hand.', mbInformation, MB_OK);
    end;
  end;
end;
