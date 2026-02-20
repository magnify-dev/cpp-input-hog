[CmdletBinding()]
param(
    [string]$DriverPath = "",  # Auto-detect: CMake build first, then VS
    [string]$AppPath = (Join-Path $PSScriptRoot "controller\dist\InputHogControl.exe"),
    [switch]$EnableTestSigning,
    [switch]$SkipAppLaunch,
    [switch]$TestSigningOnly  # Only enable test signing; skip driver install
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Assert-Admin {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw "Run this script from an elevated PowerShell session (Run as administrator)."
    }
}

function Get-TestSigningEnabled {
    $output = & bcdedit /enum 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to query boot configuration with bcdedit."
    }
    return (($output | Out-String) -match "testsigning\s+Yes")
}

function Ensure-DriverService {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ServiceName,
        [Parameter(Mandatory = $true)]
        [string]$BinaryPath
    )

    $scExe = Join-Path $env:SystemRoot "System32\sc.exe"
    # Stop and delete existing service so we always create fresh with correct path
    $queryOut = & $scExe query $ServiceName 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Removing existing service '$ServiceName'..."
        & $scExe stop $ServiceName 2>&1 | Out-Null
        Start-Sleep -Seconds 1
        & $scExe delete $ServiceName 2>&1 | Out-Null
        Start-Sleep -Seconds 2
    }

    # Create with explicit path. Use & sc.exe to avoid PowerShell's 'sc' alias for Set-Content.
    Write-Host "Creating driver service '$ServiceName'..."
    $scArgs = "create", $ServiceName, "type=", "kernel", "start=", "demand", "binPath=", $BinaryPath
    $out = & $scExe $scArgs 2>&1 | Out-String
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to create service '$ServiceName'. $out"
    }
}

function Ensure-DriverStarted {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ServiceName
    )

    $scExe = Join-Path $env:SystemRoot "System32\sc.exe"
    Write-Host "Starting driver service '$ServiceName'..."
    $startOutput = & $scExe start $ServiceName 2>&1
    $exitCode = $LASTEXITCODE

    if ($exitCode -eq 0) {
        return
    }

    $startText = ($startOutput | Out-String)
    if ($startText -match "1056") {
        Write-Host "Driver service '$ServiceName' is already running."
        return
    }

    throw "Failed to start service '$ServiceName'. Output: $startText"
}

Assert-Admin

Write-Host "InputHog setup started..."

if ($EnableTestSigning) {
    if (Get-TestSigningEnabled) {
        Write-Host "Test signing is already enabled."
    } else {
        Write-Host "Enabling test signing..."
        $bcdOutput = & bcdedit /set testsigning on 2>&1 | Out-String
        $bcdExit = $LASTEXITCODE

        # bcdedit may not set exit code on failure; check output and re-verify
        $hasError = $bcdOutput -match "Access is denied|The system cannot find|denied|error|Error|protected by Secure Boot"
        $stillDisabled = -not (Get-TestSigningEnabled)

        if ($bcdExit -ne 0 -or $hasError -or $stillDisabled) {
            Write-Error "Failed to enable test signing."
            Write-Host ""
            Write-Host "bcdedit output: $bcdOutput"
            Write-Host ""

            if ($bcdOutput -match "Secure Boot") {
                Write-Host "Secure Boot is blocking test signing. You must disable it in BIOS/UEFI:"
                Write-Host "  1. Restart and enter BIOS (usually Del, F2, F12, or Esc during boot)"
                Write-Host "  2. Find 'Secure Boot' under Security or Boot options"
                Write-Host "  3. Set Secure Boot to Disabled"
                Write-Host "  4. Save and exit, then run this script again"
            } else {
                Write-Host "Common fixes:"
                Write-Host "  1. Disable Secure Boot in BIOS/UEFI"
                Write-Host "  2. Disable Memory Integrity: Settings > Privacy & Security > Windows Security > Device security > Core isolation"
                Write-Host "  3. Try from elevated CMD:  bcdedit /set testsigning on"
            }
            throw "Failed to enable test signing."
        }
        Write-Warning "Test signing was enabled. Reboot Windows before loading unsigned test drivers."
    }
}

if ($TestSigningOnly) {
    Write-Host "Test signing step complete."
    exit 0
}

# Auto-detect driver path if not specified
if ([string]::IsNullOrEmpty($DriverPath)) {
    $candidates = @(
        (Join-Path $PSScriptRoot "build\driver\InputHog.sys"),
        (Join-Path $PSScriptRoot "build\driver\Debug\InputHog.sys"),
        (Join-Path $PSScriptRoot "build\driver\Release\InputHog.sys"),
        (Join-Path $PSScriptRoot "driver\bin\x64\Release\InputHog.sys"),
        (Join-Path $PSScriptRoot "driver\bin\x64\Debug\InputHog.sys")
    )
    foreach ($p in $candidates) {
        if (Test-Path -LiteralPath $p -PathType Leaf) {
            $DriverPath = $p
            Write-Host "Using driver: $DriverPath"
            break
        }
    }
    if ([string]::IsNullOrEmpty($DriverPath)) { $DriverPath = $candidates[0] }
}

if (-not (Test-Path -LiteralPath $DriverPath -PathType Leaf)) {
    Write-Error "Driver binary not found: $DriverPath"
    Write-Host ""
    Write-Host "Build the driver first:"
    Write-Host "  1. Open InputHog.sln in Visual Studio (with WDK installed)"
    Write-Host "  2. Select x64, Release configuration"
    Write-Host "  3. Build Solution (F7)"
    Write-Host "  Output: driver\bin\x64\Release\InputHog.sys"
    throw "Driver binary not found."
}

# Copy driver to a stable path (avoids OneDrive/sync paths that fail with error 123)
$InstallDir = "C:\InputHog"
$InstallPath = Join-Path $InstallDir "InputHog.sys"
if (-not (Test-Path $InstallDir)) { New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null }
Write-Host "Copying driver to $InstallPath (avoids OneDrive path issues)..."
Copy-Item -LiteralPath $DriverPath -Destination $InstallPath -Force
$DriverPath = $InstallPath

if (-not (Test-Path -LiteralPath $AppPath -PathType Leaf)) {
    Write-Error "Controller executable not found: $AppPath"
    Write-Host ""
    Write-Host "Build the controller:  cd controller && pip install -r requirements.txt && build.bat"
    throw "Controller executable not found."
}

Ensure-DriverService -ServiceName "InputHog" -BinaryPath $DriverPath
Ensure-DriverStarted -ServiceName "InputHog"

Write-Host "Driver is installed and running."

if (-not $SkipAppLaunch) {
    Write-Host "Launching controller app..."
    Start-Process -FilePath $AppPath
}

Write-Host "Setup complete."
