$ErrorActionPreference = 'Stop'
$validationRoot = Split-Path $PSScriptRoot -Parent
$moduleRoot = Join-Path $validationRoot 'upstream/agentteams-controller'
$replacement = @{}
$replacement[(Join-Path $moduleRoot 'internal/server/validation_probe_test.go')] = Join-Path $PSScriptRoot 'controller-server_test.go'
$replacement[(Join-Path $moduleRoot 'internal/backend/validation_probe_test.go')] = Join-Path $PSScriptRoot 'controller-backend_test.go'
$overlayPath = Join-Path $PSScriptRoot 'controller-overlay.json'
@{ Replace = $replacement } | ConvertTo-Json -Depth 5 | Set-Content $overlayPath
Push-Location $moduleRoot
try {
    go version | Set-Content (Join-Path $validationRoot 'evidence/controller-go-version.txt')
    go test -p 2 -overlay $overlayPath ./internal/server ./internal/backend -run '^TestValidation' -count=1 -v *> (Join-Path $validationRoot 'evidence/controller-probes.log')
    $testExit = $LASTEXITCODE
    $testExit | Set-Content (Join-Path $validationRoot 'evidence/controller-probes.exitcode')
    if ($testExit -ne 0) { throw "Controller probes failed: $testExit" }
} finally {
    Pop-Location
}
