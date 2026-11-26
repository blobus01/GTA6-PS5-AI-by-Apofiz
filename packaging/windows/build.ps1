<#
.SYNOPSIS
  Builds dist\ApofizPlay-GTA6-<VERSION>-win-x64-Setup.exe (Inno Setup) with a
  self-contained Python 3.12 runtime, all requirements, YOLO and ps5bridge.dll.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File packaging\windows\build.ps1
  powershell -ExecutionPolicy Bypass -File packaging\windows\build.ps1 -Cuda

  Works in Windows PowerShell 5.1 and pwsh 7. Run from any folder.

.NOTES
  Inputs (env):
    VERSION              version string (default: VERSION file, else 0.1.0)
    APOFIZ_BUILD_CACHE   download cache (default: packaging\windows\.cache)
    WIN_SIGN_PFX         path to a .pfx code-signing certificate (WIN_SIGN_CERT also accepted)
    WIN_SIGN_PASSWORD    its password
    WIN_SIGN_TIMESTAMP   RFC3161 timestamp URL (default http://timestamp.digicert.com)
  Signing happens only when WIN_SIGN_PFX/WIN_SIGN_CERT points to an existing file.
#>
[CmdletBinding()]
param(
  [string]$Version = "",
  # Build the CUDA variant of torch (NVIDIA GPUs). Default: CPU-only torch (much smaller).
  [switch]$Cuda,
  # PyTorch wheel index tag for -Cuda (see https://pytorch.org/get-started/locally/).
  [string]$CudaIndex = "cu128",
  # Skip the Inno Setup step (stage folder only, for debugging).
  [switch]$SkipInstaller,
  # Delete the staged runtime and rebuild it from scratch.
  [switch]$Clean,
  # Path to ISCC.exe if it is not in a standard location.
  [string]$Iscc = ""
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"   # Invoke-WebRequest is 10x slower with the progress bar
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$sw = [Diagnostics.Stopwatch]::StartNew()

# ---------------------------------------------------------------- pinned inputs
# python-build-standalone (Astral), CPython 3.12.16, release 20261026.
$PbsTag    = "20261026"
$PbsFile   = "cpython-3.12.16+$PbsTag-x86_64-pc-windows-msvc-install_only.tar.gz"
$PbsUrl    = "https://github.com/astral-sh/python-build-standalone/releases/download/$PbsTag/$($PbsFile -replace '\+','%2B')"
$PbsSha256 = "590dfcbe3a34c07301e6332e13e2188b98655cd072b08afa45a7998dc4c22bc5"
$YoloUrl   = "https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11n.pt"
$ChiakiTag = "v1.10.0"
$ChiakiGit = "https://github.com/streetpea/chiaki-ng.git"

# ---------------------------------------------------------------- paths
$Here  = $PSScriptRoot
$Root  = (Resolve-Path (Join-Path $Here "..\..")).Path
$Work  = Join-Path $Here ".work"
$Stage = Join-Path $Work "stage"
$Runtime = Join-Path $Stage "runtime"
$Cache = if ($env:APOFIZ_BUILD_CACHE) { $env:APOFIZ_BUILD_CACHE } else { Join-Path $Here ".cache" }
$Dist  = Join-Path $Root "dist"

if (-not $Version) { $Version = "$env:VERSION".Trim() }
if (-not $Version -and (Test-Path (Join-Path $Root "VERSION"))) { $Version = (Get-Content (Join-Path $Root "VERSION") -Raw).Trim() }
if (-not $Version) { $Version = "0.1.0" }
$Variant = if ($Cuda) { "-cuda" } else { "" }
$OutBase = "ApofizPlay-GTA6-$Version-win-x64$Variant-Setup"

function Step($msg) { Write-Host ("[{0,6:n0}s] {1}" -f $sw.Elapsed.TotalSeconds, $msg) -ForegroundColor Cyan }
function Exec([string]$exe, [string[]]$argv) {
  & $exe @argv
  if ($LASTEXITCODE -ne 0) { throw "failed ($LASTEXITCODE): $exe $($argv -join ' ')" }
}
function Download([string]$url, [string]$dest, [string]$sha256 = "") {
  if (Test-Path $dest) {
    if (-not $sha256 -or (Get-FileHash $dest -Algorithm SHA256).Hash -eq $sha256.ToUpper()) { return }
    Remove-Item $dest -Force
  }
  Write-Host "  download $url"
  $tmp = "$dest.part"
  Invoke-WebRequest -UseBasicParsing -Uri $url -OutFile $tmp
  if ($sha256) {
    $h = (Get-FileHash $tmp -Algorithm SHA256).Hash
    if ($h -ne $sha256.ToUpper()) { Remove-Item $tmp -Force; throw "SHA-256 mismatch for $url : $h" }
  }
  Move-Item $tmp $dest -Force
}

# ---------------------------------------------------------------- signing (optional)
$SignPfx = if ($env:WIN_SIGN_PFX) { $env:WIN_SIGN_PFX } else { $env:WIN_SIGN_CERT }
$SignTool = $null
if ($SignPfx -and (Test-Path $SignPfx)) {
  $SignTool = Get-ChildItem "${env:ProgramFiles(x86)}\Windows Kits\10\bin\*\x64\signtool.exe" -ErrorAction SilentlyContinue |
    Sort-Object FullName -Descending | Select-Object -First 1 -ExpandProperty FullName
  if (-not $SignTool) { $SignTool = (Get-Command signtool.exe -ErrorAction SilentlyContinue).Source }
  if (-not $SignTool) { throw "WIN_SIGN_PFX is set but signtool.exe was not found (install the Windows 10/11 SDK)" }
  $TsUrl = if ($env:WIN_SIGN_TIMESTAMP) { $env:WIN_SIGN_TIMESTAMP } else { "http://timestamp.digicert.com" }
  Write-Host "Code signing ON ($SignTool)"
} else {
  Write-Host "Code signing OFF (set WIN_SIGN_PFX + WIN_SIGN_PASSWORD to sign)"
}
function Sign-Files([string[]]$files) {
  if (-not $SignTool) { return }
  foreach ($f in $files) {
    Exec $SignTool @("sign", "/f", $SignPfx, "/p", "$env:WIN_SIGN_PASSWORD", "/fd", "sha256", "/tr", $TsUrl, "/td", "sha256", "/q", $f)
  }
}

Write-Host "Apofiz Play GTA6 $Version  ($(if ($Cuda) { "CUDA $CudaIndex" } else { 'CPU' }) torch)  root=$Root"
New-Item -ItemType Directory -Force -Path $Work, $Cache, $Dist | Out-Null

# ---------------------------------------------------------------- 1. Python runtime
$Py = Join-Path $Runtime "python.exe"
$Marker = Join-Path $Runtime ".apofiz-runtime"
$WantMarker = "$PbsFile|torch=$(if ($Cuda) { $CudaIndex } else { 'cpu' })|req=" +
  (Get-FileHash (Join-Path $Root "requirements.txt")).Hash +
  "|win=" + (Get-FileHash (Join-Path $Here "requirements-win.txt")).Hash
if ($Clean -or -not (Test-Path $Marker) -or (Get-Content $Marker -Raw).Trim() -ne $WantMarker) {
  if (Test-Path $Stage) { Step "clean stage"; Remove-Item $Stage -Recurse -Force }
  New-Item -ItemType Directory -Force -Path $Runtime | Out-Null

  Step "python-build-standalone $PbsFile"
  $tgz = Join-Path $Cache $PbsFile
  Download $PbsUrl $tgz $PbsSha256
  Exec "$env:SystemRoot\System32\tar.exe" @("-xzf", $tgz, "-C", $Runtime, "--strip-components=1")

  $env:PIP_DISABLE_PIP_VERSION_CHECK = "1"
  $env:PIP_CACHE_DIR = Join-Path $Cache "pip"
  $env:PYTHONNOUSERSITE = "1"
  $pipBase = @("-m", "pip", "install", "--no-warn-script-location", "--prefer-binary")

  Step "pip: torch ($(if ($Cuda) { $CudaIndex } else { 'cpu' }))"
  $idx = if ($Cuda) { "https://download.pytorch.org/whl/$CudaIndex" } else { "https://download.pytorch.org/whl/cpu" }
  Exec $Py ($pipBase + @("torch", "torchvision", "--index-url", $idx))

  Step "pip: requirements"
  $reqs = @("-r", (Join-Path $Root "requirements.txt"), "-r", (Join-Path $Here "requirements-win.txt"))
  $launcherReq = Join-Path $Root "launcher\requirements.txt"
  if (Test-Path $launcherReq) { $reqs += @("-r", $launcherReq) } else { Write-Warning "launcher\requirements.txt not found" }
  Exec $Py ($pipBase + $reqs)

  # Trim things the app never uses at runtime.
  Step "trim runtime"
  foreach ($d in @("Lib\test", "Lib\idlelib\idle_test", "Lib\tkinter\test", "Lib\lib2to3\tests", "include", "Scripts")) {
    $p = Join-Path $Runtime $d
    if (Test-Path $p) { Remove-Item $p -Recurse -Force }
  }
  Get-ChildItem (Join-Path $Runtime "Lib\site-packages") -Directory -Recurse -Filter "__pycache__" -ErrorAction SilentlyContinue |
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

  Set-Content -Path $Marker -Value $WantMarker -Encoding ascii
} else {
  Step "runtime up to date (use -Clean to rebuild)"
}

# ---------------------------------------------------------------- 2. native\ps5bridge.dll
$Dll = Join-Path $Root "native\ps5bridge.dll"
if (-not (Test-Path $Dll)) {
  Step "build native\ps5bridge.dll (zig cc via tools\build_native.py)"
  $chiaki = Join-Path $Root "vendor\chiaki-ng-src"
  if (-not (Test-Path (Join-Path $chiaki "lib\src\session.c"))) {
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
      throw "vendor\chiaki-ng-src is missing and git is not installed. Install Git for Windows, or copy chiaki-ng $ChiakiTag (with submodules) there."
    }
    Exec "git" @("clone", "--depth", "1", "--branch", $ChiakiTag, "--recurse-submodules", "--shallow-submodules", $ChiakiGit, $chiaki)
  }
  $benv = Join-Path $Work "buildenv"
  if (-not (Test-Path (Join-Path $benv "Scripts\python.exe"))) { Exec $Py @("-m", "venv", $benv) }
  $bpy = Join-Path $benv "Scripts\python.exe"
  Exec $bpy @("-m", "pip", "install", "--disable-pip-version-check", "-q", "ziglang", "protobuf>=4,<6", "grpcio-tools", "requests")
  Push-Location $Root
  try { Exec $bpy @((Join-Path $Root "tools\build_native.py")) } finally { Pop-Location }
  if (-not (Test-Path $Dll)) { throw "native build finished but $Dll is missing" }
}

# ---------------------------------------------------------------- 3. app files
Step "stage app files"
# Remove previous app files but keep the runtime.
Get-ChildItem $Stage -Force | Where-Object { $_.Name -ne "runtime" } | Remove-Item -Recurse -Force
$xd = @(".venv", ".buildenv", "vendor", "logs", "shots", "__pycache__", ".git", ".github", ".claude", ".idea", ".vscode",
        "node_modules", "dsh-bundle", "packaging", "dist", "site", (Join-Path $Root "native\build"), (Join-Path $Root "tests"))
$xf = @(".env.local", ".env.*.local", "*.log", "*.dylib", "*.pyc", ".mcp.json", ".DS_Store", "*.icns", "start.sh", "*.pt")
& robocopy $Root $Stage /E /NFL /NDL /NJH /NJS /NP /XD @xd /XF @xf | Out-Null
if ($LASTEXITCODE -ge 8) { throw "robocopy failed ($LASTEXITCODE)" }
$global:LASTEXITCODE = 0

$yolo = Join-Path $Root "yolo11n.pt"
if (-not (Test-Path $yolo)) { $yolo = Join-Path $Cache "yolo11n.pt"; Download $YoloUrl $yolo }
Copy-Item $yolo (Join-Path $Stage "yolo11n.pt") -Force

foreach ($need in @("server.py", "native\ps5bridge.dll", "web\index.html")) {
  if (-not (Test-Path (Join-Path $Stage $need))) { throw "stage is missing $need" }
}
if (-not (Test-Path (Join-Path $Stage "launcher\__main__.py"))) { throw "launcher\ (python -m launcher) is missing from the project" }

# Shortcut entry point: sets APOFIZ_BUNDLED=1 and runs `python -m launcher`.
Copy-Item (Join-Path $Here "ApofizPlay.pyw") (Join-Path $Stage "ApofizPlay.pyw") -Force

# Icon: launcher\assets\icon.ico if present, else make one from assets\apofiz-mark.png.
$ico = Join-Path $Stage "app.ico"
$srcIco = Join-Path $Root "launcher\assets\icon.ico"
if (Test-Path $srcIco) { Copy-Item $srcIco $ico -Force }
else {
  Exec $Py @("-I", "-c", "import sys; from PIL import Image; Image.open(sys.argv[1]).convert('RGBA').save(sys.argv[2], sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])",
             (Join-Path $Root "assets\apofiz-mark.png"), $ico)
}
Set-Content -Path (Join-Path $Stage "VERSION") -Value $Version -Encoding ascii

# Precompile: the launcher sets PYTHONDONTWRITEBYTECODE for bundled builds, so
# without this every start would recompile torch/ultralytics from source.
Step "compileall"
& $Py -I -m compileall -q -j 0 -x "[\\/](tests?|idle_test)[\\/]" $Stage | Out-Null
$global:LASTEXITCODE = 0

Sign-Files @((Join-Path $Stage "native\ps5bridge.dll"), $Py, (Join-Path $Runtime "pythonw.exe"))

$stageMB = [math]::Round(((Get-ChildItem $Stage -Recurse -File | Measure-Object Length -Sum).Sum / 1MB), 0)
Write-Host "  stage: $stageMB MB"
if ($SkipInstaller) { Step "done (stage only): $Stage"; return }

# ---------------------------------------------------------------- 4. Inno Setup
Step "Inno Setup"
if (-not $Iscc) {
  $cand = @("$env:ProgramFiles\Inno Setup 7\ISCC.exe", "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
            "$env:ProgramFiles\Inno Setup 6\ISCC.exe", "$env:LOCALAPPDATA\Programs\Inno Setup 7\ISCC.exe",
            "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe")
  $Iscc = $cand | Where-Object { Test-Path $_ } | Select-Object -First 1
  if (-not $Iscc) { $Iscc = (Get-Command iscc.exe -ErrorAction SilentlyContinue).Source }
  if (-not $Iscc -and (Get-Command choco -ErrorAction SilentlyContinue)) {
    Write-Host "  installing Inno Setup with choco"
    Exec "choco" @("install", "innosetup", "-y", "--no-progress")
    $Iscc = $cand | Where-Object { Test-Path $_ } | Select-Object -First 1
  }
  if (-not $Iscc) { throw "ISCC.exe not found. Install Inno Setup 6/7 (https://jrsoftware.org/isdl.php or 'winget install JRSoftware.InnoSetup') or pass -Iscc." }
}
$isccArgs = @("/Qp", "/DAppVersion=$Version", "/DStageDir=$Stage", "/DOutputDir=$Dist", "/DOutputBase=$OutBase")
if ($SignTool) {
  $isccArgs += "/DSign"
  $isccArgs += "/Sapofizsign=`"$SignTool`" sign /f `"$SignPfx`" /p `"$env:WIN_SIGN_PASSWORD`" /fd sha256 /tr $TsUrl /td sha256 /q `$f"
}
$isccArgs += (Join-Path $Here "installer.iss")
Exec $Iscc $isccArgs

$exe = Join-Path $Dist "$OutBase.exe"
if (-not (Test-Path $exe)) { throw "expected $exe" }
if (-not $Cuda) { Copy-Item $exe (Join-Path $Dist "ApofizPlay-GTA6-win-x64-Setup.exe") -Force }
$mb = [math]::Round((Get-Item $exe).Length / 1MB, 1)
Step "done: $exe ($mb MB) in $([math]::Round($sw.Elapsed.TotalMinutes,1)) min"
