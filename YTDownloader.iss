[Setup]
AppName=YTDownloader
AppVersion=1.0.0
AppPublisher=Tahsan
AppPublisherURL=https://github.com/yourusername/YTDownloader
AppSupportURL=https://github.com/yourusername/YTDownloader/issues
AppUpdatesURL=https://github.com/yourusername/YTDownloader/releases
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
CreateAppDir=yes
ShowLanguageDialog=no

[Files]
Source: "dist\YTDownloader\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion
Source: "install_essentials.ps1"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\YTDownloader"; Filename: "{app}\YTDownloader.exe"
Name: "{group}\Uninstall YTDownloader"; Filename: "{uninstallexe}"

[Run]
Filename: "{sys}\WindowsPowerShell\v1.0\powershell.exe"; Parameters: "-ExecutionPolicy Bypass -File ""{app}\install_essentials.ps1"" -TargetDir ""{app}"""; Flags: runhidden waituntilterminated
Filename: "{app}\YTDownloader.exe"; Description: "Launch YTDownloader"; Flags: postinstall nowait skipifsilent

[UninstallDelete]
Type: files; Name: "{app}\ffmpeg.exe"
Type: files; Name: "{app}\ffprobe.exe"
Type: filesandordirs; Name: "{localappdata}\YTDownloader"
