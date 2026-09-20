<# Build-Iso.ps1 â€” builds the offline installer ISO for the AI-Powered Industrial Academy.

Produces dist\Industrial-Academy-<version>-setup-x64.iso containing:

    setup.bat / setup.ps1        offline installer (+ start/stop/uninstall scripts)
    INSTALL.txt, AUTORUN.INF     no-auto-run media with shell docs
    app\backend, app\frontend    the full application (venv/db/bundles excluded)
    docs\                        README, SECURITY, CURRICULUM, .env.example
    wheels\                      every dependency as a wheel (offline pip install)
    python\                      python-3.12.10-amd64.exe (silent runtime install)
    CHECKSUMS.txt                sha256s of every file on the media

No third-party ISO tools are required: the image is written through the IMAPI2
filesystem COM interface that ships with Windows (IMAPI2FS.MsftFileSystemImage).

Options:
  -NoWheelDownload   Skip pip download; reuse wheels already staged on the media.
  -SkipIso           Stage the media tree only (no ISO image).
  -ShowProgress       Extra output from robocopy / pip.
#>
[CmdletBinding()]
param(
    [switch]$NoWheelDownload,
    [switch]$SkipIso,
    [switch]$ShowProgress
)
$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$SetupDir = Join-Path $Root "packaging\setup"
$DistDir  = Join-Path $Root "dist"
$CacheDir = Join-Path $DistDir "cache"

# ---- version ---------------------------------------------------------------
$configFile = Join-Path $Root "backend\app\config.py"
$version = "1.0.0"
if (Test-Path -LiteralPath $configFile) {
    $m = [regex]::Match((Get-Content -Raw -LiteralPath $configFile), 'app_version\s*=\s*"([^"]+)"')
    if ($m.Success) { $version = $m.Groups[1].Value }
}
Write-Host "Building Industrial-Academy v$version offline ISO" -ForegroundColor Cyan

$Media = Join-Path $DistDir "staging\Industrial-Academy-$version"
if (-not $SkipIso) { New-Item -ItemType Directory -Path $DistDir -Force | Out-Null }
New-Item -ItemType Directory -Path $CacheDir -Force | Out-Null

# ---- wipe + refresh media tree ---------------------------------------------
if (Test-Path -LiteralPath $Media) { Remove-Item -LiteralPath $Media -Recurse -Force }
New-Item -ItemType Directory -Path $Media -Force | Out-Null
$Job = [System.Collections.Generic.List[string]]::new()
function Log($msg) { $Job.Add($msg) | Out-Null; if ($ShowProgress) { Write-Host "  $msg" } }

# installer/support scripts at media root
Copy-Item (Join-Path $SetupDir "*") $Media -Recurse -Force
Log "staged setup scripts"

# application tree (backend + frontend)
$robocopy = 'robocopy.exe'
$q = @("/NFL","/NDL","/NJH","/NJS","/NC","/NS")
$bkin = @("/XD",".git",".venv","venv","__pycache__","node_modules",".pytest_cache","dist","offline_packages","tests","seeds",
          "/XF","*.db","*.sqlite3",".env","*.log","*.pyc","*.pyo")
& $robocopy (Join-Path $Root "backend") (Join-Path $Media "app\backend") /E $q $bkin
& $robocopy (Join-Path $Root "frontend") (Join-Path $Media "app\frontend") /E $q @("/XD","node_modules")
Log "staged backend + frontend"

# docs
New-Item -ItemType Directory -Path (Join-Path $Media "docs") -Force | Out-Null
foreach ($d in @("README.md","SECURITY.md","CURRICULUM.md")) {
    $p = Join-Path $Root $d
    if (Test-Path -LiteralPath $p) { Copy-Item $p (Join-Path $Media "docs") -Force }
}
$envSample = Join-Path $Root ".env.example"
if (Test-Path -LiteralPath $envSample) { Copy-Item $envSample (Join-Path $Media "docs") -Force }
Log "staged docs"

# ---- wheels ----------------------------------------------------------------
$WheelCache = Join-Path $CacheDir "wheels-$version"
$stagedWheels = Join-Path $Media "wheels"
$reqFiles = @((Join-Path $Root "backend\requirements.txt"),
              (Join-Path $Root "backend\requirements-integrations.txt"))
if (Test-Path -LiteralPath $stagedWheels) { Remove-Item -LiteralPath $stagedWheels -Recurse -Force }
New-Item -ItemType Directory -Path $stagedWheels -Force | Out-Null

if (-not $NoWheelDownload) {
    $python = Join-Path $Root "backend\.venv\Scripts\python.exe"
    if (-not (Test-Path -LiteralPath $python)) {
        $pyc = Get-Command py -ErrorAction SilentlyContinue
        if ($pyc) { $python = "py" } else { $python = (Get-Command python -ErrorAction SilentlyContinue).Source }
    }
    Write-Host "Downloading dependency wheels (offline-verified)..."
    $tmp = Join-Path $CacheDir "whl-tmp"
    if (Test-Path -LiteralPath $tmp) { Remove-Item -LiteralPath $tmp -Recurse -Force }
    New-Item -ItemType Directory -Path $tmp -Force | Out-Null

    $pipArgs = @("-m","pip","download","--only-binary=:all:",
              "-r",$reqFiles[0],"-r",$reqFiles[1],"-d",$tmp)
    & $python @pipArgs
    if ($LASTEXITCODE -ne 0) { throw "pip download failed" }
    Copy-Item (Join-Path $tmp "*") $stagedWheels -Force
    Remove-Item -LiteralPath $tmp -Recurse -Force
    Log "staged $((Get-ChildItem $stagedWheels -Filter *.whl).Count) wheels"
} elseif (Test-Path -LiteralPath $WheelCache) {
    Copy-Item (Join-Path $WheelCache "*") $stagedWheels -Force
} else {
    Write-Host "  -NoWheelDownload but no wheel cache present; wheels folder will be empty" -ForegroundColor Yellow
}

# ---- bundled Python installer ----------------------------------------------
$InstallerUrl = "https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe"
$InstallerName = "python-3.12.10-amd64.exe"
$installerCache = Join-Path $CacheDir $InstallerName
if (-not (Test-Path -LiteralPath $installerCache)) {
    Write-Host "Downloading bundled Python installer..."
    Invoke-WebRequest -Uri $InstallerUrl -OutFile $installerCache -UseBasicParsing
}
New-Item -ItemType Directory -Path (Join-Path $Media "python") -Force | Out-Null
Copy-Item $installerCache (Join-Path $Media "python\$InstallerName") -Force
Log "staged $InstallerName ($([math]::Round((Get-Item $installerCache).Length/1MB,1)) MB)"

$whCount = (Get-ChildItem $stagedWheels -Filter *.whl -ErrorAction SilentlyContinue).Count
if ($whCount -eq 0) { Write-Host "WARNING: wheels folder is empty; offline installs will fail." -ForegroundColor Yellow }

# ---- CHECKSUMS -------------------------------------------------------------
$checks = @()
foreach ($f in (Get-ChildItem -LiteralPath $Media -Recurse -File)) {
    $rel = $f.FullName.Substring($Media.Length + 1)
    $hash = (Get-FileHash -LiteralPath $f.FullName -Algorithm SHA256).Hash
    $checks += "$hash  $rel"
}
$checks | Sort-Object | Set-Content -Path (Join-Path $Media "CHECKSUMS.txt") -Encoding UTF8
Log "wrote CHECKSUMS.txt ($($checks.Count) files)"

# ---- ISO -------------------------------------------------------------------
$isoOut = Join-Path $DistDir "Industrial-Academy-$version-setup-x64.iso"
if ($SkipIso) {
    Write-Host "ISO skipped (staged tree at $Media)" -ForegroundColor Yellow
} else {
    Write-Host "Creating ISO image..."
    if (Test-Path -LiteralPath $isoOut) { Remove-Item -LiteralPath $isoOut -Force }
    # IMAPI2's result image is a raw COM IStream; PowerShell cannot invoke its
    # vtable methods directly, so a tiny compiled shim does the byte copy.
    if (-not ("IsoStream" -as [type])) {
        Add-Type -TypeDefinition @'
using System;
using System.IO;
using System.Runtime.InteropServices;
using System.Runtime.InteropServices.ComTypes;
public static class IsoStream {
    public static long WriteToFile(object streamObj, string path, long knownLength) {
        IStream s = (IStream)streamObj;
        IntPtr pRead = Marshal.AllocHGlobal(sizeof(int));
        long total = 0;
        try {
            using (FileStream fs = File.Create(path)) {
                byte[] buf = new byte[1024 * 1024];
                while (true) {
                    Marshal.WriteInt32(pRead, 0);
                    s.Read(buf, buf.Length, pRead);
                    int read = Marshal.ReadInt32(pRead);
                    if (read <= 0) break;
                    fs.Write(buf, 0, read);
                    total += read;
                    if (knownLength > 0 && total >= knownLength) break;
                }
                fs.Flush();
            }
        } finally {
            Marshal.FreeHGlobal(pRead);
        }
        return total;
    }
}
'@
    }
    $fsi = New-Object -ComObject IMAPI2FS.MsftFileSystemImage
    $fsi.FileSystemsToCreate = 7   # ISO9660 + Joliet + UDF
    $fsi.VolumeName = "IndustrialAcademy$($version -replace '\.','')"
    $fsi.Root.AddTree($Media, $false)   # media tree contents at the volume root
    $result = $fsi.CreateResultImage()
    [IsoStream]::WriteToFile($result.ImageStream, $isoOut, -1) | Out-Null
    $sizeMb = [math]::Round((Get-Item $isoOut).Length/1MB, 1)
    Write-Host "ISO written: $isoOut ($sizeMb MB)" -ForegroundColor Green
    $mediaSizeMb = [math]::Round(((Get-ChildItem -LiteralPath $Media -Recurse -File | Measure-Object Length -Sum).Sum)/1MB, 1)
    Write-Host "Media tree: $mediaSizeMb MB (staging kept at $Media)" -ForegroundColor Green
}