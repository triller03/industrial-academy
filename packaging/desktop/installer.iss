; ASAPA - Windows desktop installer (Mufasa Corp)
; Built by packaging/desktop/build-desktop.ps1 (Inno Setup 6, per-user install).

#define MyAppName "ASAPA"
#define MyAppVersion "1.0.0"
#define MyAppExeName "IndustrialAcademy.exe"
#define MyAppPublisher "Mufasa Corp"

[Setup]
AppId={{B2A9D06F-4C1E-4F7A-9E3B-5D0C8A1F2E44}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
DefaultDirName={localappdata}\IndustrialAcademy\app
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
SetupIconFile=assets\app.ico
OutputDir=dist-desktop
OutputBaseFilename=ASAPA-Setup-{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayName={#MyAppName}
UninstallDisplayIcon={app}\{#MyAppExeName}
ArchitecturesInstallIn64BitMode=x64compatible
CreateAppDir=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
Source: "dist-desktop\IndustrialAcademy\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Start {#MyAppName} now"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}\_internal"







