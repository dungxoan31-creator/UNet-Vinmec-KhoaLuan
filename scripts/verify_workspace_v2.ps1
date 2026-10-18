param([switch]$SkipBrowser)
$ErrorActionPreference = 'Stop'
$workspaceRoot = Split-Path $PSScriptRoot -Parent
Push-Location $workspaceRoot
try {
    foreach ($module in Get-ChildItem frontend/app/*.js) {
        node --check $module.FullName
        if ($LASTEXITCODE -ne 0) { throw "Syntax check failed: $($module.Name)" }
    }
    $checks = @('tests/workspace_v2_logic.mjs', 'tests/frontend_review_logic.js', 'tests/product_runtime.js')
    if (-not $SkipBrowser) {
        $checks += @('tests/product_brand_e2e.js', 'tests/workspace_v2_live.js', 'tests/workspace_v2_dialog.js', 'tests/workspace_v2_api_abort.js', 'tests/workspace_v2_capabilities.js')
    }
    foreach ($check in $checks) {
        node $check
        if ($LASTEXITCODE -ne 0) { throw "Verification failed: $check" }
    }
} finally { Pop-Location }
