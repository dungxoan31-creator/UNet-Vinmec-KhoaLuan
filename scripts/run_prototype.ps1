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

$patientPidHmacSecret = $env:APP_PATIENT_PID_HMAC_SECRET
if (-not $patientPidHmacSecret -or $patientPidHmacSecret.Length -lt 32) {
    [Console]::Error.WriteLine("[Launcher] Security configuration error: APP_PATIENT_PID_HMAC_SECRET must be set and contain at least 32 characters.")
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

# 3. Validate the same checkpoint selected by the application model registry
$manifestPath = $env:MODEL_SELECTION_MANIFEST
if (-not $manifestPath) {
    $manifestPath = Join-Path $RepoRoot "evaluation\selected_model.json"
} elseif (-not [System.IO.Path]::IsPathRooted($manifestPath)) {
    $manifestPath = Join-Path $RepoRoot $manifestPath
}

if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) {
    [Console]::Error.WriteLine("[Launcher] Model selection manifest not found: $manifestPath")
    exit 2
}

try {
    $selection = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json -ErrorAction Stop
    $declaredCheckpoint = [string]$selection.checkpoint
    $expectedHash = ([string]$selection.checkpoint_sha256).ToLower()
    if (-not $declaredCheckpoint -or $expectedHash -notmatch '^[0-9a-f]{64}$') {
        throw "Manifest must declare checkpoint and a 64-character SHA-256."
    }
} catch {
    [Console]::Error.WriteLine("[Launcher] Invalid model selection manifest: $($_.Exception.Message)")
    exit 2
}

$manifestDirectory = Split-Path -Parent $manifestPath
$declaredPath = if ([System.IO.Path]::IsPathRooted($declaredCheckpoint)) {
    $declaredCheckpoint
} else {
    Join-Path $RepoRoot $declaredCheckpoint
}
if (-not (Test-Path -LiteralPath $declaredPath -PathType Leaf) -and -not [System.IO.Path]::IsPathRooted($declaredCheckpoint)) {
    $manifestRelativePath = Join-Path $manifestDirectory $declaredCheckpoint
    if (Test-Path -LiteralPath $manifestRelativePath -PathType Leaf) {
        $declaredPath = $manifestRelativePath
    }
}

$checkpointPath = $env:CHECKPOINT_PATH
if (-not $checkpointPath) {
    $checkpointPath = $declaredPath
}
if (-not (Test-Path -LiteralPath $checkpointPath -PathType Leaf)) {
    [Console]::Error.WriteLine("[Launcher] Checkpoint file not found: $checkpointPath")
    exit 2
}

try {
    $sha256 = [System.Security.Cryptography.SHA256]::Create()
    try {
        $checkpointStream = [System.IO.File]::OpenRead($checkpointPath)
        try {
            $hashBytes = $sha256.ComputeHash($checkpointStream)
        } finally {
            $checkpointStream.Dispose()
        }
    } finally {
        $sha256.Dispose()
    }
    $actualHash = [System.BitConverter]::ToString($hashBytes).Replace("-", "").ToLowerInvariant()
} catch {
    [Console]::Error.WriteLine("[Launcher] Unable to verify checkpoint SHA-256: $($_.Exception.Message)")
    exit 2
}

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
    Write-Host "  - Model manifest: $manifestPath"
    Write-Host "  - Checkpoint verified: (SHA256: $actualHash)"
    Write-Host "  - Security credentials: APP_JWT_SECRET, APP_PATIENT_PID_HMAC_SECRET, APP_DOCTOR_PASSWORD, APP_ADMIN_PASSWORD validated"
    Write-Host "[Launcher] Ready for supervised launch."
    exit 0
}

# 6. Launch Prototype Application via Uvicorn
Write-Host "[Launcher] Starting Ovarian Ultrasound Prototype on http://127.0.0.1:$Port..."
Write-Host "  - Runtime: $resolvedRuntime"
Write-Host "  - DB: $env:APP_DB_PATH"
& $pyPath -m uvicorn backend.app.main:app --host 127.0.0.1 --port $Port
exit $LASTEXITCODE
