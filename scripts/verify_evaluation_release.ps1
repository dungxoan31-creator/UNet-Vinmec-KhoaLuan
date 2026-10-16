param(
    [switch]$BaselineOnly,
    [switch]$SkipBrowser,
    [switch]$PrototypeOnly,
    [string]$OutputDir = "",
    [int]$MockCommandExit = -1
)

$ErrorActionPreference = "Continue"

$RepoRoot = Split-Path -Parent $PSScriptRoot
if (-not $OutputDir) {
    if ($BaselineOnly) {
        $OutputDir = Join-Path $RepoRoot "evaluation\milestone_3_final\baseline"
    } else {
        $OutputDir = Join-Path $RepoRoot "evaluation\milestone_3_final\report"
    }
}

if (-not (Test-Path $OutputDir)) {
    New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null
}

$Utf8NoBom = New-Object System.Text.UTF8Encoding $false

function Write-Utf8File {
    param([string]$Path, [string]$Content)
    [System.IO.File]::WriteAllText($Path, $Content, $Utf8NoBom)
}

$Results = [ordered]@{
    start_time = (Get-Date -Format "yyyy-MM-ddTHH:mm:sszzz")
    baseline_only = [bool]$BaselineOnly
    skip_browser = [bool]$SkipBrowser
    prototype_only = [bool]$PrototypeOnly
    commands = @()
    overall_exit_code = 0
}

function Run-LoggedProcess {
    param(
        [string]$Name,
        [string]$FilePath,
        [string[]]$ArgumentList,
        [string]$OutputFile = ""
    )
    $cmdStart = (Get-Date -Format "yyyy-MM-ddTHH:mm:sszzz")
    $displayCmd = "$FilePath $($ArgumentList -join ' ')"
    Write-Host "[verify] Running: $Name ($displayCmd) ..."
    
    $stdoutFile = [System.IO.Path]::GetTempFileName()
    $stderrFile = [System.IO.Path]::GetTempFileName()
    
    $proc = Start-Process -FilePath $FilePath -ArgumentList $ArgumentList -NoNewWindow -Wait -PassThru -RedirectStandardOutput $stdoutFile -RedirectStandardError $stderrFile
    $exitCode = $proc.ExitCode
    
    $stdoutContent = Get-Content $stdoutFile -Raw -ErrorAction SilentlyContinue
    $stderrContent = Get-Content $stderrFile -Raw -ErrorAction SilentlyContinue
    
    Remove-Item $stdoutFile -Force -ErrorAction SilentlyContinue
    Remove-Item $stderrFile -Force -ErrorAction SilentlyContinue
    
    $combined = ""
    if ($stdoutContent) { $combined += $stdoutContent }
    if ($stderrContent) { $combined += "`n" + $stderrContent }
    
    if ($OutputFile) {
        Write-Utf8File -Path $OutputFile -Content $combined
    }
    
    $cmdEnd = (Get-Date -Format "yyyy-MM-ddTHH:mm:sszzz")
    $cmdRecord = [ordered]@{
        name = $Name
        command = $displayCmd
        exit_code = $exitCode
        start = $cmdStart
        end = $cmdEnd
    }
    $Results.commands += $cmdRecord
    
    if ($exitCode -ne 0 -and $Results.overall_exit_code -eq 0) {
        $Results.overall_exit_code = $exitCode
    }
    return $exitCode
}

# If MockCommandExit is set, execute a mock step with that exit code
if ($MockCommandExit -ge 0) {
    Run-LoggedProcess -Name "MockCommand" -FilePath "powershell.exe" -ArgumentList @("-NoProfile", "-Command", "exit $MockCommandExit") -OutputFile (Join-Path $OutputDir "mock.txt")
}

# 1. Git Status & Diff
Write-Host "[verify] Capturing git status and diff..."
Run-LoggedProcess -Name "git_status" -FilePath "git" -ArgumentList @("status") -OutputFile (Join-Path $OutputDir "git_status.txt")
Run-LoggedProcess -Name "git_diff" -FilePath "git" -ArgumentList @("diff") -OutputFile (Join-Path $OutputDir "git_diff.patch")

# 2. Checkpoint SHA256 Hash
$CheckpointPath = Join-Path $RepoRoot "checkpoints\unified_vinmec_refine_2026-10-06\lr_3e-04\baseline_unet_best.pth"
if (Test-Path $CheckpointPath) {
    $cpHash = (Get-FileHash -Path $CheckpointPath -Algorithm SHA256).Hash.ToLower()
    $cpObj = [ordered]@{
        path = $CheckpointPath
        sha256 = $cpHash
        timestamp = (Get-Date -Format "yyyy-MM-ddTHH:mm:sszzz")
    }
    Write-Utf8File -Path (Join-Path $OutputDir "checkpoint_hash.json") -Content ($cpObj | ConvertTo-Json -Depth 4)
} else {
    $cpObj = [ordered]@{
        path = $CheckpointPath
        sha256 = $null
        error = "Checkpoint not found"
    }
    Write-Utf8File -Path (Join-Path $OutputDir "checkpoint_hash.json") -Content ($cpObj | ConvertTo-Json -Depth 4)
    if ($Results.overall_exit_code -eq 0) { $Results.overall_exit_code = 2 }
}

# 3. Environment capture (Python, Node, OS, Packages)
$EnvPyScript = @"
import json, sys, platform, importlib.metadata
packages = {}
for dist in importlib.metadata.distributions():
    packages[dist.metadata['Name']] = dist.version
env_info = {
    'python_version': sys.version,
    'platform': platform.platform(),
    'packages': packages
}
print(json.dumps(env_info, indent=2))
"@
$envTempPy = [System.IO.Path]::GetTempFileName() + ".py"
Write-Utf8File -Path $envTempPy -Content $EnvPyScript
$pyPath = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $pyPath)) { $pyPath = "python" }

Run-LoggedProcess -Name "environment" -FilePath $pyPath -ArgumentList @($envTempPy) -OutputFile (Join-Path $OutputDir "environment.json")
Remove-Item $envTempPy -Force -ErrorAction SilentlyContinue

# 4. Node pure checks
$nodeOut = Join-Path $OutputDir "node.txt"
Run-LoggedProcess -Name "node_workspace_logic" -FilePath "node" -ArgumentList @("tests/workspace_v2_logic.mjs") -OutputFile $nodeOut
$nodeReviewOut = Join-Path $OutputDir "node_review.txt"
Run-LoggedProcess -Name "node_review_logic" -FilePath "node" -ArgumentList @("tests/frontend_review_logic.js") -OutputFile $nodeReviewOut
$nodeTelemOut = Join-Path $OutputDir "node_telemetry.txt"
Run-LoggedProcess -Name "node_telemetry_logic" -FilePath "node" -ArgumentList @("tests/workspace_v2_telemetry.mjs") -OutputFile $nodeTelemOut

# 5. Live Playwright browser E2E test (if not -SkipBrowser and not -BaselineOnly)
$browserPassed = $false
if (-not $SkipBrowser -and -not $BaselineOnly) {
    Write-Host "[verify] Starting isolated app server for release E2E tests..."
    $serverLogOut = Join-Path $OutputDir "server_stdout.log"
    $serverLogErr = Join-Path $OutputDir "server_stderr.log"
    $serverProc = Start-Process -FilePath $pyPath -ArgumentList @("tests/serve_isolated_app.py") -PassThru -NoNewWindow -RedirectStandardOutput $serverLogOut -RedirectStandardError $serverLogErr
    try {
        $healthy = $false
        for ($i = 0; $i -lt 30; $i++) {
            Start-Sleep -Milliseconds 800
            try {
                $h = Invoke-RestMethod -Uri "http://127.0.0.1:8027/api/health" -TimeoutSec 2 -ErrorAction Stop
                if ($h.model_ready) {
                    $healthy = $true
                    break
                }
            } catch {}
        }
        if (-not $healthy) {
            Write-Host "[verify] Error: Isolated server failed to report healthy on port 8027."
            if ($Results.overall_exit_code -eq 0) { $Results.overall_exit_code = 1 }
        } else {
            Write-Host "[verify] Isolated server ready. Running workspace_v2_release_e2e.js..."
            $e2eOut = Join-Path $OutputDir "release_e2e.txt"
            $e2eExit = Run-LoggedProcess -Name "workspace_v2_release_e2e" -FilePath "node" -ArgumentList @("tests/workspace_v2_release_e2e.js") -OutputFile $e2eOut
            if ($e2eExit -eq 0) {
                $browserPassed = $true
            }
        }
    } finally {
        if ($serverProc -and -not $serverProc.HasExited) {
            Write-Host "[verify] Stopping isolated server process..."
            Stop-Process -Id $serverProc.Id -Force -ErrorAction SilentlyContinue
        }
    }
}

# 6. Pytest in isolated runtime
$pyTestArgs = @(
    "-c",
    "`"import tests.serve_isolated_app; import pytest, sys; sys.exit(pytest.main(['tests/test_release_evidence.py', 'tests/test_evaluation_report.py', 'tests/test_runtime_configuration.py', 'tests/test_prototype_release_failures.py', '-q', '--tb=short']))`""
)
Run-LoggedProcess -Name "pytest_isolated" -FilePath $pyPath -ArgumentList $pyTestArgs -OutputFile (Join-Path $OutputDir "pytest.txt")

# 7. Consolidate Evaluation Report and Artifacts (if not -BaselineOnly)
if (-not $BaselineOnly) {
    Write-Host "[verify] Building consolidated evaluation report artifacts..."
    $reportArgs = @(
        "scripts/build_evaluation_report.py",
        "--root", ".",
        "--runs", "evaluation/milestone_3_final/legacy_test_v1", "evaluation/milestone_3_final/validation_v1",
        "--hitl", "evaluation/milestone_3_final/hitl/analysis",
        "--user-study", "evaluation/milestone_3_final/user_study",
        "--output", $OutputDir,
        "--set-current", "evaluation/milestone_3_final/legacy_test_v1"
    )
    Run-LoggedProcess -Name "build_evaluation_report" -FilePath $pyPath -ArgumentList $reportArgs -OutputFile (Join-Path $OutputDir "build_report.txt")
}

# 8. Record Final Checks and Release Evidence
$Results.end_time = (Get-Date -Format "yyyy-MM-ddTHH:mm:sszzz")
Write-Utf8File -Path (Join-Path $OutputDir "baseline_results.json") -Content ($Results | ConvertTo-Json -Depth 5)

$finalChecks = [ordered]@{
    schema_version = 1
    generated_at = $Results.end_time
    overall_exit_code = $Results.overall_exit_code
    prototype_ready = ($Results.overall_exit_code -eq 0)
    evaluation_complete = $false
    independent_gate_status = "BLOCKED"
    browser_skipped = [bool]$SkipBrowser
    live_browser_verified = $browserPassed
    commands_executed = $Results.commands.Count
}
Write-Utf8File -Path (Join-Path $OutputDir "final_checks.json") -Content ($finalChecks | ConvertTo-Json -Depth 5)

Write-Host "================================================================="
Write-Host " RELEASE EVIDENCE SUMMARY"
Write-Host "================================================================="
Write-Host " Prototype Ready (Supervised Pilot): $(if ($finalChecks.prototype_ready) { 'PASS [READY]' } else { 'FAIL [NOT READY]' })"
Write-Host " Scientific Evaluation Complete:      PARTIAL / BLOCKED"
Write-Host " Independent Holdout Gate:            BLOCKED (Missing patient-level mapping)"
Write-Host " Clinician User Study:                NOT_CONDUCTED (Technical Acceptance PASS)"
Write-Host " Live Playwright Browser Verified:    $(if ($browserPassed) { 'YES' } else { 'NO / SKIPPED' })"
Write-Host " Overall Exit Code:                   $($Results.overall_exit_code)"
Write-Host " Output Directory:                    $OutputDir"
Write-Host "================================================================="

if ($PrototypeOnly -and $Results.overall_exit_code -eq 0) {
    Write-Host "[verify] PrototypeOnly mode: Prototype release checks PASS. Exiting 0."
    exit 0
}

exit $Results.overall_exit_code
