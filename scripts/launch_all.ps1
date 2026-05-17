#requires -Version 5
# F2 一键启动:关旧进程 + 新窗口启 backend + 新窗口启 Godot 编辑器
# 用法(从任意目录):
#   PowerShell -ExecutionPolicy Bypass -File "C:\...\launch_all.ps1"
# 或在 worktree 根:
#   .\scripts\launch_all.ps1

$ErrorActionPreference = "Continue"

$WORKTREE = "C:\Users\Administrator\Documents\block7-sim\.claude\worktrees\blissful-knuth-4716c6"
$GODOT    = "C:\Tools\Godot\Godot_v4.6.2-stable_win64.exe"

Write-Host ""
Write-Host "=== Block-7 一键启动 (F2) ===" -ForegroundColor Cyan
Write-Host "worktree: $WORKTREE" -ForegroundColor DarkGray
Write-Host ""

# ---------------------------------------------------- 1. 关旧 Godot
Write-Host "[1/4] 关旧 Godot 进程..." -ForegroundColor Yellow
$godotProcs = Get-Process Godot* -ErrorAction SilentlyContinue
if ($godotProcs) {
    $godotProcs | Stop-Process -Force
    Write-Host "      关了 $($godotProcs.Count) 个 Godot 进程" -ForegroundColor DarkGray
} else {
    Write-Host "      没有 Godot 进程在跑" -ForegroundColor DarkGray
}
Start-Sleep -Milliseconds 800

# ---------------------------------------------------- 2. 关旧 backend(占 8000 端口)
Write-Host "[2/4] 关旧 backend(端口 8000)..." -ForegroundColor Yellow
$conns = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue
if ($conns) {
    $pids = $conns | Select-Object -ExpandProperty OwningProcess -Unique
    foreach ($p in $pids) {
        try {
            Stop-Process -Id $p -Force -ErrorAction Stop
            Write-Host "      关了 PID=$p" -ForegroundColor DarkGray
        } catch {
            Write-Host "      关 PID=$p 失败:$_" -ForegroundColor Red
        }
    }
} else {
    Write-Host "      端口 8000 空闲" -ForegroundColor DarkGray
}
Start-Sleep -Milliseconds 500

# ---------------------------------------------------- 3. 新窗口启 backend
Write-Host "[3/4] 新窗口启 backend..." -ForegroundColor Yellow
$backendCmd = "Set-Location '$WORKTREE'; .\scripts\launch_backend.ps1"
Start-Process powershell -ArgumentList @('-NoExit', '-Command', $backendCmd) | Out-Null
Write-Host "      新 PowerShell 窗口已开,等 Uvicorn 启动..." -ForegroundColor DarkGray
Start-Sleep -Seconds 2

# ---------------------------------------------------- 4. 启 Godot 编辑器
Write-Host "[4/4] 启 Godot 编辑器(指向 F2 worktree)..." -ForegroundColor Yellow
if (-not (Test-Path $GODOT)) {
    Write-Host "      ERROR:Godot 不存在 $GODOT" -ForegroundColor Red
    Write-Host "      请确认 Godot 路径(或修改本脚本顶部 \$GODOT 变量)" -ForegroundColor Red
    return
}
Start-Process $GODOT -ArgumentList @('--editor', '--path', "$WORKTREE\godot_client") | Out-Null

Write-Host ""
Write-Host "=== 一键启动完成 ===" -ForegroundColor Green
Write-Host ""
Write-Host "下一步:" -ForegroundColor Cyan
Write-Host "  1. 等 backend 窗口出现 'Application startup complete'(约 3-5 秒)" -ForegroundColor White
Write-Host "  2. Godot 编辑器起来后按 F5 跑主场景" -ForegroundColor White
Write-Host "  3. API key 弹窗 Enter 提交(已有 key 自动填)" -ForegroundColor White
Write-Host "  4. LoadingOverlay 出现 → 按 Tab 启动预热(30-90 秒)" -ForegroundColor White
Write-Host "  5. 进游戏:WASD 移动,走近 NPC 看 whisper,按 E 弹气泡菜单" -ForegroundColor White
Write-Host ""
