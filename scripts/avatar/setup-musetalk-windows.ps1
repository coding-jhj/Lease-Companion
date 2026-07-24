param(
    [string]$PythonLauncher = 'py',
    [switch]$SkipDependencies,
    [switch]$SkipWeights
)

$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $true
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$museTalkRoot = Join-Path $repoRoot 'tmp\MuseTalk'
$venvRoot = Join-Path $repoRoot 'tmp\musetalk-venv'
$venvPython = Join-Path $venvRoot 'Scripts\python.exe'
$museTalkCommit = '0a89dec45a0192b824e3cf4daf96c239440c5ed8'
$backendEnv = Join-Path $repoRoot 'backend\.env'

function Set-DotEnvValue {
    param(
        [string]$Path,
        [string]$Name,
        [string]$Value
    )

    $lines = if (Test-Path -LiteralPath $Path) { @(Get-Content -LiteralPath $Path) } else { @() }
    $pattern = '^\s*' + [regex]::Escape($Name) + '='
    $found = $false
    $updated = @(
        foreach ($line in $lines) {
            if ($line -match $pattern) {
                $found = $true
                "$Name=$Value"
            }
            else {
                $line
            }
        }
    )
    if (-not $found) {
        $updated += "$Name=$Value"
    }
    Set-Content -LiteralPath $Path -Value $updated -Encoding UTF8
}

if (-not (Test-Path -LiteralPath (Join-Path $museTalkRoot 'scripts\inference.py'))) {
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $museTalkRoot) | Out-Null
    & git clone https://github.com/TMElyralab/MuseTalk.git $museTalkRoot
    if ($LASTEXITCODE -ne 0) {
        throw 'MuseTalk clone failed.'
    }
}

& git -c "safe.directory=$($museTalkRoot.Replace('\', '/'))" -C $museTalkRoot checkout $museTalkCommit
if ($LASTEXITCODE -ne 0) {
    throw "MuseTalk checkout failed: $museTalkCommit"
}

if (-not (Test-Path -LiteralPath $venvPython)) {
    & $PythonLauncher -3.10 -m venv $venvRoot
    if ($LASTEXITCODE -ne 0) {
        throw 'Python 3.10 virtual environment creation failed.'
    }
}

if (-not $SkipDependencies) {
    & $venvPython -m pip install --upgrade pip
    if ($LASTEXITCODE -ne 0) { throw 'pip upgrade failed.' }
    & $venvPython -m pip install torch==2.0.1 torchvision==0.15.2 torchaudio==2.0.2 --index-url https://download.pytorch.org/whl/cu118
    if ($LASTEXITCODE -ne 0) { throw 'PyTorch installation failed.' }
    & $venvPython -m pip install -r (Join-Path $museTalkRoot 'requirements.txt')
    if ($LASTEXITCODE -ne 0) { throw 'MuseTalk requirements installation failed.' }
    & $venvPython -m pip install --no-cache-dir -U openmim
    if ($LASTEXITCODE -ne 0) { throw 'OpenMIM installation failed.' }
    $mim = Join-Path $venvRoot 'Scripts\mim.exe'
    & $mim install mmengine
    if ($LASTEXITCODE -ne 0) { throw 'mmengine installation failed.' }
    & $mim install 'mmcv==2.0.1'
    if ($LASTEXITCODE -ne 0) { throw 'mmcv installation failed.' }
    & $mim install 'mmdet==3.1.0'
    if ($LASTEXITCODE -ne 0) { throw 'mmdet installation failed.' }
    & $mim install 'mmpose==1.1.0'
    if ($LASTEXITCODE -ne 0) { throw 'mmpose installation failed.' }
    & $venvPython -m pip install 'yapf==0.40.1'
    if ($LASTEXITCODE -ne 0) {
        throw 'MuseTalk dependency installation failed.'
    }
}

if (-not $SkipWeights -and -not (Test-Path -LiteralPath (Join-Path $museTalkRoot 'models\musetalkV15\unet.pth'))) {
    $previousPath = $env:PATH
    $env:PATH = (Join-Path $venvRoot 'Scripts') + [IO.Path]::PathSeparator + $env:PATH
    Push-Location $museTalkRoot
    try {
        & (Join-Path $museTalkRoot 'download_weights.bat')
        if ($LASTEXITCODE -ne 0) {
            throw 'MuseTalk weight download failed.'
        }
    }
    finally {
        Pop-Location
        $env:PATH = $previousPath
    }
}

& (Join-Path $PSScriptRoot 'verify-musetalk.ps1') `
    -MuseTalkRoot $museTalkRoot `
    -AssetRoot $museTalkRoot `
    -MuseTalkPython $venvPython

if (-not (Test-Path -LiteralPath $backendEnv)) {
    Copy-Item -LiteralPath (Join-Path $repoRoot 'backend\.env.example') -Destination $backendEnv
}
Set-DotEnvValue -Path $backendEnv -Name 'PRACTICE_MEDIA_ENABLED' -Value 'true'
Set-DotEnvValue -Path $backendEnv -Name 'MUSETALK_ROOT' -Value '..\tmp\MuseTalk'
Set-DotEnvValue -Path $backendEnv -Name 'MUSETALK_ASSET_ROOT' -Value ''
Set-DotEnvValue -Path $backendEnv -Name 'MUSETALK_PYTHON' -Value '..\tmp\musetalk-venv\Scripts\python.exe'
Set-DotEnvValue -Path $backendEnv -Name 'MUSETALK_SOURCE_AVATAR' -Value '..\frontend\public\practice\avatar\musetalk-source.mp4'
Set-DotEnvValue -Path $backendEnv -Name 'MUSETALK_UNET_MODEL_PATH' -Value '..\tmp\MuseTalk\models\musetalkV15\unet.pth'
Set-DotEnvValue -Path $backendEnv -Name 'MUSETALK_UNET_CONFIG' -Value '..\tmp\MuseTalk\models\musetalkV15\musetalk.json'

Write-Host 'backend/.env was configured. Restart FastAPI to apply MuseTalk.' -ForegroundColor Cyan
