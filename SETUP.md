# 安装与运行指南

> **目标读者**:第一次拉到本仓库的开发者 / 玩家
> **预计耗时**:3-10 分钟(取决于是否已有 DeepSeek 账号)

---

## 前置依赖

| 工具 | 最低版本 | 备注 |
|---|---|---|
| Python | 3.11+ | 推荐 3.12 / 3.13 |
| Godot Engine | 4.3+ | [下载](https://godotengine.org/download) |
| Git | any | clone 用 |
| DeepSeek API key | — | [注册](https://platform.deepseek.com),需充值(开发期 ¥100 足够) |

支持的 OS:Windows 10/11(已测)/ macOS / Linux(后两者作者未测,理论可跑)。

---

## 步骤 1:Clone 仓库

```bash
git clone https://github.com/<your-username>/block7-sim
cd block7-sim
```

---

## 步骤 2:获取 DeepSeek API key + 配置 .env

### 2.1 注册 DeepSeek 账号 + 充值

1. 访问 **<https://platform.deepseek.com>**
2. 注册账号(支持微信、手机号)
3. 进入 "费用充值" → 充值 ¥20-100(开发期完全够,**本项目实测 ¥0.4/游戏日**)
4. 进入 "API Keys" → 点 "创建 API Key" → 复制(`sk-` 开头的字符串)

### 2.2 写入 `.env` 文件

在项目**根目录**(与 `README.md` 同级)创建 `.env` 文件:

```bash
cp .env.example .env
```

**Windows PowerShell**:
```powershell
Copy-Item .env.example .env
```

然后用文本编辑器打开 `.env`,**只需要改第一行**:

```diff
- DEEPSEEK_API_KEY=your_api_key_here
+ DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxx
```

其它字段保持默认即可。`.env` 已被 `.gitignore` 排除,**永远不会被 commit**。

### 2.3 验证 key 有效(可选)

```bash
curl https://api.deepseek.com/v1/chat/completions \
  -H "Authorization: Bearer sk-xxxxxxxxxxxxxxxxxxxxxxxxx" \
  -H "Content-Type: application/json" \
  -d '{"model":"deepseek-v4-flash","messages":[{"role":"user","content":"你好"}]}'
```

返回 JSON 含 `"content": "..."` 即 key OK。

---

## 步骤 3:安装 Python 依赖

```bash
cd backend
pip install -e ".[dev]"
```

`-e` 把 backend 安装为可编辑模式,改代码立即生效(不必重装)。

可选:用 venv 隔离:
```bash
python -m venv .venv
.venv\Scripts\activate    # Windows
# 或 source .venv/bin/activate  # macOS/Linux
pip install -e ".[dev]"
```

---

## 步骤 4:启动 backend

### 4.1 推荐方式(默认 paused,零成本)

```bash
# 从项目根 cd 到 backend
cd backend
python -m uvicorn src.main:app --host 127.0.0.1 --port 8000
```

看到这 4 行 = 成功:
```
[main] lifespan startup: auto_tick=True start_paused=True ...
[sim] registered 12 agents
[sim] started: 12 agents, time_scale=60, tick_interval=1s, paused=True
INFO:     Application startup complete.
```

**保持这个窗口开着**。默认 paused 状态 — backend 不烧任何 token,等 Godot 端点 ▶ 才开始跑。

### 4.2 加速测试模式(测每日反思,24 秒跨日)

```bash
# Windows PowerShell
$env:BLOCK7_TIME_SCALE = "3600"
$env:BLOCK7_START_PAUSED = "0"
python -m uvicorn src.main:app --host 127.0.0.1 --port 8000

# macOS/Linux
BLOCK7_TIME_SCALE=3600 BLOCK7_START_PAUSED=0 python -m uvicorn src.main:app --host 127.0.0.1 --port 8000
```

每 24 现实秒跨一个游戏日 → 自动触发跨日反思(Block G)。

### 4.3 完全离线模式(零 LLM 调用,纯调试 Godot 端)

```bash
# Windows PowerShell
$env:BLOCK7_AUTO_TICK = "0"
python -m uvicorn src.main:app --host 127.0.0.1 --port 8000
```

backend 启动但 tick 循环不跑,Godot 端能连看到 12 agent 初始状态,但完全不烧 token。

### 4.4 全部环境变量

详见 `.env.example`,简要:
- `BLOCK7_START_PAUSED=1` — 启动暂停(默认,推荐)
- `BLOCK7_AUTO_TICK=1` — tick 循环开关(默认 1 开)
- `BLOCK7_TIME_SCALE=60` — 1 现实秒 = N 游戏秒(默认 60)
- `BLOCK7_TICK_INTERVAL=1.0` — tick 间隔(现实秒)
- `BLOCK7_THINKING_THRESHOLD=120` — fine plan 触发阈值(游戏秒)
- `BLOCK7_MAX_ACTIONS=15` — 每次 fine plan 输出上限
- `BLOCK7_DAILY_REFLECTION=1` — 跨日反思开关(默认开)

---

## 步骤 5:启动 Godot 客户端

1. 打开 Godot 4.3+,选择 "Import",定位到本项目的 `godot_client/project.godot`,点 "Import and Edit"
2. 等几秒等编辑器扫描资源
3. 按 **F5** 运行(或点右上角 ▶)
4. 第一次会提示选主场景,选 `scenes/Main.tscn`

### 第一次启动的预期

1. 全屏黑色加载界面 "⏳ 暮谷镇 · 加载中"
2. 左下角 **绿色 ▶ 开始(暂停中)** 按钮 — 点它开始烧 token
3. 等 30-90 秒,所有 12 agent 完成首轮 LLM 思考 → 加载界面消失
4. 看到老松广场场景 + 9 个 agent 名牌(艾琳是真实金发蓝裙像素 sprite,其它是色块)
5. 数字键 **1/2/3/4** 切场所
6. 点 Inspector 里 agent 按钮 **或** 直接点 agent sprite → 右下弹出 memory 面板(可切 全部/反思/观察/计划 4 个 tab)
7. 几分钟后两个 agent 在同场所触发对话 — 头顶冒白色气泡

### 监控成本

- **左下 PausePanel 旁** 实时显示 `¥X.XXX / X.XX/min / 命中 9X%`
- **PowerShell 一行** 看完整统计:
  ```bash
  curl http://127.0.0.1:8000/sim/health
  ```

---

## 步骤 6:跑测试(可选)

```bash
cd backend
python -m pytest -q
```

预期 **122 passed**(mock 测试,不烧 token)。

跑真实 API 测试(¥0.05/次):
```bash
python -m pytest tests/test_cache_hit_rate.py -v -s
```

预期缓存命中率 **≥ 90%**。

---

## 常见问题

### Q: backend 启动报 `sqlite3.OperationalError: unable to open database file`

确保你**从项目根目录** cd 到 `backend` 后再启动:
```bash
cd /path/to/block7-sim/backend
python -m uvicorn src.main:app --host 127.0.0.1 --port 8000
```

而**不是**直接在项目根目录跑(SQLite 相对路径会错位)。

### Q: Godot 端 "● 未连接" 不变绿

1. backend 是否还在跑?另开终端 `curl http://127.0.0.1:8000/health`,应该返回 `{"status":"ok"}`
2. 端口是否被占用?另一个 backend 进程可能没关掉
3. 防火墙是否拦截?Windows 第一次启动会弹"是否允许"

### Q: 12 个 agent 中只有 1 个有真实 sprite(艾琳),其它都是色块

正常 — 项目目前只有 agent_04 艾琳的完整像素素材。你可以自行用 ChatGPT/Imagen 生成其它 11 个角色的 sprite,放到 `godot_client/assets/characters/agent_<NN>/` 目录:
- `walk_n.png` / `walk_s.png` / `walk_e.png` / `walk_w.png` — 64×64 像素侧视行走
- `idle.png` — 静止帧
- `portrait.png` — 头像(256×256,对话用)

放好后 Godot 会自动加载(代码层完全不用改)。

### Q: 一小时跑了好几块钱,超预期?

**检查 BLOCK7_TIME_SCALE 是否被设成 3600 等加速值**——加速模式下 sim 推进太快,LLM 调用频率高。
正常 `time_scale=60` 实测约 **¥0.4/游戏日**(¥0.4/小时)。
随时按 Godot 左下橙色 ⏸ 暂停。

### Q: backend log 偶发 "daily JSON parse failed"

可忽略 — LLM 偶尔输出非纯 JSON,系统有三步容错(strip markdown / trailing comma)+ fallback 兜底。不影响 sim 运行。

---

## 安全提醒

- **`.env` 永远不要 commit**——`.gitignore` 已经排除,但任何 fork / clone 都从 `.env.example` 重新填
- **API key 不要分享**——DeepSeek 单次泄漏可能被刷干账户
- 如果误 commit 了 key,**立刻去 DeepSeek 平台 revoke 那个 key + 创建新 key**

---

## 下一步

跑通后,你可以:
- 读 [docs/Project_Design_Document_v0_2.md](docs/Project_Design_Document_v0_2.md) 理解架构
- 改 `backend/data/personas/agent_xx.yaml` 调整角色人格
- 改 `backend/src/llm/prompt_builder.py` 中的 `LAYER_0_SYSTEM` 切换世界观(注意:会破坏 4 层缓存命中率,需要重跑 `tests/test_cache_hit_rate.py` 验证)
- 看 [docs/工作展望.md](docs/工作展望.md) 中"待做"的 Block J/K/L

欢迎 issue / PR。
