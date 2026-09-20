<# setup.ps1 - offline installer for the AI-Powered Industrial Academy.

Run from the mounted ISO / unpacked media (setup.bat wraps this). Copies the
application to a writable location, provisions a Python virtual environment
using any system Python 3.10+ or the bundled installer, installs all
dependencies from the bundled wheels/ folder (no internet required), builds
the initial database + curriculum + offline bundles, and creates shortcuts.

Options:
  -InstallDir <path>   Destination folder. Default: %LOCALAPPDATA%\IndustrialAcademy
  -Port <int>          Server port. Default 8000
  -EnableFirewall      Add an inbound firewall rule for the server port (admin)
  -StartAtBoot         Register a scheduled task that starts the server at logon
  -SkipInit            Skip the first-run database/bundle build
  -PassThru            Print a JSON summary instead of the human banner
#>
[CmdletBinding()]
param(
    [string]$InstallDir = "$env:LOCALAPPDATA\IndustrialAcademy",
    [int]$Port = 8000,
    [switch]$EnableFirewall,
    [switch]$StartAtBoot,
    [switch]$SkipInit,
    [switch]$PassThru
)

$ErrorActionPreference = "Stop"
$Media = Split-Path -Parent $MyInvocation.MyCommand.Path
$Version = "1.0.0"

$script:steps = New-Object System.Collections.Generic.List[string]
$script:warnings = New-Object System.Collections.Generic.List[string]

function Write-Step($name, $ok, $note) {
    $entry = $name
    if ($note) { $entry = "$name ($note)" }
    $script:steps.Add($entry) | Out-Null
    if (-not $PassThru) {
        $mark = "[WARN]"
        if ($ok -eq $true) { $mark = "[ OK ]" }
        $line = "  $mark $name"
        if ($note) { $line += " - $note" }
        Write-Host $line
    }
}

# --- Python resolution ------------------------------------------------------
function Get-PyScore($candidate) {
    if (-not $candidate) { return 0 }
    if (-not (Test-Path -LiteralPath $candidate)) { return 0 }
    try {
        $vout = & $candidate -c 'import sys;print("{0}.{1}".format(sys.version_info[0],sys.version_info[1]))' 2>$null
        if ($LASTEXITCODE -ne 0) { return 0 }
        $v = [version]::Parse(($vout -join "").Trim())
        return ($v.Major * 10) + $v.Minor
    } catch {
        return 0
    }
}

function Find-SystemPython {
    $cands = New-Object System.Collections.Generic.List[string]
    $c = Get-Command py -ErrorAction SilentlyContinue
    if ($c) {
        foreach ($ver in @("3.12", "3.11", "3.10")) {
            $out = & py ("-" + $ver) -c 'import sys;print(sys.executable)' 2>$null
            if ($LASTEXITCODE -eq 0 -and $out) { $cands.Add(($out -join "").Trim()) }
        }
    }
    $c2 = Get-Command python -ErrorAction SilentlyContinue
    if ($c2) { $cands.Add($c2.Source) }
    $best = ""
    $bestScore = 0
    foreach ($cand in $cands) {
        $score = Get-PyScore $cand
        if ($score -gt $bestScore) {
            $best = $cand
            $bestScore = $score
        }
    }
    if ($best -and $bestScore -ge 31) {
        $o = New-Object PSObject
        $o | Add-Member -MemberType NoteProperty -Name Path -Value $best
        $o | Add-Member -MemberType NoteProperty -Name Score -Value $bestScore
        return $o
    }
    return $null
}

$bundledInstaller = $null
$pythonDir = Join-Path $Media "python"
if (Test-Path -LiteralPath $pythonDir) {
    $exe = Get-ChildItem -LiteralPath $pythonDir -Filter "*.exe" -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -match "amd64|win64" } | Select-Object -First 1
    if ($exe) { $bundledInstaller = $exe.FullName }
}
if (-not $bundledInstaller) {
    $exe = Get-ChildItem -LiteralPath $Media -Filter "python-*.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($exe) { $bundledInstaller = $exe.FullName }
}

$py = $null
$bundledProbe = Join-Path $env:LOCALAPPDATA "Programs\Python\Python312\python.exe"
if ($bundledInstaller) {
    if (Test-Path -LiteralPath $bundledProbe) {
        $py = $bundledProbe
        Write-Step "Python 3.12 runtime" $true "already installed (bundled)"
    } else {
        Write-Step "Installing bundled Python 3.12 runtime" $true (Split-Path $bundledInstaller -Leaf)
        $ip = Start-Process -FilePath $bundledInstaller -ArgumentList "/quiet", "InstallAllUsers=0", "Include_launcher=1", "Include_test=0", "Include_pip=1", "PrependPath=1", "Shortcuts=0" -Wait -PassThru
        if ($ip.ExitCode -ne 0) {
            $script:warnings.Add("Bundled Python installer exited with code $($ip.ExitCode).")
        }
        if (Test-Path -LiteralPath $bundledProbe) {
            $py = $bundledProbe
            Write-Step "Python 3.12 installed" $true
        }
    }
}

if (-not $py) {
    $sys = Find-SystemPython
    if ($sys) {
        $py = $sys.Path
        $major = [int]($sys.Score / 10)
        $minor = $sys.Score % 10
        Write-Step "Python runtime" $true "using system Python $major.$minor"
    } else {
        $msg = "No Python 3.10+ found and no bundled installer present. Install Python 3.12 (64-bit) from https://www.python.org/downloads/ then re-run setup.bat."
        if ($PassThru) { Write-Output (@{ ok = $false; error = $msg } | ConvertTo-Json); exit 2 }
        Write-Host ""
        Write-Host $msg -ForegroundColor Yellow
        exit 2
    }
}

# --- copy application -------------------------------------------------------
$srcApp = Join-Path $Media "app"
if (-not (Test-Path -LiteralPath $srcApp)) { $srcApp = $Media }
$failCond = -not (Test-Path -LiteralPath (Join-Path $srcApp "backend"))
$failCond = $failCond -or (-not (Test-Path -LiteralPath (Join-Path $srcApp "frontend")))
if ($failCond) {
    $msg = "Media looks incomplete: expected 'app/backend' and 'app/frontend' (or backend/ and frontend/ alongside this script)."
    if ($PassThru) { Write-Output (@{ ok = $false; error = $msg } | ConvertTo-Json); exit 2 }
    Write-Host $msg -ForegroundColor Yellow
    exit 2
}
New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
$appDir = Join-Path $InstallDir "app"
$backendDir = Join-Path $appDir "backend"
if (-not (Test-Path -LiteralPath (Join-Path $backendDir "requirements.txt"))) {
    Write-Step "Copying application files" $true $InstallDir
    robocopy $srcApp $appDir /E /NFL /NDL /NJH /NJS /NC /NS /XD .git .venv venv __pycache__ node_modules dist > $null
    if ($LASTEXITCODE -ge 8) { $script:warnings.Add("robocopy reported a copy failure.") }
} else {
    Write-Step "Application already present" $true $InstallDir
}

# --- virtual environment ----------------------------------------------------
$venvPy = Join-Path $backendDir ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $venvPy)) {
    Write-Step "Creating virtual environment" $false "python -m venv"
    & $py -m venv (Join-Path $backendDir ".venv")
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $venvPy)) {
        $msg = "Virtual environment creation failed."
        if ($PassThru) { Write-Output (@{ ok = $false; error = $msg } | ConvertTo-Json); exit 1 }
        Write-Host $msg -ForegroundColor Yellow
        exit 1
    }
    Write-Step "Virtual environment created" $true
} else {
    Write-Step "Virtual environment present" $true
}

# --- dependencies (offline from wheels/, online fallback) --------------------
$wheelsDir = Join-Path $Media "wheels"
function Install-Reqs($reqFile, $label) {
    $pipArgs = @("-m", "pip", "install")
    if (Test-Path -LiteralPath $wheelsDir) {
        $pipArgs += @("--no-index", "--find-links", $wheelsDir)
    }
    $pipArgs += @("-r", $reqFile)
    & $venvPy @pipArgs
    if ($LASTEXITCODE -eq 0) {
        Write-Step $label $true
        return $true
    }
    if (-not (Test-Path -LiteralPath $wheelsDir)) {
        Write-Step $label $false "no wheels/ on media, install failed"
        return $false
    }
    & $venvPy -m pip install -r $reqFile
    if ($LASTEXITCODE -eq 0) {
        Write-Step "$label (online fallback)" $true
        return $true
    }
    Write-Step $label $false "offline and online installs both failed"
    return $false
}

$coreOk = Install-Reqs (Join-Path $backendDir "requirements.txt") "Core dependencies"
$intOk = Install-Reqs (Join-Path $backendDir "requirements-integrations.txt") "Integration dependencies (MODBUS / S7 / OPC UA)"
if (-not $coreOk) {
    $msg = "Core dependency installation failed. Check pip output above."
    if ($PassThru) { Write-Output (@{ ok = $false; error = $msg } | ConvertTo-Json); exit 1 }
    Write-Host $msg -ForegroundColor Yellow
    exit 1
}
if (-not $intOk) {
    $script:warnings.Add("Integration dependencies were not installable; the FACTORY I/O / S7 / OPC UA links will report 'disabled'.")
}

# --- first-run init ---------------------------------------------------------
if (-not $SkipInit) {
    Write-Step "Building initial database + offline bundles" $false "python -m app.init_db"
    Push-Location $backendDir
    & $venvPy -m app.init_db
    $initOk = ($LASTEXITCODE -eq 0)
    Pop-Location
    if ($initOk) {
        Write-Step "First-run init complete" $true
    } else {
        $script:warnings.Add("init_db finished with warnings; the server will re-run init on first boot.")
    }
}

# --- shortcuts --------------------------------------------------------------
function New-Shortcut($name, $target) {
    $sh = New-Object -ComObject WScript.Shell
    $lnk = $sh.CreateShortcut($name)
    $lnk.TargetPath = $target
    $lnk.WorkingDirectory = $appDir
    $lnk.Save()
}
$desktop = [Environment]::GetFolderPath("Desktop")
$startMenu = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Industrial Academy"
$startBat = Join-Path $InstallDir "start-academy.bat"
$stopBat = Join-Path $InstallDir "stop-academy.bat"
New-Item -ItemType Directory -Path $startMenu -Force | Out-Null
New-Shortcut (Join-Path $desktop "Industrial Academy.lnk") $startBat
New-Shortcut (Join-Path $startMenu "Start Industrial Academy.lnk") $startBat
New-Shortcut (Join-Path $startMenu "Stop Industrial Academy.lnk") $stopBat
Write-Step "Shortcuts created (Desktop + Start Menu)" $true

# --- firewall ---------------------------------------------------------------
if ($EnableFirewall) {
    try {
        netsh advfirewall firewall delete rule name="Industrial Academy (TCP $Port)" | Out-Null
        netsh advfirewall firewall add rule name="Industrial Academy (TCP $Port)" dir=in action=allow protocol=TCP localport=$Port | Out-Null
        if ($LASTEXITCODE -eq 0) {
            Write-Step "Inbound firewall rule added (port $Port)" $true
        } else {
            $script:warnings.Add("Firewall rule not added (exit $LASTEXITCODE). Run as Administrator.")
        }
    } catch {
        $script:warnings.Add("Firewall rule not added: $($_.Exception.Message) Run as Administrator.")
    }
}

# --- scheduled task ---------------------------------------------------------
if ($StartAtBoot) {
    $action = New-ScheduledTaskAction -Execute $startBat
    $trigger = New-ScheduledTaskTrigger -AtLogOn
    try {
        Register-ScheduledTask -TaskName "Industrial Academy" -Action $action -Trigger $trigger -Description "Starts the Industrial Academy server at logon." -Force | Out-Null
        Write-Step "Scheduled task registered (start at logon)" $true
    } catch {
        $script:warnings.Add("Could not register scheduled task: $($_.Exception.Message)")
    }
}

# --- state & summary ---------------------------------------------------------
@{
    version      = $Version
    installed_at = (Get-Date).ToString("o")
    port         = $Port
    install_dir  = $InstallDir
    warnings     = @($script:warnings)
} | ConvertTo-Json | Set-Content -Path (Join-Path $InstallDir "install.state.json") -Encoding UTF8

$summary = @{
    ok         = $true
    version    = $Version
    installDir = $InstallDir
    url        = "http://127.0.0.1:$Port"
    steps      = @($script:steps)
    warnings   = @($script:warnings)
}
if ($PassThru) {
    Write-Output ($summary | ConvertTo-Json)
    exit 0
}

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  AI-Powered Industrial Academy  v$Version - setup complete" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  Installed to:  $InstallDir"
Write-Host "  Launch:        Desktop / Start Menu  ->  Industrial Academy"
Write-Host "  Web UI:        http://127.0.0.1:$Port"
Write-Host ""
Write-Host "  Demo account:  demo@academy.local / demo1234"
Write-Host "  Admin account: admin@academy.local / admin1234"
Write-Host "  IMPORTANT: change or disable these accounts before real use."
Write-Host "------------------------------------------------------------"
if ($script:warnings.Count -gt 0) {
    Write-Host "  Non-fatal warnings:" -ForegroundColor Yellow
    $script:warnings | ForEach-Object { Write-Host "      ! $_" -ForegroundColor Yellow }
}
$stateFile = Join-Path $InstallDir "install.state.json"
Write-Host "State: $stateFile"
exit 0