param(
    [ValidatePattern('^[A-Za-z0-9][A-Za-z0-9._-]*$')]
    [string]$Version = 'dev'
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$releasePath = Join-Path $repoRoot "dist/repomesh-$Version"

function Invoke-Checked {
    param([string]$Program, [string[]]$Arguments)
    & $Program @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Program failed with exit code $LASTEXITCODE"
    }
}

Push-Location $repoRoot
try {
    # Never overwrite an older bundle or silently mix assets from two builds.
    if (Test-Path -LiteralPath $releasePath) {
        throw "Release directory already exists: $releasePath. Choose a new version."
    }
    Invoke-Checked npm @('--prefix', 'web', 'ci')
    Invoke-Checked npm @('--prefix', 'web', 'run', 'build')
    New-Item -ItemType Directory -Path "$releasePath/bin", "$releasePath/web", "$releasePath/configs" | Out-Null

    $targetOS = (& go env GOOS).Trim()
    if ($LASTEXITCODE -ne 0) { throw 'Could not determine GOOS' }
    $targetArch = (& go env GOARCH).Trim()
    if ($LASTEXITCODE -ne 0) { throw 'Could not determine GOARCH' }
    $suffix = if ($targetOS -eq 'windows') { '.exe' } else { '' }
    foreach ($name in @('repomesh-web', 'repomesh-coordinator', 'repomesh-host-executor')) {
        Invoke-Checked go @('build', '-buildvcs=false', '-trimpath', '-ldflags', "-X repomesh.local/repomesh/internal/buildinfo.Version=$Version", '-o', "$releasePath/bin/$name$suffix", "./cmd/$name")
    }
    Copy-Item -LiteralPath 'web/dist' -Destination "$releasePath/web/dist" -Recurse
    Copy-Item -LiteralPath 'configs/repomesh.env.example' -Destination "$releasePath/configs/repomesh.env.example"
    Copy-Item -LiteralPath 'web/package-lock.json' -Destination "$releasePath/web/package-lock.json"
    Copy-Item -LiteralPath 'README.md' -Destination "$releasePath/SOURCE-README.md"
    @"
RepoMesh $Version ($targetOS/$targetArch) - scaffold only

Run from this bundle directory:
  ./bin/repomesh-web$suffix --assets ./web/dist
  ./bin/repomesh-coordinator$suffix --version
  ./bin/repomesh-host-executor$suffix --version

Web: http://127.0.0.1:8080 ; /healthz = process only ; /readyz = 503.
Coordinator and host executor default startup exits 1: not implemented.
No database, queue, AgentTeams, Docker or Python service is configured.
All three binaries and web assets belong to this one release bundle.
This scaffold is not a business/integration acceptance result.
"@ | Set-Content -LiteralPath "$releasePath/README.txt" -Encoding utf8
    $artifactHashes = @{}
    Get-ChildItem -LiteralPath $releasePath -File -Recurse | ForEach-Object {
        $relative = [System.IO.Path]::GetRelativePath($releasePath, $_.FullName).Replace('\', '/')
        $artifactHashes[$relative] = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
    }
    [ordered]@{
        version = $Version
        stage = 'scaffold'
        businessReady = $false
        target = "$targetOS/$targetArch"
        artifacts = $artifactHashes
    } | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath "$releasePath/release.json" -Encoding utf8
    Write-Output "Release bundle: $releasePath"
} finally {
    Pop-Location
}
