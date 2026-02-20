@echo off
REM Build debug exe with console window (shows tracebacks)
cd /d "%~dp0"

pip install -r requirements.txt -q
pyinstaller --clean InputHogControl-Debug.spec

if %ERRORLEVEL% equ 0 (
    echo.
    echo Debug build complete. Output: dist\InputHogControl-Debug.exe
    echo Run it to see a console window with errors.
    echo Errors also logged to: dist\inputhog_debug.log
) else (
    echo Build failed.
    exit /b 1
)
