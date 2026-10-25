param(
    [switch]$BaselineOnly,
    [switch]$SkipBrowser,
    [switch]$PrototypeOnly,
    [ValidateSet("full", "selected")]
    [string]$TestScope = "selected",
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
    test_scope = $TestScope
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
$SelectedManifestPath = Join-Path $RepoRoot "evaluation\selected_model.json"
$SelectedManifest = Get-Content -LiteralPath $SelectedManifestPath -Raw | ConvertFrom-Json
$CheckpointPath = [System.IO.Path]::GetFullPath((Join-Path $RepoRoot $SelectedManifest.checkpoint))
$AllowedRoot = [System.IO.Path]::GetFullPath($RepoRoot).TrimEnd('\', '/') + [System.IO.Path]::DirectorySeparatorChar
if (-not $CheckpointPath.StartsWith($AllowedRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw 'Selected checkpoint must stay within the repository.'
}
if (Test-Path $CheckpointPath) {
    $cpHash = (Get-FileHash -Path $CheckpointPath -Algorithm SHA256).Hash.ToLower()
    $cpObj = [ordered]@{
        path = $CheckpointPath
        sha256 = $cpHash
        manifest = $SelectedManifestPath
        expected_sha256 = $SelectedManifest.checkpoint_sha256
        timestamp = (Get-Date -Format "yyyy-MM-ddTHH:mm:sszzz")
    }
    Write-Utf8File -Path (Join-Path $OutputDir "checkpoint_hash.json") -Content ($cpObj | ConvertTo-Json -Depth 4)
    if (-not $SelectedManifest.checkpoint_sha256 -or $cpHash -ne $SelectedManifest.checkpoint_sha256) {
        Write-Host '[verify] Selected checkpoint SHA-256 does not match the serving manifest.'
        if ($Results.overall_exit_code -eq 0) { $Results.overall_exit_code = 2 }
    }
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
Run-LoggedProcess -Name "node_logic" -FilePath "node" -ArgumentList @("--test", "tests/*.mjs") -OutputFile $nodeOut
$nodeReviewOut = Join-Path $OutputDir "node_review.txt"
Run-LoggedProcess -Name "node_runtime_contract" -FilePath "node" -ArgumentList @("tests/product_runtime.js") -OutputFile $nodeReviewOut

# 5. Live Playwright browser E2E test (if not -SkipBrowser and not -BaselineOnly)
$browserPassed = $false
if (-not $SkipBrowser -and -not $BaselineOnly) {
    Write-Host "[verify] Browser suites manage independent temporary servers; clinical writes use synthetic fixtures."
    $viewerExit = Run-LoggedProcess -Name "workstation_release_e2e" -FilePath "node" -ArgumentList @("tests/workstation_viewer_e2e.js") -OutputFile (Join-Path $OutputDir "release_e2e.txt")
    $safetyExit = Run-LoggedProcess -Name "safety_release_e2e" -FilePath "node" -ArgumentList @("tests/clinical_safety_e2e.js") -OutputFile (Join-Path $OutputDir "safety_e2e.txt")
    $roundtripExit = Run-LoggedProcess -Name "roundtrip_release_e2e" -FilePath "node" -ArgumentList @("tests/clinical_roundtrip_e2e.js") -OutputFile (Join-Path $OutputDir "roundtrip_e2e.txt")
    $browserPassed = ($viewerExit -eq 0 -and $safetyExit -eq 0 -and $roundtripExit -eq 0)
}

# 6. Pytest in isolated runtime
if ($TestScope -eq "full") {
    $pyTestArgs = @(
        "-c",
        "`"import pytest, sys; sys.exit(pytest.main(['tests', '-q', '--tb=short']))`""
    )
} else {
    $pyTestArgs = @(
        "-c",
        "`"import pytest, sys; sys.exit(pytest.main(['tests/test_release_evidence.py', 'tests/test_evaluation_report.py', 'tests/test_runtime_configuration.py', 'tests/test_prototype_release_failures.py', '-q', '--tb=short']))`""
    )
}
Run-LoggedProcess -Name "pytest_isolated" -FilePath $pyPath -ArgumentList $pyTestArgs -OutputFile (Join-Path $OutputDir "pytest.txt")

# 7. Record Baseline Results & Build Consolidated Report
$Results.live_browser_verified = $browserPassed
if ($PrototypeOnly -and -not $browserPassed -and $Results.overall_exit_code -eq 0) {
    Write-Host "[verify] PrototypeOnly mode requires live browser E2E; verification is incomplete."
    $Results.overall_exit_code = 1
}
$Results.end_time = (Get-Date -Format "yyyy-MM-ddTHH:mm:sszzz")
$baselineResultsPath = Join-Path $OutputDir "baseline_results.json"
Write-Utf8File -Path $baselineResultsPath -Content ($Results | ConvertTo-Json -Depth 5)

if (-not $BaselineOnly) {
    Write-Host "[verify] Building consolidated evaluation report artifacts..."
    $reportArgs = @(
        "scripts/build_evaluation_report.py",
        "--root", ".",
        "--runs", "evaluation/milestone_3_final/legacy_test_v1", "evaluation/milestone_3_final/validation_v1",
        "--hitl", "evaluation/milestone_3_final/hitl/analysis",
        "--user-study", "evaluation/milestone_3_final/user_study",
        "--output", $OutputDir,
        "--checks", $baselineResultsPath
    )
    Run-LoggedProcess -Name "build_evaluation_report" -FilePath $pyPath -ArgumentList $reportArgs -OutputFile (Join-Path $OutputDir "build_report.txt")
}

# 8. Record Final Checks and Release Evidence
$finalChecksPath = Join-Path $OutputDir "final_checks.json"
if (Test-Path $finalChecksPath) {
    $finalChecks = Get-Content $finalChecksPath -Raw | ConvertFrom-Json
} else {
    $finalChecks = [ordered]@{
        schema_version = 1
        generated_at = $Results.end_time
        test_scope = $TestScope
        overall_exit_code = $Results.overall_exit_code
        prototype_ready = ($Results.overall_exit_code -eq 0 -and -not $SkipBrowser -and $browserPassed)
        evaluation_complete = $false
        clinician_validation = $false
        independent_gate_status = "BLOCKED"
        browser_skipped = [bool]$SkipBrowser
        live_browser_verified = $browserPassed
        commands_executed = $Results.commands.Count
    }
    Write-Utf8File -Path $finalChecksPath -Content ($finalChecks | ConvertTo-Json -Depth 5)
}

Write-Host "================================================================="
Write-Host " RELEASE EVIDENCE SUMMARY"
Write-Host "================================================================="
Write-Host " Regression Test Scope:               $TestScope"
Write-Host " Technical Prototype Checks (RUO only): $(if ($finalChecks.prototype_ready) { 'PASS' } else { 'FAIL' })"
Write-Host " Clinical / Supervised Pilot Approval: NOT GRANTED BY THIS VERIFIER"
Write-Host " Scientific Evaluation Complete:      $(if ($finalChecks.evaluation_complete) { 'PASS [COMPLETE]' } else { 'PARTIAL / BLOCKED' })"
Write-Host " Independent Holdout Gate:             $($finalChecks.independent_gate_status)"
Write-Host " Clinician User Study:                $(if ($finalChecks.clinician_validation) { 'VERIFIED' } else { 'NOT_CONDUCTED' })"
Write-Host " Live Playwright Browser Verified:    $(if ($browserPassed) { 'YES' } else { 'NO / SKIPPED' })"
Write-Host " Overall Exit Code:                   $($Results.overall_exit_code)"
Write-Host " Output Directory:                    $OutputDir"
Write-Host "================================================================="

if ($PrototypeOnly -and $Results.overall_exit_code -eq 0) {
    Write-Host "[verify] PrototypeOnly mode: technical RUO checks passed; no clinical readiness is implied."
    exit 0
}

exit $Results.overall_exit_code
