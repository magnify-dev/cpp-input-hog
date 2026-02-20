<#
.SYNOPSIS
  Build the InputHog driver with CMake. Stops the driver service first so the .sys file can be overwritten.
#>
param([ValidateSet("Debug", "Release")][string]$Config = "Debug")

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot

# Stop driver if running (unlocks InputHog.sys)
$svc = Get-Service -Name "InputHog" -ErrorAction SilentlyContinue
if ($svc -and $svc.Status -eq "Running") {
    Write-Host "Stopping InputHog driver..."
    Stop-Service -Name "InputHog" -Force
    Start-Sleep -Seconds 2
}

$buildDir = Join-Path $root "build"
$preset = if ($Config -eq "Debug") { "x64-debug" } else { "x64-release" }

Write-Host "Configuring CMake (preset: $preset)..."
Set-Location $root
cmake --preset $preset
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "If Ninja was mentioned: delete build dir and retry: Remove-Item -Recurse -Force build"
    exit $LASTEXITCODE
}

Write-Host "Building..."
Set-Location $root
cmake --build build --config $Config
$exitCode = $LASTEXITCODE
Set-Location $root

if ($exitCode -eq 0) {
    $sysPath = Join-Path $buildDir "driver\InputHog.sys"
    Write-Host ""
    Write-Host "Build complete: $sysPath"
} else {
    Write-Host ""
    Write-Host "If LNK1104 persists: close the controller app, pause OneDrive sync, or check antivirus."
    exit $exitCode
}
