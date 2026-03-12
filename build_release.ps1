param(
    [switch]$NoObfuscate
)

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

python -m pip show pyinstaller *> $null
if ($LASTEXITCODE -ne 0) {
    python -m pip install pyinstaller
}

$spec = "YTDownloader.spec"

if (-not $NoObfuscate) {
    python -m pip show pyarmor *> $null
    if ($LASTEXITCODE -ne 0) {
        python -m pip install pyarmor
    }
    if (Test-Path "obf") {
        Remove-Item "obf" -Recurse -Force
    }
    try {
        pyarmor gen -O obf --recursive `
            main.py downloader.py history_manager.py queue_manager.py ui_style.py
        $spec = "YTDownloader_obf.spec"
    } catch {
        Write-Warning "PyArmor failed. Falling back to non-obfuscated build."
        $spec = "YTDownloader.spec"
    }
}

python -m pyinstaller --clean -y $spec

$iscc = "C:\Users\Tahsan\AppData\Local\Programs\INNOSE~1\ISCC.exe"
if (-not (Test-Path $iscc)) {
    $iscc = "ISCC.exe"
}
& $iscc "$PSScriptRoot\YTDownloader.iss"
