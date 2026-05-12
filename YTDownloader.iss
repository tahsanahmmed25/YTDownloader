[Setup]
AppName=YTDownloader
AppVersion=2.2.0
AppVerName=YTDownloader 2.2.0
AppPublisher=Tahsan
AppPublisherURL=https://github.com/tahsanahmmed25/YTDownloader
AppSupportURL=https://github.com/tahsanahmmed25/YTDownloader/issues
AppUpdatesURL=https://github.com/tahsanahmmed25/YTDownloader/releases
AppCopyright=Copyright (C) 2024-2026 Tahsan
VersionInfoVersion=2.2.0.0
VersionInfoCompany=Tahsan
VersionInfoDescription=YTDownloader - YouTube Video Downloader
VersionInfoProductName=YTDownloader
DefaultDirName={localappdata}\Programs\YTDownloader
DefaultGroupName=YTDownloader
OutputDir=dist_installer
OutputBaseFilename=YTDownloader-Setup
Compression=lzma
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64
PrivilegesRequired=lowest
WizardStyle=modern
UninstallDisplayIcon={app}\YTDownloader.exe
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
Source: "dist\YTDownloader\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion createallsubdirs

; yt-dlp.exe — required for all downloads (MUST be present alongside the app)
Source: "yt-dlp.exe"; DestDir: "{app}"; Flags: ignoreversion

; FFmpeg binaries — required for merging video+audio streams into MP4/MKV
Source: "ffmpeg.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "ffprobe.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\YTDownloader"; Filename: "{app}\YTDownloader.exe"; IconFilename: "{app}\icons\download.ico"
Name: "{group}\Uninstall YTDownloader"; Filename: "{uninstallexe}"
Name: "{commondesktop}\YTDownloader"; Filename: "{app}\YTDownloader.exe"; IconFilename: "{app}\icons\download.ico"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional icons:"

[Run]
Filename: "{app}\YTDownloader.exe"; Description: "Launch YTDownloader"; Flags: postinstall nowait skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}\.data"
