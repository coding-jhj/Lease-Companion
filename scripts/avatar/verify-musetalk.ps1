param(
    [string]$MuseTalkRoot,
    [string]$AssetRoot,
    [string]$MuseTalkPython,
    [string]$BackendPython
)

$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $true
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path

if (-not $MuseTalkRoot) {
    $MuseTalkRoot = Join-Path $repoRoot 'tmp\MuseTalk'
}
if (-not $AssetRoot) {
    $AssetRoot = $MuseTalkRoot
}
if (-not $MuseTalkPython) {
    $MuseTalkPython = Join-Path $repoRoot 'tmp\musetalk-venv\Scripts\python.exe'
}
if (-not $BackendPython) {
    $BackendPython = Join-Path $repoRoot '.venv\Scripts\python.exe'
}

$required = @(
    (Join-Path $MuseTalkRoot 'scripts\inference.py'),
    $MuseTalkPython,
    $BackendPython,
    (Join-Path $AssetRoot 'models\musetalkV15\unet.pth'),
    (Join-Path $AssetRoot 'models\musetalkV15\musetalk.json'),
    (Join-Path $AssetRoot 'models\dwpose\dw-ll_ucoco_384.pth'),
    (Join-Path $AssetRoot 'models\face-parse-bisent\79999_iter.pth'),
    (Join-Path $AssetRoot 'models\sd-vae\config.json'),
    (Join-Path $AssetRoot 'models\sd-vae\diffusion_pytorch_model.bin'),
    (Join-Path $AssetRoot 'models\whisper\config.json'),
    (Join-Path $AssetRoot 'models\whisper\pytorch_model.bin'),
    (Join-Path $repoRoot 'frontend\public\practice\avatar\musetalk-source.mp4')
)

$missing = @($required | Where-Object { -not (Test-Path -LiteralPath $_) })
if ($missing.Count -gt 0) {
    Write-Error ("MuseTalk prerequisites are missing:`n- " + ($missing -join "`n- "))
}

& ffmpeg -version *> $null
if ($LASTEXITCODE -ne 0) {
    throw 'ffmpeg is not available on PATH.'
}

& $BackendPython -c "import supertonic; print('supertonic=ok')"
if ($LASTEXITCODE -ne 0) {
    throw 'Supertonic is not installed in the Backend Python environment.'
}

$previousPythonPath = $env:PYTHONPATH
$env:PYTHONPATH = $MuseTalkRoot
Push-Location $AssetRoot
try {
    & $MuseTalkPython -c "import scripts.inference, torch; assert torch.cuda.is_available(); print('musetalk=ok'); print('torch=' + torch.__version__); print('gpu=' + torch.cuda.get_device_name(0))"
    if ($LASTEXITCODE -ne 0) {
        throw 'MuseTalk import or CUDA validation failed.'
    }
}
finally {
    Pop-Location
    if ($null -eq $previousPythonPath) {
        Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
    }
    else {
        $env:PYTHONPATH = $previousPythonPath
    }
}

Write-Host 'MuseTalk runtime verification passed.' -ForegroundColor Green
Write-Host "MUSETALK_ROOT=$MuseTalkRoot"
Write-Host "MUSETALK_ASSET_ROOT=$AssetRoot"
Write-Host "MUSETALK_PYTHON=$MuseTalkPython"
