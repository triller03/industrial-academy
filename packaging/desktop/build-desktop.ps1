<#
.SYNOPSIS
    Build the Windows desktop app + installer for the AI-Powered Industrial Academy.
.DESCRIPTION
    1. Build venv (.build-venv, core requirements + pywebview + PyInstaller + Pillow)
    2. Render the app icon (assets/app.ico via Pillow)
    3. PyInstaller one-folder --windowed bundle using launcher.py
    4. Compile the per-user Inno Setup installer (IndustrialAcademy-Setup-<version>.exe)
    Inno Setup is fetched as a portable copy under .tools\innosetup when ISCC_PATH is not set.
.PARAMETER SkipVenv
    Reuse an existing .build-venv instead of (re)creating and reinstalling.
.PARAMETER SkipInstaller
    Build the PyInstaller bundle only; do not compile the Inno Setup installer.
.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\packaging\desktop\build-desktop.ps1
#>
[CmdletBinding()]
param(
    [switch]$SkipVenv,
    [switch]$SkipInstaller
)

$ErrorActionPreference = "Stop"
$DesktopDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Resolve-Path (Join-Path $DesktopDir "..\..")

$VersionLine = Select-String -LiteralPath (Join-Path $RepoRoot "backend\app\config.py") -Pattern 'app_version\s*=\s*"([^"]+)"' | Select-Object -First 1
$Version = if ($VersionLine) { $VersionLine.Matches[0].Groups[1].Value } else { "1.0.0" }
Write-Host "== Desktop build (app version $Version) =="

$BuildDir = Join-Path $DesktopDir "dist-desktop"
$DistPkg = Join-Path $BuildDir "IndustrialAcademy"
$Venv = Join-Path $DesktopDir ".build-venv"
$ToolsDir = Join-Path $DesktopDir ".tools"

function Find-Python312 {
    $cmd = Get-Command py -ErrorAction SilentlyContinue
    if ($cmd) {
        $spec = & py -3.12 -c "import sys; print(sys.executable)" 2>$null
        if ($LASTEXITCODE -eq 0 -and $spec) { return $spec }
    }
    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python) { return $python.Source }
    throw "Python 3.12 not found. Install it or pass PYTHON via --paths."
}

$BasePython = Find-Python312
$VenvPython = Join-Path $Venv "Scripts\python.exe"

# 1. venv -------------------------------------------------------------------
if (-not (Test-Path -LiteralPath $VenvPython)) {
    Write-Host "Creating build venv: $Venv"
    & $BasePython -m venv $Venv
    if ($LASTEXITCODE -ne 0) { throw "venv creation failed" }
}
if (-not $SkipVenv) {
    Write-Host "Installing build dependencies (core requirements + pywebview + pyinstaller + pillow)..."
    & $VenvPython -m pip install --upgrade pip --quiet
    & $VenvPython -m pip install --quiet -r (Join-Path $RepoRoot "backend\requirements.txt")
    & $VenvPython -m pip install --quiet pywebview pyinstaller pillow
    if ($LASTEXITCODE -ne 0) { throw "pip install failed" }
}

# 2. icon -------------------------------------------------------------------
Write-Host "Rendering app icon..."
& $VenvPython (Join-Path $DesktopDir "assets\make_icon.py")
if ($LASTEXITCODE -ne 0) { throw "icon render failed" }

# 3. PyInstaller bundle -----------------------------------------------------
$PyInstallArgs = @(
    "--noconfirm", "--clean", "--onedir", "--windowed",
    "--name", "IndustrialAcademy",
    "--paths", (Join-Path $RepoRoot "backend"),
    "--add-data", ("{0};frontend" -f (Join-Path $RepoRoot "frontend")),
    "--icon", (Join-Path $DesktopDir "assets\app.ico"),
    "--collect-all", "uvicorn",
    "--collect-all", "webview",
    "--hidden-import", "uvicorn.logging",
    "--hidden-import", "uvicorn.loops.auto",
    "--hidden-import", "uvicorn.protocols.http.auto",
    "--hidden-import", "uvicorn.protocols.websockets.auto",
    "--hidden-import", "passlib.handlers.bcrypt",
    "--distpath", $BuildDir,
    "--workpath", (Join-Path $BuildDir "build"),
    "--specpath", $DesktopDir,
    (Join-Path $DesktopDir "launcher.py")
)
Write-Host "Running PyInstaller..."
& $VenvPython -m PyInstaller @PyInstallArgs
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }
if (-not (Test-Path -LiteralPath (Join-Path $DistPkg "IndustrialAcademy.exe"))) {
    throw "PyInstaller did not produce $DistPkg\IndustrialAcademy.exe"
}
Write-Host "Bundle: $DistPkg"

if ($SkipInstaller) { Write-Host "== Bundle ready (installer skipped) =="; exit 0 }

# 4. Inno Setup installer ----------------------------------------------------
$Iscc = $env:ISCC_PATH
$PortableSetup = Join-Path $ToolsDir "innosetup-setup.exe"
$InnoDir = Join-Path $ToolsDir "innosetup"
if (-not $Iscc) { $Iscc = Join-Path $InnoDir "ISCC.exe" }
if (-not (Test-Path -LiteralPath $Iscc)) {
    New-Item -ItemType Directory -Force -Path $ToolsDir | Out-Null
    Write-Host "Downloading portable Inno Setup..."
    [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
    Invoke-WebRequest -Uri "https://github.com/jrsoftware/issrc/releases/download/is-6_7_3/innosetup-6.7.3.exe" -OutFile $PortableSetup -UseBasicParsing
    Write-Host "Installing portable Inno Setup to $InnoDir ..."
    & $PortableSetup "/PORTABLE" ("/DIR=" + $InnoDir) "/VERYSILENT" "/SUPPRESSMSGBOXES" "/NORESTART"
    if (-not (Test-Path -LiteralPath $Iscc)) {
        throw "Portable Inno Setup failed. Set ISCC_PATH to a valid ISCC.exe and retry."
    }
}
Write-Host "Using ISCC: $Iscc"

$IssFile = Join-Path $DesktopDir "installer.iss"
$IssText = Get-Content -LiteralPath $IssFile -Raw
$IssText = $IssText -replace '#define MyAppVersion ".*?"', ('#define MyAppVersion "' + $Version + '"')
Set-Content -LiteralPath $IssFile -Value $IssText -Encoding ASCII

Write-Host "Compiling installer..."
& $Iscc $IssFile
$SetupExe = Join-Path $DesktopDir ("dist-desktop\IndustrialAcademy-Setup-" + $Version + ".exe")
if (-not (Test-Path -LiteralPath $SetupExe)) {
    throw "ISCC did not produce $SetupExe"
}
$SizeMb = [math]::Round((Get-Item -LiteralPath $SetupExe).Length / 1MB, 1)
Write-Host "== Installer ready: $SetupExe ($SizeMb MB) =="