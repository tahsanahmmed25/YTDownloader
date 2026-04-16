param(
    [switch]$NoObfuscate
)

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

function Resolve-BuildPython {
    $venvPython = Join-Path $PSScriptRoot "venv\Scripts\python.exe"
    if (Test-Path $venvPython) {
        return (Resolve-Path $venvPython).Path
    }

    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if ($pythonCommand) {
        return $pythonCommand.Source
    }

    throw "Python was not found. Create .\venv or add python to PATH."
}

function Invoke-Python {
    param(
        [Parameter(ValueFromRemainingArguments = $true)]
        [string[]]$Arguments
    )

    & $script:PythonExe @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed: $script:PythonExe $($Arguments -join ' ')"
    }
}

function Test-PythonPackage {
    param([string]$Package)

    & $script:PythonExe -m pip show $Package *> $null
    return ($LASTEXITCODE -eq 0)
}

function Ensure-PythonPackage {
    param([string]$Package)

    if (Test-PythonPackage $Package) {
        return
    }

    Write-Host "Installing $Package into the selected interpreter..."
    Invoke-Python -m pip install $Package
}

$PythonExe = Resolve-BuildPython
Write-Host "Using Python interpreter: $PythonExe"

Invoke-Python "$PSScriptRoot\build_release_support.py" preflight
Ensure-PythonPackage "pyinstaller"

$spec = "YTDownloader.spec"

if (-not $NoObfuscate) {
    try {
        Ensure-PythonPackage "pyarmor"
        if (Test-Path "obf") {
            Remove-Item "obf" -Recurse -Force
        }
        Invoke-Python -m pyarmor gen -O obf --recursive `
            main.py downloader.py history_manager.py queue_manager.py ui_style.py
        $spec = "YTDownloader_obf.spec"
    } catch {
        Write-Warning "PyArmor failed or is unavailable. Falling back to non-obfuscated build."
        if (Test-Path "obf") {
            Remove-Item "obf" -Recurse -Force -ErrorAction SilentlyContinue
        }
        $spec = "YTDownloader.spec"
    }
}

Write-Host "Building spec: $spec"
Invoke-Python -m PyInstaller --clean -y $spec

$preferredIscc = "F:\Installed Softwares\InnoSetup\ISCC.exe"
$iscc = $null
if (Test-Path $preferredIscc) {
    $iscc = $preferredIscc
} else {
    $isccCommand = Get-Command ISCC.exe -ErrorAction SilentlyContinue
    if ($isccCommand) {
        $iscc = $isccCommand.Source
    }
}

if (-not $iscc) {
    throw "Inno Setup compiler not found. Install Inno Setup or add ISCC.exe to PATH."
}

& $iscc "$PSScriptRoot\YTDownloader.iss"
