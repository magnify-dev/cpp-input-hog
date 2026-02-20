<#
.SYNOPSIS
  Test-sign the InputHog driver. Use when unsigned driver fails with error 577.

.DESCRIPTION
  Creates a test certificate, installs it, and signs the driver.
  Run as Administrator. Requires WDK (MakeCert, SignTool).
#>
[CmdletBinding()]
param(
    [string]$DriverPath = "",
    [switch]$CreateCertOnly  # Only create/install cert, don't sign
)

$ErrorActionPreference = "Stop"

# Require Administrator (for cert store writes)
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) { throw "Run as Administrator. Right-click PowerShell -> Run as administrator" }

# Find WDK tools (use latest version)
$wdkBinPath = "C:\Program Files (x86)\Windows Kits\10\bin"
$verDirs = Get-ChildItem $wdkBinPath -Directory -ErrorAction SilentlyContinue | Where-Object { $_.Name -match "^\d+\.\d+\.\d+\.\d+$" }
$wdkBin = $verDirs | Sort-Object Name -Descending | Select-Object -First 1
if (-not $wdkBin) { throw "WDK not found. Install from https://learn.microsoft.com/en-us/windows-hardware/drivers/download-the-wdk" }
$wdkX64 = Join-Path $wdkBin.FullName "x64"
$makecert = Join-Path $wdkX64 "MakeCert.exe"
$signtool = Join-Path $wdkX64 "signtool.exe"
if (-not (Test-Path $makecert)) { throw "MakeCert not found at $makecert" }
if (-not (Test-Path $signtool)) { throw "SignTool not found at $signtool" }

$certStore = "PrivateCertStore"
$certName = "InputHog(Test)"
$certFile = Join-Path $PSScriptRoot "InputHogTest.cer"

# Create test certificate (once)
if (-not (Test-Path $certFile)) {
    Write-Host "Creating test certificate..."
    & $makecert -r -pe -ss $certStore -n "CN=$certName" -eku 1.3.6.1.5.5.7.3.3 $certFile
    if ($LASTEXITCODE -ne 0) { throw "MakeCert failed" }
    Write-Host "Certificate created: $certFile"
}

# Install cert to Trusted Root and Trusted Publishers (required for kernel driver)
$cert = New-Object System.Security.Cryptography.X509Certificates.X509Certificate2($certFile)
$storeRoot = New-Object System.Security.Cryptography.X509Certificates.X509Store("Root", "LocalMachine")
$storePub = New-Object System.Security.Cryptography.X509Certificates.X509Store("TrustedPublisher", "LocalMachine")
$storeRoot.Open("ReadWrite")
$storePub.Open("ReadWrite")
try {
    if (-not ($storeRoot.Certificates | Where-Object { $_.Thumbprint -eq $cert.Thumbprint })) {
        $storeRoot.Add($cert)
        Write-Host "Added cert to Trusted Root Certification Authorities"
    }
    if (-not ($storePub.Certificates | Where-Object { $_.Thumbprint -eq $cert.Thumbprint })) {
        $storePub.Add($cert)
        Write-Host "Added cert to Trusted Publishers"
    }
} finally {
    $storeRoot.Close()
    $storePub.Close()
}

if ($CreateCertOnly) {
    Write-Host "Certificate ready. Run again without -CreateCertOnly to sign the driver."
    exit 0
}

# Find driver (same paths as setup-windows.ps1)
if ([string]::IsNullOrEmpty($DriverPath)) {
    $candidates = @(
        (Join-Path $PSScriptRoot "build\driver\InputHog.sys"),
        (Join-Path $PSScriptRoot "build\driver\Debug\InputHog.sys"),
        (Join-Path $PSScriptRoot "build\driver\Release\InputHog.sys"),
        "C:\InputHog\InputHog.sys",
        (Join-Path $PSScriptRoot "driver\bin\x64\Release\InputHog.sys"),
        (Join-Path $PSScriptRoot "driver\bin\x64\Debug\InputHog.sys")
    )
    foreach ($p in $candidates) {
        if (Test-Path -LiteralPath $p -PathType Leaf) {
            $DriverPath = $p
            break
        }
    }
    if ([string]::IsNullOrEmpty($DriverPath)) { throw "Driver not found. Build first, or pass -DriverPath" }
}
if (-not (Test-Path $DriverPath)) { throw "Driver not found: $DriverPath" }

# Sign driver
Write-Host "Signing driver: $DriverPath"
& $signtool sign /v /fd SHA256 /s $certStore /n $certName /t http://timestamp.digicert.com $DriverPath
if ($LASTEXITCODE -ne 0) { throw "SignTool failed" }
Write-Host "Driver signed successfully."
Write-Host "Now run: .\setup-windows.ps1 -EnableTestSigning"
