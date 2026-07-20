#requires -Version 7
<#
.SYNOPSIS
  로컬 통합 개발 스택 기동: PostgreSQL → 백엔드(app.main:app) → 프론트(Vite, MSW off).
  한 터미널에서 백엔드[BE]·프론트[FE] 로그를 실시간 병합 출력하고, Ctrl+C로 전부 종료한다.

.DESCRIPTION
  lease 콘다 환경(또는 .venv)을 활성화한 상태에서 저장소 루트 기준으로 실행할 것.
  구형 데모(scripts/run-minimum-mvp.ps1의 app.mvp_app)가 아니라 정식 app.main:app을 띄운다.

  터널은 이 스크립트가 아니라 별도 터미널에서 실행한다 (URL이 로그에 묻히지 않도록):
    "C:\Program Files (x86)\cloudflared\cloudflared.exe" tunnel --url http://localhost:5173

.PARAMETER Force
  8000/5173을 점유 중인 프로세스를 강제 종료하고 진행 (스테일 서버 정리).

.PARAMETER SkipMigrate
  alembic upgrade head 를 건너뛴다.
#>
param(
    [switch]$Force,
    [switch]$SkipMigrate
)

$ErrorActionPreference = 'Stop'
$root     = Split-Path -Parent $PSScriptRoot
$backend  = Join-Path $root 'backend'
$frontend = Join-Path $root 'frontend'
$compose  = Join-Path $root 'docker-compose.yml'

$logDir = Join-Path $env:TEMP 'lease-dev-logs'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
# 서버별 stdout/stderr 각각 (uvicorn 로그는 stderr로 나가므로 둘 다 tail)
$logs = @{
    'BE-out' = Join-Path $logDir 'backend.out';  'BE-err' = Join-Path $logDir 'backend.err'
    'FE-out' = Join-Path $logDir 'frontend.out'; 'FE-err' = Join-Path $logDir 'frontend.err'
}
$logs.Values | ForEach-Object { Set-Content -Path $_ -Value '' }

function Fail($m) { Write-Host "✗ $m" -ForegroundColor Red; exit 1 }
function Ok($m)   { Write-Host "✓ $m" -ForegroundColor Green }

Write-Host '[점검] 사전 확인' -ForegroundColor Cyan

# 0) lease 환경 확인 (uvicorn import 가능?)
& python -c 'import uvicorn' 2>$null
if ($LASTEXITCODE -ne 0) { Fail 'python에서 uvicorn을 찾을 수 없음. lease 환경을 활성화했는지 확인 (conda activate lease).' }
Ok 'Python·uvicorn 확인'

# 1) PostgreSQL 기동 + 준비 대기
& docker compose -f $compose up -d db | Out-Null
$deadline = (Get-Date).AddSeconds(30)
do {
    & docker compose -f $compose exec -T db pg_isready -U lease 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) { break }
    Start-Sleep -Seconds 1
} while ((Get-Date) -lt $deadline)
if ($LASTEXITCODE -ne 0) { Fail 'PostgreSQL(5433) 준비 안 됨. Docker Desktop이 켜져 있는지 확인.' }
Ok 'PostgreSQL 준비됨 (5433)'

# 2) backend/.env · DATABASE_URL
$envFile = Join-Path $backend '.env'
if (-not (Test-Path $envFile)) { Fail 'backend/.env 없음. backend/.env.example 을 복사하세요.' }
if (-not (Select-String -Path $envFile -Pattern '^DATABASE_URL=' -Quiet)) { Fail 'backend/.env에 DATABASE_URL 이 없음.' }
Ok 'backend/.env · DATABASE_URL 확인'

# 3) 포트 8000·5173
foreach ($p in 8000, 5173) {
    $conn = Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($conn) {
        if ($Force) {
            Stop-Process -Id $conn.OwningProcess -Force -ErrorAction SilentlyContinue
            Ok "포트 $p 점유 프로세스(PID $($conn.OwningProcess)) 종료"
        }
        else {
            Fail "포트 $p 사용 중 (PID $($conn.OwningProcess)). -Force 로 정리하거나 해당 프로세스를 끄고 다시 실행."
        }
    }
}
Ok '포트 8000·5173 비어있음'

# 4) migration
if (-not $SkipMigrate) {
    Push-Location $backend
    try { & alembic upgrade head } finally { Pop-Location }
    if ($LASTEXITCODE -ne 0) { Fail 'alembic upgrade head 실패.' }
    Ok 'migration head 적용'
}

Write-Host '[기동] 백엔드·프론트 시작' -ForegroundColor Cyan
$be = Start-Process -FilePath 'python' `
    -ArgumentList '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8000' `
    -WorkingDirectory $backend `
    -RedirectStandardOutput $logs['BE-out'] -RedirectStandardError $logs['BE-err'] `
    -PassThru -NoNewWindow
$fe = Start-Process -FilePath 'npm.cmd' `
    -ArgumentList 'run', 'dev' `
    -WorkingDirectory $frontend `
    -RedirectStandardOutput $logs['FE-out'] -RedirectStandardError $logs['FE-err'] `
    -PassThru -NoNewWindow
Ok "백엔드 PID $($be.Id) / 프론트 PID $($fe.Id)"
Write-Host '로그 병합 출력 시작 — Ctrl+C 로 전부 종료. 터널은 별도 터미널에서 실행.' -ForegroundColor Cyan
Write-Host ('-' * 64)

# 병합 tail: 4개 로그를 태그 달아 실시간 출력
# ponytail: 매 tick 전체 라인수 비교(간단). dev 세션 규모엔 충분, 장시간이면 byte-offset로 교체.
$tails = @(
    @{ File = $logs['BE-out']; Tag = '[BE]'; Pos = 0 }
    @{ File = $logs['BE-err']; Tag = '[BE]'; Pos = 0 }
    @{ File = $logs['FE-out']; Tag = '[FE]'; Pos = 0 }
    @{ File = $logs['FE-err']; Tag = '[FE]'; Pos = 0 }
)
try {
    while ($true) {
        if ($be.HasExited -or $fe.HasExited) {
            Write-Host '! 서버 프로세스가 종료됨 — 로그 확인 후 재실행.' -ForegroundColor Yellow
            break
        }
        foreach ($t in $tails) {
            $lines = @(Get-Content -Path $t.File -ErrorAction SilentlyContinue)
            if ($lines.Count -gt $t.Pos) {
                $color = if ($t.Tag -eq '[BE]') { 'Gray' } else { 'DarkCyan' }
                $lines[$t.Pos..($lines.Count - 1)] | ForEach-Object { Write-Host "$($t.Tag) $_" -ForegroundColor $color }
                $t.Pos = $lines.Count
            }
        }
        Start-Sleep -Milliseconds 400
    }
}
finally {
    Write-Host "`n[종료] 서버 정리 중" -ForegroundColor Cyan
    foreach ($proc in $be, $fe) {
        if ($proc -and -not $proc.HasExited) { Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue }
    }
    Ok '종료 완료'
}
