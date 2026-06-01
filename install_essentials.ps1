param(
    [string]$TargetDir = ""
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

if ([string]::IsNullOrWhiteSpace($TargetDir)) {
    $TargetDir = Split-Path -Parent $MyInvocation.MyCommand.Path
}

if (-not (Test-Path $TargetDir)) {
    New-Item -ItemType Directory -Path $TargetDir | Out-Null
}

try {
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
}
catch {
}

function DownloadFile($Url, $Destination) {
    Write-Host "Downloading $Url"
    if (-not ($Url -like "https://*")) {
        throw "Refusing non-HTTPS download URL: $Url"
    }
    Invoke-WebRequest -Uri $Url -OutFile $Destination -UseBasicParsing
}

$ffmpegTarget = Join-Path $TargetDir "ffmpeg.exe"
$ffprobeTarget = Join-Path $TargetDir "ffprobe.exe"

$ffmpegUrl = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
$localTmp = Join-Path $TargetDir ".data\YTDownloaderPro\.tmp"
if (-not (Test-Path $localTmp)) {
    New-Item -ItemType Directory -Path $localTmp -Force | Out-Null
}
$zipPath = Join-Path $localTmp "ffmpeg-release-essentials.zip"
$extractDir = Join-Path $localTmp "ffmpeg-essentials"

if (Test-Path $extractDir) {
    Remove-Item -Recurse -Force $extractDir
}

DownloadFile $ffmpegUrl $zipPath
$expectedHash = $env:YTDL_FFMPEG_WIN_ZIP_SHA256
if (-not $expectedHash -or $expectedHash -notmatch '^[a-fA-F0-9]{64}$') {
    throw "Set YTDL_FFMPEG_WIN_ZIP_SHA256 to the expected ffmpeg-release-essentials.zip SHA256 before running this script."
}
$actualHash = (Get-FileHash $zipPath -Algorithm SHA256).Hash.ToLower()
if ($actualHash -ne $expectedHash.ToLower()) {
    Remove-Item $zipPath -Force -ErrorAction SilentlyContinue
    throw "FFmpeg archive SHA256 mismatch. Expected $expectedHash but got $actualHash."
}
Expand-Archive -Path $zipPath -DestinationPath $extractDir -Force

$ffmpegExe = Get-ChildItem -Path $extractDir -Recurse -Filter "ffmpeg.exe" | Select-Object -First 1
$ffprobeExe = Get-ChildItem -Path $extractDir -Recurse -Filter "ffprobe.exe" | Select-Object -First 1

if ($ffmpegExe) {
    Copy-Item $ffmpegExe.FullName (Join-Path $TargetDir "ffmpeg.exe") -Force
}

if ($ffprobeExe) {
    Copy-Item $ffprobeExe.FullName (Join-Path $TargetDir "ffprobe.exe") -Force
}

if (Test-Path $zipPath) {
    Remove-Item $zipPath -Force
}

if (Test-Path $extractDir) {
    Remove-Item -Recurse -Force $extractDir
}
