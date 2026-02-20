@echo off
REM Build InputHogControl.exe with PyInstaller
REM Requires: pip install pyinstaller

cd /d "%~dp0"

pyinstaller --clean InputHogControl.spec

if %ERRORLEVEL% equ 0 (
    echo.
    echo Build complete. Output: dist\InputHogControl.exe
) else (
    echo Build failed.
    exit /b 1
)
