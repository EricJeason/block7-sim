#requires -Version 5.1
# Block-7 Backend 启动脚本
# 用法:.\launch_backend.ps1 [default|fast]
#   default — paused 启动,零成本(等 Godot 里点 ▶)
#   fast    — 加速模式 + 自动 resume(测 Block G 反思,24 秒跨日)
#
# 自动处理:
# - 端口 8000 已占用时,先关掉旧 backend(避免双开造成的暂停死循环)
# - 自动 cd 到 worktree backend 目录(不依赖外部 cwd)

param([string]$Mode = "default")

# 切换到 backend 目录(脚本父目录 ../backend)
$BackendDir = Join-Path $PSScriptRoot "..\backend"
$BackendDir = (Resolve-Path $BackendDir).Path
Set-Location $BackendDir

# 端口占用检测 — 避免双开
$existing = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue |
    Where-Object { $_.State -eq 'Listen' } |
    Select-Object -First 1
if ($existing) {
    $pid_to_kill = $existing.OwningProcess
    Write-Host ""
    Write-Host "⚠️  Port 8000 已被进程占用 (PID=$pid_to_kill),自动关闭旧 backend..." -ForegroundColor Yellow
    try {
        Stop-Process -Id $pid_to_kill -Force -ErrorAction Stop
        Start-Sleep -Milliseconds 1500
        Write-Host "✓ 旧 backend 已关闭" -ForegroundColor Green
    } catch {
        Write-Host "✗ 关闭失败,可能权限不足或进程不存在。请手动 Ctrl+C 关闭旧窗口后重试。" -ForegroundColor Red
    }
}

if ($Mode -eq "fast") {
    $env:BLOCK7_TIME_SCALE = "3600"
    $env:BLOCK7_START_PAUSED = "0"
    Write-Host ""
    Write-Host "=== Block-7 Backend [FAST MODE] ===" -ForegroundColor Yellow
    Write-Host "1 现实秒 = 1 游戏小时,24 秒跨日触发 Block G 反思" -ForegroundColor Yellow
    Write-Host "成本约 ¥0.05/分钟,Ctrl+C 关闭" -ForegroundColor Yellow
    Write-Host ""
} else {
    Write-Host ""
    Write-Host "=== Block-7 Backend (default paused,零成本) ===" -ForegroundColor Cyan
    Write-Host "Godot 端点 ▶ 开始 才烧 token,Ctrl+C 关闭" -ForegroundColor Cyan
    Write-Host ""
}

python -m uvicorn src.main:app --host 127.0.0.1 --port 8000
