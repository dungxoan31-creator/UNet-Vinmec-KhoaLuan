$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$demoData = Join-Path $projectRoot "data\demo_workspace"
$demoDatabase = Join-Path $demoData "ovarian_ai.db"
$python = Join-Path $projectRoot ".venv\Scripts\python.exe"
$pidSecretPath = Join-Path $demoData ".patient_pid_hmac_secret"
$jwtSecretPath = Join-Path $demoData ".app_jwt_secret"

if (-not (Test-Path -LiteralPath $demoDatabase)) {
  & $python (Join-Path $projectRoot "scripts\seed_demo_workspace.py")
  if ($LASTEXITCODE -ne 0) { throw "Demo workspace seeding failed (exit $LASTEXITCODE)." }
}
if (-not (Test-Path -LiteralPath $pidSecretPath) -or -not (Test-Path -LiteralPath $jwtSecretPath)) {
  throw "Demo database secrets are missing. Recreate the isolated demo database with scripts/seed_demo_workspace.py."
}

$env:APP_DATA_DIR = $demoData
$env:APP_DB_PATH = $demoDatabase
$env:APP_SYNTHETIC_DEMO_MODE = "1"
$env:APP_PATIENT_PID_HMAC_SECRET = (Get-Content -LiteralPath $pidSecretPath -Raw).Trim()
$env:APP_JWT_SECRET = (Get-Content -LiteralPath $jwtSecretPath -Raw).Trim()
$env:HOST = "127.0.0.1"

Set-Location $projectRoot
& $python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
