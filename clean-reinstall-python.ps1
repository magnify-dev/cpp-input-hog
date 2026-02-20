# Clean Python & Conda Reinstall Script
# Run this script in an elevated (Administrator) PowerShell for full cleanup

$ErrorActionPreference = "Stop"

Write-Host "=== Step 1: Remove Conda/Python from PATH ===" -ForegroundColor Cyan
$machinePath = [Environment]::GetEnvironmentVariable('Path', 'Machine')
$pathEntries = $machinePath -split ';' | Where-Object { 
    $_ -and $_ -notmatch 'Python\\Python39|miniconda3|conda|Anaconda' 
}
$newMachinePath = ($pathEntries | Where-Object { $_ }) -join ';'
if ($newMachinePath -ne $machinePath) {
    try {
        [Environment]::SetEnvironmentVariable('Path', $newMachinePath, 'Machine')
        Write-Host "Removed Python/Conda from Machine PATH" -ForegroundColor Green
    } catch {
        Write-Host "Could not modify Machine PATH (need Admin?). Run PowerShell as Administrator." -ForegroundColor Yellow
    }
} else {
    Write-Host "No Python/Conda entries in Machine PATH" -ForegroundColor Gray
}

Write-Host "`n=== Step 2: Delete old Python installation ===" -ForegroundColor Cyan
$pythonPath = "C:\Users\timvu\AppData\Local\Programs\Python\Python39"
if (Test-Path $pythonPath) {
    Remove-Item -Path $pythonPath -Recurse -Force
    Write-Host "Deleted: $pythonPath" -ForegroundColor Green
} else {
    Write-Host "Python39 folder not found (already removed)" -ForegroundColor Gray
}

Write-Host "`n=== Step 3: Delete Miniconda (if exists) ===" -ForegroundColor Cyan
$condaPath = "C:\Users\timvu\miniconda3"
if (Test-Path $condaPath) {
    Remove-Item -Path $condaPath -Recurse -Force
    Write-Host "Deleted: $condaPath" -ForegroundColor Green
} else {
    Write-Host "Miniconda folder not found" -ForegroundColor Gray
}

Write-Host "`n=== Step 4: Download and install Python 3.12 ===" -ForegroundColor Cyan
$pythonUrl = "https://www.python.org/ftp/python/3.12.7/python-3.12.7-amd64.exe"
$installerPath = "$env:TEMP\python-3.12.7-amd64.exe"

try {
    Invoke-WebRequest -Uri $pythonUrl -OutFile $installerPath -UseBasicParsing
    Write-Host "Downloaded Python 3.12.12" -ForegroundColor Green
} catch {
    Write-Host "Download failed. Please download manually from: $pythonUrl" -ForegroundColor Red
    exit 1
}

Write-Host "Installing Python (this may take a minute)..." -ForegroundColor Yellow
$proc = Start-Process -FilePath $installerPath -ArgumentList "/quiet InstallAllUsers=0 PrependPath=1" -Wait -PassThru
if ($proc.ExitCode -ne 0) {
    Write-Host "Installer returned exit code: $($proc.ExitCode)" -ForegroundColor Yellow
}

Remove-Item $installerPath -Force -ErrorAction SilentlyContinue

Write-Host "`n=== Step 5: Refresh PATH and install project dependencies ===" -ForegroundColor Cyan
# Refresh environment variables in current session
$env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' + [Environment]::GetEnvironmentVariable('Path', 'User')

$pythonExe = "C:\Users\timvu\AppData\Local\Programs\Python\Python312\python.exe"
$pipExe = "C:\Users\timvu\AppData\Local\Programs\Python\Python312\Scripts\pip.exe"

if (Test-Path $pythonExe) {
    Write-Host "Python installed at: $pythonExe" -ForegroundColor Green
    & $pythonExe --version
    
    $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
    $requirementsPath = Join-Path $scriptDir "controller\requirements.txt"
    
    if (Test-Path $requirementsPath) {
        Write-Host "`nInstalling project dependencies (pyinstaller)..." -ForegroundColor Yellow
        & $pipExe install -r $requirementsPath
        Write-Host "`nDone! Python and dependencies are ready." -ForegroundColor Green
    } else {
        Write-Host "requirements.txt not found at $requirementsPath" -ForegroundColor Yellow
    }
} else {
    Write-Host "Python executable not found. You may need to open a NEW terminal for PATH to take effect." -ForegroundColor Yellow
    Write-Host "Then run: pip install -r controller\requirements.txt" -ForegroundColor Yellow
}

Write-Host "`n=== IMPORTANT ===" -ForegroundColor Cyan
Write-Host "Close and reopen your terminal (or IDE) for PATH changes to take full effect." -ForegroundColor White
