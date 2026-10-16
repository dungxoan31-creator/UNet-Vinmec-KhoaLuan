<#
.SYNOPSIS
    Launcher and pre-flight readiness runner for the Human-in-the-Loop Ovarian Ultrasound Prototype.
.DESCRIPTION
    Validates Python environment, external checkpoint hash integrity, and required security secrets
    before starting the FastAPI service on an isolated runtime directory.
.PARAMETER RuntimeDir
    Path to isolated runtime data directory (contains database and uploads). Defaults to artifacts/prototype-runtime.
.PARAMETER Port
    HTTP port to bind uvicorn on localhost. Defaults to 8000.
.PARAMETER CheckOnly
    If specified, performs all readiness checks, prints status, and exits 0 without spawning uvicorn or creating DB rows.
#>
param(
    [string]$RuntimeDir = "",
    [int]$Port = 8000,
    [switch]$CheckOnly
)

$ErrorActionPreference = "Continue"

$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

# 1. Validate Python Interpreter
$pyPath = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $pyPath)) {
    $pyCmd = Get-Command "python" -ErrorAction SilentlyContinue
    if ($pyCmd) {
        $pyPath = $pyCmd.Source
    } else {
        [Console]::Error.WriteLine("[Launcher] Python interpreter not found in .venv\Scripts\python.exe or PATH.")
        exit 2
    }
}

# 2. Validate Security Secrets in Environment
$jwtSecret = $env:APP_JWT_SECRET
if (-not $jwtSecret -or $jwtSecret.Length -lt 32) {
    [Console]::Error.WriteLine("[Launcher] Security configuration error: APP_JWT_SECRET must be set and contain at least 32 characters.")
    exit 2
}

$docPass = $env:APP_DOCTOR_PASSWORD
if (-not $docPass -or $docPass.Trim() -eq "") {
    [Console]::Error.WriteLine("[Launcher] Security configuration error: APP_DOCTOR_PASSWORD must be configured in environment.")
    exit 2
}

$adminPass = $env:APP_ADMIN_PASSWORD
if (-not $adminPass -or $adminPass.Trim() -eq "") {
    [Console]::Error.WriteLine("[Launcher] Security configuration error: APP_ADMIN_PASSWORD must be configured in environment.")
    exit 2
}

# 3. Validate Checkpoint File & Hash
$checkpointPath = $env:CHECKPOINT_PATH
if (-not $checkpointPath) {
    $checkpointPath = Join-Path $RepoRoot "checkpoints\unified_vinmec_refine_2026-10-06\lr_3e-04\baseline_unet_best.pth"
}

if (-not (Test-Path $checkpointPath)) {
    [Console]::Error.WriteLine("[Launcher] Checkpoint file not found: $checkpointPath")
    exit 2
}

$expectedHash = "417828fa74349d0f7909434f9ad1ad7cb3258b64d41d3d756e2e80569744697d"
$actualHash = (Get-FileHash -Path $checkpointPath -Algorithm SHA256).Hash.ToLower()

if ($actualHash -ne $expectedHash) {
    [Console]::Error.WriteLine("[Launcher] Checkpoint SHA-256 hash mismatch! Expected $expectedHash, got $actualHash")
    exit 2
}

# 4. Configure Isolated Runtime Directory
if (-not $RuntimeDir) {
    $RuntimeDir = Join-Path $RepoRoot "artifacts\prototype-runtime"
}

$resolvedRuntime = [System.IO.Path]::GetFullPath($RuntimeDir)
if (-not (Test-Path $resolvedRuntime)) {
    New-Item -ItemType Directory -Path $resolvedRuntime -Force | Out-Null
}

$env:APP_DATA_DIR = $resolvedRuntime
$env:APP_DB_PATH = Join-Path $resolvedRuntime "ovarian_ai.db"
$env:PYTHONPATH = $RepoRoot

# 5. CheckOnly Mode Handling
if ($CheckOnly) {
    Write-Host "[Launcher] Pre-flight readiness check PASSED:"
    Write-Host "  - Python: $pyPath"
    Write-Host "  - Runtime Directory: $resolvedRuntime"
    Write-Host "  - Checkpoint verified: (SHA256: $actualHash)"
    Write-Host "  - Security credentials: APP_JWT_SECRET, APP_DOCTOR_PASSWORD, APP_ADMIN_PASSWORD validated"
    Write-Host "[Launcher] Ready for supervised launch."
    exit 0
}

# 6. Launch Prototype Application via Uvicorn
Write-Host "[Launcher] Starting Ovarian Ultrasound Prototype on http://127.0.0.1:$Port..."
Write-Host "  - Runtime: $resolvedRuntime"
Write-Host "  - DB: $env:APP_DB_PATH"
& $pyPath -m uvicorn backend.app.main:app --host 127.0.0.1 --port $Port
exit $LASTEXITCODE
