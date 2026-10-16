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
$nodeAppendOut = Join-Path $OutputDir "node_review.txt"
Run-LoggedProcess -Name "node_review_logic" -FilePath "node" -ArgumentList @("tests/frontend_review_logic.js") -OutputFile $nodeAppendOut
if (Test-Path $nodeAppendOut) {
    $existingNode = Get-Content $nodeOut -Raw -ErrorAction SilentlyContinue
    $appendContent = Get-Content $nodeAppendOut -Raw -ErrorAction SilentlyContinue
    Write-Utf8File -Path $nodeOut -Content "$existingNode`n$appendContent"
    Remove-Item $nodeAppendOut -Force -ErrorAction SilentlyContinue
}

# 5. Pytest in isolated runtime
$pyTestArgs = @(
    "-c",
    "`"import tests.serve_isolated_app; import pytest, sys; sys.exit(pytest.main(['tests/test_release_evidence.py', '-q', '--tb=short']))`""
)
Run-LoggedProcess -Name "pytest_isolated" -FilePath $pyPath -ArgumentList $pyTestArgs -OutputFile (Join-Path $OutputDir "pytest.txt")

$Results.end_time = (Get-Date -Format "yyyy-MM-ddTHH:mm:sszzz")
Write-Utf8File -Path (Join-Path $OutputDir "baseline_results.json") -Content ($Results | ConvertTo-Json -Depth 5)

Write-Host "[verify] Finished with overall exit code: $($Results.overall_exit_code)"
exit $Results.overall_exit_code
