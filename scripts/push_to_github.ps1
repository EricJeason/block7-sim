#requires -Version 5.1
# Block-7 一键 push 到 GitHub
#
# 用法:Eric 双击执行 或 PowerShell 跑
#   .\scripts\push_to_github.ps1
#
# 自动完成:
# 1. 检测 gh CLI(应已安装,winget install GitHub.cli)
# 2. 检测 GitHub 登录状态;未登录则启动 web 登录(浏览器弹出)
# 3. 创建公开 repo "block7-sim"
# 4. 把当前 main 分支 push 到 origin
# 5. 输出仓库 URL

$ErrorActionPreference = "Stop"

# 项目根(脚本所在目录的父目录)
$RepoRoot = (Resolve-Path "$PSScriptRoot\..").Path
Set-Location $RepoRoot

Write-Host "=== Block-7 → GitHub 推送 ===" -ForegroundColor Cyan
Write-Host "项目路径: $RepoRoot"
Write-Host ""

# Step 1:找 gh.exe
$ghPath = "C:\Program Files\GitHub CLI\gh.exe"
if (-not (Test-Path $ghPath)) {
    $ghPath = (Get-Command gh -ErrorAction SilentlyContinue).Source
}
if (-not $ghPath) {
    Write-Host "✗ 未找到 gh CLI" -ForegroundColor Red
    Write-Host "请先安装:winget install --id GitHub.cli" -ForegroundColor Yellow
    Read-Host "按回车关闭"
    exit 1
}
Write-Host "✓ 找到 gh: $ghPath" -ForegroundColor Green

# Step 2:检测登录
Write-Host ""
Write-Host "检测 GitHub 登录..."
$authOk = $false
try {
    & $ghPath auth status 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) {
        $authOk = $true
    }
} catch {
    $authOk = $false
}

if (-not $authOk) {
    Write-Host "⚠️  未登录 GitHub,即将启动浏览器登录" -ForegroundColor Yellow
    Write-Host "  推荐流程:GitHub.com → HTTPS → Login with a web browser → 浏览器粘贴 device code"
    Write-Host ""
    & $ghPath auth login
    if ($LASTEXITCODE -ne 0) {
        Write-Host "✗ 登录失败,中止" -ForegroundColor Red
        Read-Host "按回车关闭"
        exit 1
    }
}
Write-Host "✓ GitHub 已登录" -ForegroundColor Green

# Step 3:确认当前 git 状态
Write-Host ""
Write-Host "当前 git 状态:"
& git status -sb | Select-Object -First 5

# Step 4:检测是否已有 origin
$hasOrigin = $false
try {
    $remote = & git remote get-url origin 2>$null
    if ($LASTEXITCODE -eq 0) {
        $hasOrigin = $true
        Write-Host ""
        Write-Host "⚠️  已存在 origin: $remote" -ForegroundColor Yellow
        Write-Host "  跳过 repo 创建,直接 push 到现有 origin"
    }
} catch {}

if (-not $hasOrigin) {
    Write-Host ""
    Write-Host "创建 GitHub repo + push..." -ForegroundColor Cyan
    & $ghPath repo create block7-sim `
        --public `
        --source=. `
        --remote=origin `
        --push `
        --description "Stanford Generative Agents 中文复刻 — 暮谷镇生成式智能体社会模拟器" `
        --homepage "https://arxiv.org/abs/2304.03442"
    if ($LASTEXITCODE -ne 0) {
        Write-Host "✗ 创建/推送失败" -ForegroundColor Red
        Read-Host "按回车关闭"
        exit 1
    }
} else {
    Write-Host ""
    Write-Host "Push main 到 origin..." -ForegroundColor Cyan
    & git push -u origin main
    if ($LASTEXITCODE -ne 0) {
        Write-Host "✗ Push 失败" -ForegroundColor Red
        Read-Host "按回车关闭"
        exit 1
    }
}

# Step 5:输出 URL
$username = & $ghPath api user --jq .login
Write-Host ""
Write-Host "═══════════════════════════════════════════════" -ForegroundColor Green
Write-Host "✓ 推送成功" -ForegroundColor Green
Write-Host "  仓库 URL: https://github.com/$username/block7-sim" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════════" -ForegroundColor Green
Write-Host ""
Write-Host "下一步建议:"
Write-Host "  1. 浏览器访问 https://github.com/$username/block7-sim 确认"
Write-Host "  2. 在 Settings → About 加 topics 标签:agent / llm / godot / deepseek / stanford-generative-agents"
Write-Host "  3. 加截图:在 Issues 创建一个 'Screenshots' issue 上传游戏截图,README 引用"
Write-Host ""
Read-Host "按回车关闭"
