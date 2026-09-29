; =====================================================================
; Inno Setup Script para MyGDriveSync (Windows x64)
; Compilar con: iscc.exe scripts\installer.iss
; =====================================================================

#define MyAppName "MyGDriveSync"
#define MyAppVersion "0.1.0"
#define MyAppPublisher "davidzmx"
#define MyAppURL "https://github.com/davidzmx/MyGDriveSync"
#define MyAppExeName "MyGDriveSync.exe"

[Setup]
AppId={{D37E84B2-9F12-42B1-8C53-8A21B428A401}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\MyGDriveSync
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
OutputDir=..\dist
OutputBaseFilename=MyGDriveSync_Setup_x64
SetupIconFile=..\assets\gdrive-sync.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64
UninstallDisplayIcon={app}\{#MyAppExeName}
PrivilegesRequired=lowest

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "startup"; Description: "Iniciar MyGDriveSync automáticamente al iniciar Windows"; GroupDescription: "Opciones adicionales:"

[Files]
Source: "..\dist\MyGDriveSync\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Registry]
; Inicio automatico al arrancar Windows
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "MyGDriveSync"; ValueData: """{app}\{#MyAppExeName}"""; Flags: uninsdeletevalue; Tasks: startup

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
