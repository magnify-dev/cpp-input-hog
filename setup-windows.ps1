[CmdletBinding()]
param(
    [string]$DriverPath = (Join-Path $PSScriptRoot "driver\bin\x64\Release\InputHog.sys"),
    [string]$AppPath = (Join-Path $PSScriptRoot "controller\dist\InputHogControl.exe"),
    [switch]$EnableTestSigning,
    [switch]$SkipAppLaunch
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

    $existing = Get-CimInstance Win32_SystemDriver -Filter "Name='$ServiceName'" -ErrorAction SilentlyContinue
    $quotedPath = '"' + $BinaryPath + '"'

    if ($null -eq $existing) {
        Write-Host "Creating driver service '$ServiceName'..."
        & sc.exe create $ServiceName type= kernel start= demand binPath= $quotedPath | Out-Null
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to create service '$ServiceName'."
        }
    } else {
        Write-Host "Updating driver service '$ServiceName' binPath..."
        & sc.exe config $ServiceName type= kernel start= demand binPath= $quotedPath | Out-Null
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to update service '$ServiceName'."
        }
    }
}

function Ensure-DriverStarted {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ServiceName
    )

    Write-Host "Starting driver service '$ServiceName'..."
    $startOutput = & sc.exe start $ServiceName 2>&1
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
        & bcdedit /set testsigning on | Out-Null
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to enable test signing."
        }
        Write-Warning "Test signing was enabled. Reboot Windows before loading unsigned test drivers."
    }
}

if (-not (Test-Path -LiteralPath $DriverPath -PathType Leaf)) {
    throw "Driver binary not found: $DriverPath"
}

if (-not (Test-Path -LiteralPath $AppPath -PathType Leaf)) {
    throw "Controller executable not found: $AppPath"
}

Ensure-DriverService -ServiceName "InputHog" -BinaryPath $DriverPath
Ensure-DriverStarted -ServiceName "InputHog"

Write-Host "Driver is installed and running."

if (-not $SkipAppLaunch) {
    Write-Host "Launching controller app..."
    Start-Process -FilePath $AppPath
}

Write-Host "Setup complete."
