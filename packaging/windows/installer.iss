; Inno Setup script for Apofiz Play GTA6 (Windows x64). Built by build.ps1:
;   ISCC /DAppVersion=0.1.0 /DStageDir=...\.work\stage /DOutputDir=...\dist /DOutputBase=... installer.iss
; Works with Inno Setup 6.3+ and 7.x.
;
; Command-line switches understood by the installer (besides the standard Inno ones):
;   /NOLAUNCH         do not start the app after installing (default: start it, also in /SILENT
;                     mode, so the in-app auto-updater relaunches the app after an update)
; Uninstaller:
;   /REMOVEUSERDATA   also delete %USERPROFILE%\.ps5-remote and %LOCALAPPDATA%\ApofizPlay
;                     (interactive uninstall asks; silent uninstall keeps them unless this is given)

#ifndef AppVersion
  #define AppVersion "0.1.0"
#endif
#ifndef StageDir
  #define StageDir AddBackslash(SourcePath) + ".work\stage"
#endif
#ifndef OutputDir
  #define OutputDir AddBackslash(SourcePath) + "..\..\dist"
#endif
#ifndef OutputBase
  #define OutputBase "ApofizPlay-GTA6-" + AppVersion + "-win-x64-Setup"
#endif

#define AppName "Apofiz Play GTA6"
#define AppPyw "{app}\ApofizPlay.pyw"
#define FwRule "Apofiz Play GTA6"

[Setup]
AppId={{6F0B8E52-3C1D-4B7A-9E43-A9F2D1C6B7E4}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=Apofiz
AppPublisherURL=https://apofiz.com
DefaultDirName={autopf}\Apofiz Play GTA6
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
; Admin: needed for Program Files and the Windows Firewall rules.
PrivilegesRequired=admin
UsedUserAreasWarning=no
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir={#OutputDir}
OutputBaseFilename={#OutputBase}
SetupIconFile={#StageDir}\app.ico
UninstallDisplayIcon={app}\app.ico
UninstallDisplayName={#AppName}
Compression=lzma2/max
SolidCompression=yes
LZMAUseSeparateProcess=yes
LZMANumBlockThreads=4
WizardStyle=modern
; Close the running app (pythonw.exe from {app}\runtime) during install/update.
CloseApplications=force
CloseApplicationsFilter=*.exe,*.dll,*.pyd
RestartApplications=no
#ifdef Sign
SignTool=apofizsign
SignedUninstaller=yes
#endif

[Languages]
Name: "en"; MessagesFile: "compiler:Default.isl"
Name: "ru"; MessagesFile: "compiler:Languages\Russian.isl"

[CustomMessages]
en.AutoStart=Start {#AppName} when I sign in to Windows
ru.AutoStart=Запускать {#AppName} при входе в Windows
en.Firewall=Allow PS5 Remote Play through Windows Firewall (local network only): UDP 9295-9304 and 987, TCP 9295, plus the app's own Python. Without this, Windows may block the console's video stream.
ru.Firewall=Разрешить Remote Play с PS5 в брандмауэре Windows (только локальная сеть): UDP 9295-9304 и 987, TCP 9295 и Python приложения. Без этого Windows может блокировать видео с консоли.
en.FirewallGroup=Network:
ru.FirewallGroup=Сеть:
en.StartupGroup=Startup:
ru.StartupGroup=Автозапуск:
en.FwStatus=Adding Windows Firewall rules...
ru.FwStatus=Добавляю правила брандмауэра...
en.RemoveData=Also delete your settings and PS5 link (PSN sign-in, console keys, logs)?%n%n%1%n%2%n%nChoose No to keep them for a later reinstall.
ru.RemoveData=Удалить также настройки и привязку PS5 (вход в PSN, ключи консоли, логи)?%n%n%1%n%2%n%nНет — сохранить их для повторной установки.

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "autostart"; Description: "{cm:AutoStart}"; GroupDescription: "{cm:StartupGroup}"; Flags: unchecked
Name: "firewall"; Description: "{cm:Firewall}"; GroupDescription: "{cm:FirewallGroup}"

[InstallDelete]
; Fresh runtime on upgrade so removed packages don't linger.
Type: filesandordirs; Name: "{app}\runtime"

[Files]
Source: "{#StageDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Dirs]
; The app writes logs\, .env.local and __pycache__ next to its code (see README:
; "Known issues"), so ordinary users need write access to the install folder.
Name: "{app}"; Permissions: users-modify
Name: "{app}\logs"; Permissions: users-modify

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\runtime\pythonw.exe"; Parameters: """{#AppPyw}"""; WorkingDir: "{app}"; IconFilename: "{app}\app.ico"; Comment: "PS5 Remote Play + GTA6 AI"
Name: "{group}\Logs"; Filename: "{localappdata}\ApofizPlay\logs"
Name: "{group}\{cm:UninstallProgram,{#AppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\runtime\pythonw.exe"; Parameters: """{#AppPyw}"""; WorkingDir: "{app}"; IconFilename: "{app}\app.ico"; Tasks: desktopicon
Name: "{userstartup}\{#AppName}"; Filename: "{app}\runtime\pythonw.exe"; Parameters: """{#AppPyw}"" --no-browser"; WorkingDir: "{app}"; IconFilename: "{app}\app.ico"; Tasks: autostart

[Run]
; Firewall: drop old rules first (upgrade), then add. remoteip=localsubnet keeps it LAN-only;
; profile=any because many home Wi-Fi networks are marked "Public".
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall delete rule name=""{#FwRule}"""; Flags: runhidden; Tasks: firewall
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall add rule name=""{#FwRule}"" dir=in action=allow protocol=UDP localport=9295-9304,987 remoteip=localsubnet profile=any"; Flags: runhidden; StatusMsg: "{cm:FwStatus}"; Tasks: firewall
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall add rule name=""{#FwRule}"" dir=in action=allow protocol=TCP localport=9295 remoteip=localsubnet profile=any"; Flags: runhidden; Tasks: firewall
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall add rule name=""{#FwRule}"" dir=in action=allow protocol=UDP program=""{app}\runtime\python.exe"" remoteip=localsubnet profile=any"; Flags: runhidden; Tasks: firewall
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall add rule name=""{#FwRule}"" dir=in action=allow protocol=UDP program=""{app}\runtime\pythonw.exe"" remoteip=localsubnet profile=any"; Flags: runhidden; Tasks: firewall
; Launch after install. No skipifsilent: the auto-updater runs Setup.exe /SILENT and expects the app back.
Filename: "{app}\runtime\pythonw.exe"; Parameters: """{#AppPyw}"""; WorkingDir: "{app}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: postinstall nowait runasoriginaluser; Check: ShouldLaunch

[UninstallRun]
Filename: "{sys}\WindowsPowerShell\v1.0\powershell.exe"; Parameters: "-NoProfile -NonInteractive -ExecutionPolicy Bypass -Command ""Get-Process python,pythonw -ErrorAction SilentlyContinue | Where-Object {{ $_.Path -like '{app}\runtime\*' } | Stop-Process -Force"""; Flags: runhidden; RunOnceId: "StopApp"
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall delete rule name=""{#FwRule}"""; Flags: runhidden; RunOnceId: "DelFirewall"

[UninstallDelete]
; Runtime-created files inside the install folder (bytecode, logs, .env.local).
Type: filesandordirs; Name: "{app}"

[Code]
var
  RemoveUserData: Boolean;

function ShouldLaunch: Boolean;
begin
  Result := (Pos('/NOLAUNCH', UpperCase(GetCmdTail)) = 0);
end;

procedure StopRunningApp;
var
  Code: Integer;
begin
  // Stop launcher/server/bot started from this install folder (upgrade or uninstall).
  Exec(ExpandConstant('{sys}\WindowsPowerShell\v1.0\powershell.exe'),
    '-NoProfile -NonInteractive -ExecutionPolicy Bypass -Command "Get-Process python,pythonw -ErrorAction SilentlyContinue | ' +
    'Where-Object { $_.Path -like ''' + ExpandConstant('{app}') + '\runtime\*'' } | Stop-Process -Force"',
    '', SW_HIDE, ewWaitUntilTerminated, Code);
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  if DirExists(ExpandConstant('{app}\runtime')) then
    StopRunningApp;
  Result := '';
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  Backup: String;
begin
  // Restore the PSN sign-in saved by a previous uninstall (psn.py keeps it in {app}\.env.local).
  if CurStep = ssPostInstall then
  begin
    Backup := ExpandConstant('{%USERPROFILE}\.ps5-remote\env.local.backup');
    if FileExists(Backup) and not FileExists(ExpandConstant('{app}\.env.local')) then
      FileCopy(Backup, ExpandConstant('{app}\.env.local'), True);
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  UserDir, DataDir: String;
begin
  UserDir := ExpandConstant('{%USERPROFILE}\.ps5-remote');
  DataDir := ExpandConstant('{localappdata}\ApofizPlay');
  if CurUninstallStep = usUninstall then
  begin
    RemoveUserData := Pos('/REMOVEUSERDATA', UpperCase(GetCmdTail)) > 0;
    if (not RemoveUserData) and (not UninstallSilent) then
      RemoveUserData := MsgBox(FmtMessage(CustomMessage('RemoveData'), [UserDir, DataDir]),
        mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES;
    if not RemoveUserData then
    begin
      // Keep the PSN sign-in: it lives in {app}\.env.local, which is about to be deleted.
      if FileExists(ExpandConstant('{app}\.env.local')) then
      begin
        ForceDirectories(UserDir);
        FileCopy(ExpandConstant('{app}\.env.local'), UserDir + '\env.local.backup', False);
      end;
    end;
  end;
  if (CurUninstallStep = usPostUninstall) and RemoveUserData then
  begin
    DelTree(UserDir, True, True, True);
    DelTree(DataDir, True, True, True);
  end;
end;
