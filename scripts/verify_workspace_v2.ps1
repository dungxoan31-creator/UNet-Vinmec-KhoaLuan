param([switch]$SkipBrowser)
$ErrorActionPreference = 'Stop'
$workspaceRoot = Split-Path $PSScriptRoot -Parent
Push-Location $workspaceRoot
try {
    $browserChecks = @('tests/workstation_viewer_e2e.js', 'tests/clinical_safety_e2e.js', 'tests/clinical_roundtrip_e2e.js')
    $logicChecks = @(Get-ChildItem -LiteralPath tests -Filter '*.mjs' -File | Sort-Object Name | ForEach-Object { $_.FullName })
    $required = @('scripts/type_check.js', 'tests/product_runtime.js') + $logicChecks
    if (-not $SkipBrowser) { $required += $browserChecks }
    $missing = @($required | Where-Object { -not (Test-Path -LiteralPath $_ -PathType Leaf) })
    if ($missing.Count) { throw "Verification targets missing: $($missing -join ', ')" }
    if (-not $logicChecks.Count) { throw 'No Node logic tests discovered; refusing empty verification.' }
    Write-Host '[syntax] JavaScript syntax only; this does not verify static types.'
    node scripts/type_check.js
    if ($LASTEXITCODE -ne 0) { throw 'Syntax verification failed.' }
    Write-Host '[unit] Node logic tests'
    node --test @logicChecks
    if ($LASTEXITCODE -ne 0) { throw 'Node logic verification failed.' }
    node tests/product_runtime.js
    if ($LASTEXITCODE -ne 0) { throw 'Product runtime contract verification failed.' }
    if ($SkipBrowser) {
        Write-Host '[browser] SKIPPED by -SkipBrowser; not full browser verification.'
    } else {
        foreach ($check in $browserChecks) {
            Write-Host "[browser] $check (self-managed isolated runtime and synthetic fixtures)"
            node $check
            if ($LASTEXITCODE -ne 0) { throw "Browser verification failed: $check" }
        }
    }
    Write-Host 'PASS: requested frontend verification scope. API/Python and clinical validation are separate checks.'
} finally { Pop-Location }
