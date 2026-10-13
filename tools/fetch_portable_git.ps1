#Requires -Version 5.1
<#
.SYNOPSIS
  Скачивает MinGit (portable git) в vendor/portable-git для installer.iss.
  Запуск из корня проекта: powershell -ExecutionPolicy Bypass -File tools/fetch_portable_git.ps1
#>
$ErrorActionPreference = "Stop"
$Version = "2.47.1.windows.1"
$Url = "https://github.com/git-for-windows/git/releases/download/v$Version/MinGit-2.47.1-64-bit.zip"
$Root = Split-Path -Parent $PSScriptRoot
$Vendor = Join-Path $Root "vendor\portable-git"
$Zip = Join-Path $env:TEMP "MinGit-2.47.1-64-bit.zip"

if (Test-Path $Vendor) { Remove-Item -Recurse -Force $Vendor }
New-Item -ItemType Directory -Force -Path $Vendor | Out-Null
Write-Host "Downloading $Url ..."
Invoke-WebRequest -Uri $Url -OutFile $Zip
Write-Host "Extracting to $Vendor ..."
Expand-Archive -Path $Zip -DestinationPath $Vendor -Force
Remove-Item -Force $Zip
$GitExe = Join-Path $Vendor "cmd\git.exe"
if (-not (Test-Path $GitExe)) { throw "git.exe not found after extract" }
Write-Host "OK: $GitExe"
& $GitExe --version
