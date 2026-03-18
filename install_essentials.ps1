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
} catch {
}

function DownloadFile($Url, $Destination) {
    Write-Host "Downloading $Url"
    Invoke-WebRequest -Uri $Url -OutFile $Destination -UseBasicParsing
}

$ffmpegTarget = Join-Path $TargetDir "ffmpeg.exe"
$ffprobeTarget = Join-Path $TargetDir "ffprobe.exe"

$ffmpegUrl = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
$zipPath = Join-Path $env:TEMP "ffmpeg-release-essentials.zip"
$extractDir = Join-Path $env:TEMP "ffmpeg-essentials"

if (Test-Path $extractDir) {
    Remove-Item -Recurse -Force $extractDir
}

DownloadFile $ffmpegUrl $zipPath
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
