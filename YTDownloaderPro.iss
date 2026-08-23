[Setup]
AppName=YTDownloaderPro
AppVersion=3.1.1
AppVerName=YTDownloaderPro 3.1.1
AppPublisher=Tahsan Ahmmed
AppPublisherURL=https://github.com/tahsanahmmed25/YTDownloaderPro
AppSupportURL=https://github.com/tahsanahmmed25/YTDownloaderPro/issues
AppUpdatesURL=https://github.com/tahsanahmmed25/YTDownloaderPro/releases
AppCopyright=Copyright (C) 2024-2026 Tahsan Ahmmed
VersionInfoVersion=3.1.1.0
VersionInfoCompany=Tahsan Ahmmed
VersionInfoDescription=YTDownloaderPro - YouTube Video Downloader
VersionInfoProductName=YTDownloaderPro
DefaultDirName={localappdata}\Programs\YTDownloaderPro
DefaultGroupName=YTDownloaderPro
OutputDir=dist_installer
OutputBaseFilename=YTDownloaderPro-Setup
Compression=lzma
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64
PrivilegesRequired=lowest
WizardStyle=modern
UninstallDisplayIcon={app}\YTDownloaderPro.exe
LicenseFile=LICENSE
DisableProgramGroupPage=yes
DisableDirPage=no
DirExistsWarning=no
CreateAppDir=yes
ShowLanguageDialog=no
SetupLogging=yes
DisableWelcomePage=no
DisableReadyPage=no

[Files]
; Main application bundle (everything PyInstaller produced)
Source: "dist\YTDownloaderPro\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion createallsubdirs

; yt-dlp.exe — required for all downloads (MUST be present alongside the app)
Source: "yt-dlp.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\YTDownloaderPro"; Filename: "{app}\YTDownloaderPro.exe"; IconFilename: "{app}\icons\download.ico"
Name: "{group}\Uninstall YTDownloaderPro"; Filename: "{uninstallexe}"
Name: "{userdesktop}\YTDownloaderPro"; Filename: "{app}\YTDownloaderPro.exe"; IconFilename: "{app}\icons\download.ico"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional icons:"

[Run]
Filename: "{app}\YTDownloaderPro.exe"; Description: "Launch YTDownloaderPro"; Flags: postinstall nowait skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}\.data"
