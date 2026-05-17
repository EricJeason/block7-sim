# 推送到 GitHub 指南

> 项目本地已 100% ready,只剩一步登录 GitHub。Eric 任选一种方式即可。

---

## 方式 A:一键脚本(推荐,~2 分钟)

**前置**:Windows 已用 winget 装好 GitHub CLI(我已替你装好,见 `C:\Program Files\GitHub CLI\gh.exe`)。

1. 在文件资源管理器双击 `scripts\push_to_github.ps1`
   - 或 PowerShell 跑:`.\scripts\push_to_github.ps1`

2. **第一次会启动浏览器登录 GitHub**:
   - 控制台提示选 "GitHub.com" → "HTTPS" → "Login with a web browser"
   - 复制控制台显示的 8 位 device code(如 `XXXX-YYYY`)
   - 浏览器打开 https://github.com/login/device,粘贴 code,确认登录
   - 回到 PowerShell,看到 "Logged in as ..." 即成功

3. 脚本自动:
   - 创建 public repo `block7-sim`
   - push 当前 main 分支(含全部 21 个 commit 历史)
   - 输出仓库 URL

完成后访问 `https://github.com/<your-username>/block7-sim`。

---

## 方式 B:纯 git push(如果方式 A 卡住)

1. 浏览器访问 **<https://github.com/new>**
2. Repository name 填 `block7-sim`,公开 / 私有任选,**不要勾 "Initialize with README"**(我们本地已有)
3. 点 "Create repository"
4. GitHub 显示推送命令,但用下面这个(已配好):

```powershell
cd C:\Users\Administrator\Documents\block7-sim
git remote add origin https://github.com/<your-username>/block7-sim.git
git push -u origin main
```

5. 第一次 push 时 Git Credential Manager 弹窗,**Sign in with browser**,完成后自动 push

---

## 方式 C:导出 PAT(完全无浏览器,适合 headless)

1. 访问 <https://github.com/settings/tokens/new>
2. Note 填 `block7-sim push`,Expiration 选 30 days,勾 `repo` 和 `workflow`
3. 点 "Generate token",**复制那一长串以 `ghp_` 开头的 token**(只显示一次!)
4. PowerShell:
   ```powershell
   "ghp_xxxxxxxxxxxxx" | & "C:\Program Files\GitHub CLI\gh.exe" auth login --with-token
   ```
5. 然后跑 `scripts\push_to_github.ps1` 一键完成

---

## 推送后建议

1. **加 topics 标签**(Settings → About 旁边的齿轮)
   ```
   generative-agents, llm, godot-engine, deepseek, stanford,
   python, fastapi, websocket, chinese-game, simulation
   ```
2. **加 social preview 图**(Settings → Social preview),用一张游戏截图
3. **在 README.md 顶部加 badge**:
   ```markdown
   ![Tests](https://img.shields.io/badge/tests-122%20passed-green)
   ![License](https://img.shields.io/badge/license-MIT-blue)
   ![Python](https://img.shields.io/badge/python-3.11+-blue)
   ```
4. **issue 创建 "Screenshots" pinned issue** 上传游戏截图,README 用 raw URL 引用
5. **GitHub Actions CI**(可选,后续):自动跑 `pytest tests` mock 测试

---

## 安全提醒

- 仓库**不含** `.env` 或任何 API key(已经 .gitignore + git 历史扫描确认)
- `.env.example` 是模板,只含占位 `your_api_key_here`
- 如果你后续误 commit 了真 key,**立刻**:
  1. https://platform.deepseek.com 撤销那个 key
  2. 创建新 key 填回本地 `.env`
  3. `git filter-repo` 清 git 历史(或简单做法:`git push origin --force` 时把含 key 的 commit 改掉)
