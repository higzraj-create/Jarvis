; Inno Setup script - builds JARVIS_Setup.exe from dist\JARVIS
#define AppName "J.A.R.V.I.S Music Reactor"
#define AppVer "10.0"
[Setup]
AppId={{7A3C1B52-9D4E-4F10-B7C2-5A1E0C9D2F11}
AppName={#AppName}
AppVersion={#AppVer}
AppPublisher=JARVIS
DefaultDirName={localappdata}\Programs\JARVIS
DefaultGroupName=JARVIS
PrivilegesRequired=lowest
OutputDir=installer
OutputBaseFilename=JARVIS_Setup
SetupIconFile=jarvis.ico
UninstallDisplayIcon={app}\JARVIS.exe
Compression=lzma2/fast
SolidCompression=yes
WizardStyle=modern
DisableProgramGroupPage=yes
[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; Flags: checkedonce
[Files]
Source: "dist\JARVIS\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion
Source: "jarvis.ico"; DestDir: "{app}"; Flags: ignoreversion
[Icons]
Name: "{autoprograms}\JARVIS"; Filename: "{app}\JARVIS.exe"; IconFilename: "{app}\jarvis.ico"
Name: "{autodesktop}\JARVIS"; Filename: "{app}\JARVIS.exe"; IconFilename: "{app}\jarvis.ico"; Tasks: desktopicon
[Run]
Filename: "{app}\JARVIS.exe"; Description: "Launch JARVIS"; Flags: nowait postinstall skipifsilent
