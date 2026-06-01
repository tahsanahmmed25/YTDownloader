@echo off
setlocal
cd /d %~dp0

set "PYTHON_EXE=%~dp0venv\Scripts\python.exe"
if exist "%PYTHON_EXE%" goto python_ready

set "PYTHON_EXE=%~dp0.venv\Scripts\python.exe"
if exist "%PYTHON_EXE%" goto python_ready

set "PYTHON_EXE="
for /f "delims=" %%I in ('where python 2^>nul') do if not defined PYTHON_EXE set "PYTHON_EXE=%%I"
if not defined PYTHON_EXE (
  echo Python was not found. Create .\venv or .\.venv or add python to PATH.
  exit /b 1
)

:python_ready
echo Using Python interpreter: %PYTHON_EXE%
"%PYTHON_EXE%" -m pip install -r "%~dp0requirements-dev.lock"
if errorlevel 1 exit /b %errorlevel%
"%PYTHON_EXE%" "%~dp0build_release_support.py" preflight
if errorlevel 1 exit /b %errorlevel%

call :ensure_package pyinstaller
if errorlevel 1 exit /b %errorlevel%
"%PYTHON_EXE%" -m pytest
if errorlevel 1 exit /b %errorlevel%

set SPEC=YTDownloaderPro.spec

if /i "%1"=="--no-obfuscate" goto build

call :ensure_package pyarmor
if errorlevel 1 (
  echo PyArmor is unavailable. Falling back to non-obfuscated build.
  set SPEC=YTDownloaderPro.spec
) else (
  if exist obf rmdir /s /q obf
  "%PYTHON_EXE%" -m pyarmor gen -O obf --recursive main.py downloader.py history_manager.py queue_manager.py ui_style.py
  if errorlevel 1 (
    echo PyArmor failed. Falling back to non-obfuscated build.
    if exist obf rmdir /s /q obf
    set SPEC=YTDownloaderPro.spec
  ) else (
    set SPEC=YTDownloaderPro_obf.spec
  )
)

:build
echo Building spec: %SPEC%
"%PYTHON_EXE%" -m PyInstaller --clean -y %SPEC%
if errorlevel 1 exit /b %errorlevel%

set "ISCC="
if exist "F:\Installed Softwares\InnoSetup\ISCC.exe" set "ISCC=F:\Installed Softwares\InnoSetup\ISCC.exe"
if not defined ISCC (
  for /f "delims=" %%I in ('where ISCC.exe 2^>nul') do if not defined ISCC set "ISCC=%%I"
)
if not defined ISCC (
  echo Inno Setup compiler not found. Install Inno Setup or add ISCC.exe to PATH.
  exit /b 1
)

"%ISCC%" YTDownloaderPro.iss
if errorlevel 1 exit /b %errorlevel%

if exist "dist_installer\YTDownloaderPro-Setup.exe" (
  for /f "tokens=1" %%H in ('certutil -hashfile "dist_installer\YTDownloaderPro-Setup.exe" SHA256 ^| findstr /r "^[0-9A-Fa-f][0-9A-Fa-f]"') do (
    echo %%H  YTDownloaderPro-Setup.exe> "dist_installer\SHA256SUMS-windows.txt"
  )
)

endlocal
goto :eof

:ensure_package
"%PYTHON_EXE%" -m pip show %~1 >nul 2>&1
if not errorlevel 1 exit /b 0
echo %~1 is missing. Install pinned dependencies first: "%PYTHON_EXE%" -m pip install -r requirements-dev.lock
exit /b 1
