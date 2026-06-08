[Setup]
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName=QuickShot
AppVersion=5.3.9
AppPublisher=QuickShot
DefaultDirName={autopf}\QuickShot
DefaultGroupName=QuickShot
UninstallDisplayName=QuickShot
AllowNoIcons=yes
UsePreviousTasks=no
OutputDir=installer_output
OutputBaseFilename=QuickShot-5.3.9-Setup
SetupIconFile=assets\icon.ico
UninstallDisplayIcon={app}\QuickShot.exe
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "chinesesimp"; MessagesFile: "installer\ChineseSimplified.isl"

[CustomMessages]
english.DesktopIconTask=Create desktop shortcut
english.AdditionalIconsTaskGroup=Additional icons:
english.StartupTask=Start with Windows
english.OtherOptionsTaskGroup=Other options:
english.LaunchQuickShot=Launch QuickShot
chinesesimp.DesktopIconTask=创建桌面快捷方式
chinesesimp.AdditionalIconsTaskGroup=附加图标:
chinesesimp.StartupTask=随 Windows 启动
chinesesimp.OtherOptionsTaskGroup=其他选项:
chinesesimp.LaunchQuickShot=启动 QuickShot

[Tasks]
Name: "desktopicon"; Description: "{cm:DesktopIconTask}"; GroupDescription: "{cm:AdditionalIconsTaskGroup}"; Flags: unchecked
Name: "startupicon"; Description: "{cm:StartupTask}"; GroupDescription: "{cm:OtherOptionsTaskGroup}"; Flags: unchecked

[Files]
Source: "dist\QuickShot.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\QuickShot"; Filename: "{app}\QuickShot.exe"
Name: "{group}\Uninstall QuickShot"; Filename: "{uninstallexe}"
Name: "{autodesktop}\QuickShot"; Filename: "{app}\QuickShot.exe"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "QuickShot"; ValueData: """{app}\QuickShot.exe"""; Flags: uninsdeletevalue; Tasks: startupicon

[Run]
Filename: "{app}\QuickShot.exe"; Description: "{cm:LaunchQuickShot}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{cmd}"; Parameters: "/C taskkill /F /IM QuickShot.exe 2>nul"; Flags: runhidden; RunOnceId: "StopQuickShot"

[Code]
var
  ResultCode: Integer;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssInstall then
  begin
    Exec('taskkill', '/IM QuickShot.exe /F', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  end;
end;
