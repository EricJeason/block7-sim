# Day 1 Block A — 项目骨架完整化(Claude Code 任务包)

> **派发对象**:Windows 终端中的 Claude Code
> **预计时长**:30–45 分钟
> **优先级**:必须最先完成,后续 Block B/C/D 全部依赖此 Block

---

## 任务上下文

**项目**:Block-7 生成式智能体社会模拟器
**当前阶段**:Day 1, Block A
**架构总纲**:见项目根目录 `docs/Project_Design_Document_v0_2.md`(由 Eric 在 Block A 开始前手动放入此目录)

**前置任务**(Day 0 已完成,无需重做):
- ✅ 项目根目录创建完毕,18 个子目录就位
- ✅ `.gitignore`、`.env.example`、`README.md` 已存在
- ✅ 本地 git 仓库已初始化(分支 `main`,1 条 Day 0 commit)
- ✅ DeepSeek API key 已充值,可调用

**本任务依赖**:无(这是所有 Day 1 任务的入口)

---

## 任务目标

在 Cowork 搭好的目录骨架上,补完**Python 后端**与 **Godot 客户端**的所有项目级配置文件、模块占位文件、最小可运行 demo,让 Block B(DeepSeek 客户端)、Block C(SQLite schema)、Block D(Action Queue)能无障碍直接开始写业务逻辑。

**核心原则**:**只搭架子,不写业务逻辑**。除"hello world 级别的最小可启动验证代码"外,所有模块文件都只放空函数签名 + docstring。业务逻辑在 Block B 之后才写。

---

## 详细规格

### A.1 Python 后端骨架

#### A.1.1 `backend/pyproject.toml`

创建 Python 项目配置文件,使用 PEP 621 标准。

**依赖列表**(`[project.dependencies]`):

| 包 | 版本约束 | 用途 |
|---|---|---|
| `httpx` | `>=0.27,<1.0` | 异步 HTTP 客户端,调用 DeepSeek API |
| `fastapi` | `>=0.115,<1.0` | 后端 Web 服务 |
| `uvicorn[standard]` | `>=0.32,<1.0` | ASGI 服务器 |
| `websockets` | `>=13.0,<15.0` | WebSocket 协议 |
| `pydantic` | `>=2.9,<3.0` | 数据模型校验 |
| `aiosqlite` | `>=0.20,<1.0` | 异步 SQLite |
| `pyyaml` | `>=6.0,<7.0` | persona YAML 加载 |
| `python-dotenv` | `>=1.0,<2.0` | 加载 `.env` |
| `tiktoken` | `>=0.8,<1.0` | token 计数(用于成本统计) |
| `rich` | `>=13.0,<14.0` | 控制台日志美化 |

**开发依赖**(`[project.optional-dependencies] dev`):

| 包 | 用途 |
|---|---|
| `pytest>=8.0` | 测试框架 |
| `pytest-asyncio>=0.24` | 异步测试 |
| `ruff>=0.7` | linter + formatter |
| `mypy>=1.13` | 类型检查 |
| `httpx[cli]` | 命令行 HTTP 调试 |

**其他配置**:
- `requires-python = ">=3.11"`
- `name = "block7-sim-backend"`,`version = "0.1.0"`
- `[tool.ruff]`:line-length = 100,target-version = "py311"
- `[tool.pytest.ini_options]`:`asyncio_mode = "auto"`,`testpaths = ["tests"]`

#### A.1.2 Python 模块占位文件

在 `backend/src/` 下创建以下文件(替换 Cowork 留下的 `.gitkeep`):

```
backend/src/
├── __init__.py                 # 空,标识为 package
├── main.py                     # FastAPI app 入口(最小可启动)
├── config.py                   # 加载 .env 与全局配置
├── agent/
│   ├── __init__.py
│   ├── runtime.py              # AgentRuntime 数据类(占位 dataclass)
│   ├── scheduler.py            # Action Queue 调度器(空函数签名)
│   ├── planning.py             # 粗/细粒度规划(空函数签名)
│   ├── perception.py           # 同场所事件传播(空函数签名)
│   └── reflection.py           # 每日反思(空函数签名)
├── llm/
│   ├── __init__.py
│   ├── deepseek.py             # DeepSeek 客户端(空类骨架)
│   └── prompt_builder.py       # 4 层 prompt 缓存结构构建器(空函数签名)
├── memory/
│   ├── __init__.py
│   ├── schema.py               # SQLite schema 定义(空,Block C 填)
│   ├── store.py                # CRUD + 关键词查询(空函数签名)
│   └── compression.py          # memory 压缩策略(空函数签名)
└── api/
    ├── __init__.py
    ├── routes.py               # FastAPI 路由(只放 /health)
    └── websocket.py            # WS 路由(占位)
```

**对每个 .py 文件的内容要求**:
- 顶部 docstring:一句话说明该模块负责什么
- 占位类/函数:只有签名 + docstring + `raise NotImplementedError("Block X 实现")`,标注哪个 Block 会实现
- `from __future__ import annotations` 启用现代类型注解

#### A.1.3 `backend/src/main.py`(必须可运行)

最小可启动的 FastAPI app:

```python
"""FastAPI app entry point. Block A 只实现 /health 验活路由。"""
from __future__ import annotations
from fastapi import FastAPI
from contextlib import asynccontextmanager
from src.config import settings

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Block A: 占位,Block B 之后这里加 LLM 客户端预热、数据库连接等
    yield

app = FastAPI(title="Block-7 Sim Backend", version="0.1.0", lifespan=lifespan)

@app.get("/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}
```

#### A.1.4 `backend/src/config.py`

加载 `.env` 并提供类型化的配置对象(用 pydantic-settings 或简单 dataclass 都行):

```python
"""全局配置,从 .env 加载。"""
from __future__ import annotations
import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

@dataclass(frozen=True)
class Settings:
    deepseek_api_key: str
    deepseek_base_url: str
    deepseek_model_pro: str
    deepseek_model_flash: str
    backend_host: str
    backend_port: int
    sqlite_path: str
    log_level: str
    log_dir: str

settings = Settings(
    deepseek_api_key=os.getenv("DEEPSEEK_API_KEY", ""),
    deepseek_base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
    deepseek_model_pro=os.getenv("DEEPSEEK_MODEL_PRO", "deepseek-v4-pro"),
    deepseek_model_flash=os.getenv("DEEPSEEK_MODEL_FLASH", "deepseek-v4-flash"),
    backend_host=os.getenv("BACKEND_HOST", "127.0.0.1"),
    backend_port=int(os.getenv("BACKEND_PORT", "8000")),
    sqlite_path=os.getenv("SQLITE_PATH", "./backend/data/sim.db"),
    log_level=os.getenv("LOG_LEVEL", "INFO"),
    log_dir=os.getenv("LOG_DIR", "./logs"),
)
```

#### A.1.5 `backend/tests/test_smoke.py`

最小烟测,验证 import 链通畅:

```python
"""Block A 烟测:验证所有模块可 import,/health 路由返回 200。"""
from fastapi.testclient import TestClient
from src.main import app

def test_health():
    client = TestClient(app)
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"

def test_imports():
    """所有占位模块都能 import,即使未实现"""
    from src.agent import runtime, scheduler, planning, perception, reflection
    from src.llm import deepseek, prompt_builder
    from src.memory import schema, store, compression
    from src.api import routes, websocket
```

---

### A.2 Godot 客户端骨架

#### A.2.1 `godot_client/project.godot`

Godot 4 项目配置文件。关键设置:

- `application/config/name = "Block7Sim"`
- `application/run/main_scene = "res://scenes/Main.tscn"`
- `display/window/size/viewport_width = 1280`
- `display/window/size/viewport_height = 720`
- `rendering/textures/canvas_textures/default_texture_filter = 0` (Nearest,像素艺术友好)
- `[autoload]` 注册全局单例:
  - `GameClock = "*res://scripts/game_clock.gd"`
  - `BackendClient = "*res://scripts/backend_client.gd"`

#### A.2.2 `godot_client/scenes/Main.tscn`

主场景,Node2D 根节点 + 一个 Label 显示 "Block-7 Sim — Day 1 Block A OK"。挂载 `res://scripts/main.gd`。

#### A.2.3 GDScript 文件

| 文件 | 职责 | Block A 实现深度 |
|---|---|---|
| `scripts/main.gd` | 主场景控制 | `_ready()` 打印日志 + 显示 Label |
| `scripts/game_clock.gd` | 游戏时间系统(autoload 单例) | 仅声明 `game_time: float = 0.0` 与 `time_scale: float = 60.0`,`_process(delta)` 累加 |
| `scripts/backend_client.gd` | HTTP / WebSocket 客户端(autoload 单例) | 仅声明 `health_check()` 函数,内部用 `HTTPRequest` 节点访问 `http://127.0.0.1:8000/health`,`_ready()` 时自动调用一次并 `print()` 结果 |
| `scripts/agents/AgentNode.gd` | 单个 agent 的可视节点 | 仅类声明 + `@export var agent_id: String`,`_ready()` 留空 |

#### A.2.4 GDScript 编码规范

- 文件顶部:`extends <Node>` 后空一行,加注释 `## <模块说明>`
- 所有类成员加类型注解(`var foo: int = 0`,`func bar(x: float) -> void:`)
- 占位函数体用 `pass` + 注释 `# Block X: implement this`

---

### A.3 顶层文件

#### A.3.1 `Makefile`(给 mac/linux 用)与 `dev.ps1`(给 Windows PowerShell 用)

提供常用开发命令的快捷方式。

**`Makefile`**(顶层):

```makefile
.PHONY: install backend test lint godot

install:
	cd backend && pip install -e ".[dev]"

backend:
	cd backend && uvicorn src.main:app --reload --host 127.0.0.1 --port 8000

test:
	cd backend && pytest -v

lint:
	cd backend && ruff check src tests && mypy src

godot:
	@echo "Open godot_client/project.godot in Godot 4 editor"
```

**`dev.ps1`**(顶层,Windows 用户首选):

```powershell
# 用法:.\dev.ps1 install | backend | test | lint
param([string]$cmd = "help")
switch ($cmd) {
    "install" { Push-Location backend; pip install -e ".[dev]"; Pop-Location }
    "backend" { Push-Location backend; uvicorn src.main:app --reload --host 127.0.0.1 --port 8000; Pop-Location }
    "test"    { Push-Location backend; pytest -v; Pop-Location }
    "lint"    { Push-Location backend; ruff check src tests; mypy src; Pop-Location }
    default   { Write-Host "用法: .\dev.ps1 [install|backend|test|lint]" }
}
```

#### A.3.2 `.env`(从 `.env.example` 复制并填入真实 API key)

**注意**:`.env` 已在 `.gitignore` 中,Claude Code 应主动从 `.env.example` 复制一份,但**`DEEPSEEK_API_KEY` 字段保持原样,不要填值**——由 Eric 手动填入真实 key。完成后提示 Eric。

#### A.3.3 `docs/CLAUDE.md`(给 Claude Code 看的项目说明)

写一份简短的项目说明,内容:
- 项目代号、当前阶段
- 目录结构总览(自动生成的 tree)
- 关键约束:不使用 embedding;严格遵守 4 层 prompt 缓存结构;Action Queue 永不阻塞游戏循环
- Block 路线图(A→B→C→D→E→F→G→H)与每个 Block 的状态
- 指向 `docs/Project_Design_Document_v0_2.md` 作为权威设计文档

---

## 验收标准(Block A 必须全部通过才能进入 Block B)

执行以下 5 步,每步都必须成功:

### 验收 1:Python 依赖安装

```powershell
cd <PROJECT_ROOT>
.\dev.ps1 install
```

预期:无错误,所有依赖装齐。

### 验收 2:后端可启动

```powershell
.\dev.ps1 backend
```

预期:终端显示:
```
INFO:     Uvicorn running on http://127.0.0.1:8000
INFO:     Application startup complete.
```

### 验收 3:健康检查路由

新开一个 PowerShell 窗口:

```powershell
curl http://127.0.0.1:8000/health
```

预期返回:`{"status":"ok","version":"0.1.0"}`

### 验收 4:烟测通过

回到第一个窗口,Ctrl+C 停止后端,然后:

```powershell
.\dev.ps1 test
```

预期:`test_smoke.py` 中两个测试全部通过(`test_health`、`test_imports`)。

### 验收 5:Godot 项目可打开

手动用 Godot 4 编辑器打开 `godot_client/project.godot`,按 F5 运行 Main 场景。

预期:窗口弹出,显示 "Block-7 Sim — Day 1 Block A OK",**且 Godot 控制台显示** `Backend health check: ok`(说明 BackendClient 单例已成功调用后端 /health,**前提是后端正在运行**)。

如果后端没启动,Godot 控制台会显示连接失败——这是正常的,不影响 Block A 验收。

---

## 验收完成后的 git commit

Claude Code 在所有验收通过后,主动执行:

```powershell
cd <PROJECT_ROOT>
git add .
git commit -m "Day 1 Block A: complete project skeleton (Python + Godot)"
```

---

## 注意事项(严格遵守)

1. **不要写业务逻辑**。Action Queue 调度、LLM 调用、SQLite schema、planning/reflection 全部留空 + `NotImplementedError`,标注 Block B/C/D 实现。
2. **不要使用 embedding 或向量检索**。任何想要引入 sentence-transformers / faiss / chromadb / langchain 的冲动都是错的——参见 v0.2 文档第 0 节变更项 #1。
3. **严格遵守目录结构**。Cowork 已搭好的目录不要新增/重命名;`.gitkeep` 文件可以随对应目录有真实内容后顺手 `git rm`。
4. **prompt 模板必须按 4 层缓存结构**(Layer 0 / 1 / 2 / 3),即使 Block A 不实现真实 prompt,`prompt_builder.py` 的函数签名要预留这个结构。参见 v0.2 文档 §2.2。
5. **Python 版本目标 3.11+**。如果你检测到环境是 3.10 或更低,**停止并提示 Eric**,不要尝试降级依赖。
6. **不要联网下载额外资源**。除 pip install 必要依赖外,不要拉镜像、不要克隆其他仓库、不要写"参考 XXX 项目"的占位代码。
7. **遇到任何决策不确定**,在代码里留 `# TODO(Block X): ...` 注释,继续推进。不要中途询问 Eric——Block A 的目标就是让骨架先立起来。
8. **每完成一个文件**,用 `git status` 确认它被正确跟踪。

---

## 给 Eric 的最后说明(Claude Code 完成时一并报告)

Claude Code 完成 Block A 后,在最终消息中总结:

- 创建了多少个文件(分 Python / Godot / 顶层)
- 5 项验收的实际结果(全部通过 / 哪一项失败 + 原因)
- `.env` 文件状态(是否提示 Eric 填 API key)
- 是否已 git commit
- **下一步明确建议**:Eric 应该在主对话回复"Block A 完成,请发 Block B 任务包"
