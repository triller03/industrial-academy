<# uninstall.ps1 - removes ASAPA (Industrial Automation Training Platform) from this PC.

Removes: desktop/start-menu shortcuts, the scheduled task, the firewall rule,
and the install folder (requires -RemoveData to delete the database and
offline bundles too). Legacy "Industrial Academy" items are cleaned up as well.

Options:
  -InstallDir <path>   The folder that setup.ps1 created. Defaults to the
                       standard location: %LOCALAPPDATA%\IndustrialAcademy
  -RemoveData          Also delete the database, offline_packages/ bundles,
                       .env and logs (irreversible).
  -Force               Skip confirmation prompts.
#>
[CmdletBinding()]
param(
    [string]$InstallDir = "$env:LOCALAPPDATA\IndustrialAcademy",
    [switch]$RemoveData,
    [switch]$Force
)
$ErrorActionPreference = "Continue"

function Confirm-Yes([string]$msg, [switch]$ForceYes) {
    if ($ForceYes) { return $true }
    $r = Read-Host "$msg [y/N]"
    return $r -match "^(y|yes)$"
}

Write-Host "ASAPA uninstaller" -ForegroundColor Cyan
Write-Host "Install dir: $InstallDir"

# stop a running server first
$bat = Join-Path $InstallDir "stop-academy.bat"
if (Test-Path -LiteralPath $bat) {
    Write-Host "Stopping server..."
    Start-Process -FilePath $bat -NoNewWindow -Wait
} else {
    Write-Host "Stopping anything on port 8000..."
    foreach ($p in (Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue)) {
        Stop-Process -Id $p.OwningProcess -Force -ErrorAction SilentlyContinue
    }
}

# scheduled task (current + legacy names)
foreach ($taskName in @("ASAPA", "Industrial Academy")) {
    if (Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue) {
        if (Confirm-Yes "Remove the '$taskName' scheduled task?" -ForceYes:$Force) {
            Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
            Write-Host "  Removed scheduled task '$taskName'." -ForegroundColor Green
        }
    }
}

# firewall rule (current + legacy names)
foreach ($ruleName in @("ASAPA (TCP 8000)", "Industrial Academy (TCP 8000)")) {
    if (Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue) {
        if (Confirm-Yes "Remove the '$ruleName' firewall rule?" -ForceYes:$Force) {
            Remove-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue
            Write-Host "  Removed firewall rule '$ruleName'." -ForegroundColor Green
        }
    }
}

# shortcuts
$targets = @(
    (Join-Path ([Environment]::GetFolderPath("Desktop")) "ASAPA.lnk"),
    (Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\ASAPA\Start ASAPA.lnk"),
    (Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\ASAPA\Stop ASAPA.lnk"),
    (Join-Path ([Environment]::GetFolderPath("Desktop")) "Industrial Academy.lnk"),
    (Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Industrial Academy\Start Industrial Academy.lnk"),
    (Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Industrial Academy\Stop Industrial Academy.lnk")
)
foreach ($t in $targets) {
    if (Test-Path -LiteralPath $t) { Remove-Item -LiteralPath $t -Force; Write-Host "  Removed shortcut: $t" -ForegroundColor Green }
}
Remove-Item (Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\ASAPA") -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item (Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Industrial Academy") -Recurse -Force -ErrorAction SilentlyContinue

# install folder
if (Test-Path -LiteralPath $InstallDir) {
    if ($RemoveData -or (Confirm-Yes "Delete the install folder '$InstallDir'?" -ForceYes:$Force)) {
        Remove-Item -LiteralPath $InstallDir -Recurse -Force -ErrorAction Continue
        if (Test-Path -LiteralPath $InstallDir) {
            Write-Host "  Some files could not be deleted (file in use?). Delete '$InstallDir' manually." -ForegroundColor Yellow
        } else {
            Write-Host "  Deleted install folder." -ForegroundColor Green
        }
    } else {
        Write-Host "  Install folder kept: $InstallDir" -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "Uninstall finished." -ForegroundColor Cyan