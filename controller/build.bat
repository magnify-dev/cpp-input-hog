@echo off
REM Build InputHogControl.exe with PyInstaller
REM Requires: pip install pyinstaller

cd /d "%~dp0"

REM Close any running instance so PyInstaller can overwrite the exe
taskkill /F /IM InputHogControl.exe 2>nul
taskkill /F /IM InputHogControl-Debug.exe 2>nul
timeout /t 1 /nobreak >nul

pyinstaller --clean InputHogControl.spec

if %ERRORLEVEL% equ 0 (
    echo.
    echo Build complete. Output: dist\InputHogControl.exe
) else (
    echo Build failed.
    exit /b 1
)
