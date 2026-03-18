@echo off
setlocal
cd /d %~dp0

python -m pip show pyinstaller >nul 2>&1
if errorlevel 1 (
  python -m pip install pyinstaller
)

set SPEC=YTDownloader.spec

if /i "%1"=="--no-obfuscate" goto build

python -m pip show pyarmor >nul 2>&1
if errorlevel 1 (
  python -m pip install pyarmor
)

if exist obf rmdir /s /q obf
pyarmor gen -O obf --recursive main.py downloader.py history_manager.py queue_manager.py ui_style.py
if errorlevel 1 (
  echo PyArmor failed. Falling back to non-obfuscated build.
  set SPEC=YTDownloader.spec
) else (
  set SPEC=YTDownloader_obf.spec
)

:build
pyinstaller --clean -y %SPEC%

"C:\Users\Tahsan\AppData\Local\Programs\INNOSE~1\ISCC.exe" YTDownloader.iss

endlocal
