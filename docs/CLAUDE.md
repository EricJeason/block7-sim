# CLAUDE.md — Block-7 项目说明(给 Claude Code 看)

**项目代号**:Block-7 生成式智能体社会模拟器
**当前阶段**:Day 1 — Block A 已完成,等待启动 Block B(DeepSeek 客户端)
**权威设计文档**:[`Project_Design_Document_v0_2.md`](Project_Design_Document_v0_2.md)

---

## 目录结构总览

```
block7-sim/
├── backend/                 Python 后端(FastAPI + DeepSeek + SQLite)
│   ├── pyproject.toml
│   ├── src/
│   │   ├── main.py          FastAPI 入口(Block A:仅 /health)
│   │   ├── config.py        .env 加载 + Settings dataclass
│   │   ├── agent/           AgentRuntime / scheduler / planning / perception / reflection
│   │   ├── llm/             DeepSeek 客户端 + 4 层 prompt 缓存构建器
│   │   ├── memory/          SQLite schema / store / 压缩(关键词召回,无向量)
│   │   └── api/             FastAPI 路由 + WebSocket
│   ├── tests/               pytest(Block A 烟测在此)
│   └── data/                运行期 SQLite 与 persona YAML
├── godot_client/            Godot 4 客户端
│   ├── project.godot
│   ├── scenes/Main.tscn     主场景
│   └── scripts/             main / game_clock / backend_client / agents/
├── docs/                    设计文档与本文件
├── logs/                    运行日志输出目录
├── Makefile                 mac/linux 开发命令
├── dev.ps1                  Windows PowerShell 开发命令(install/backend/test/lint)
├── .env / .env.example      环境变量(.env 不入库)
└── README.md
```

---

## 关键约束(写代码前必读)

1. **不使用 embedding / 向量检索**。Memory 召回走关键词倒排 + 时间衰减打分。
   严禁引入 sentence-transformers / faiss / chromadb / langchain。
   (设计文档第 0 节变更项 #1)
2. **严格遵守 4 层 prompt 缓存结构**:
   - Layer 0:系统指令 / 角色框架(进程级常驻)
   - Layer 1:agent 不变特征(persona)
   - Layer 2:当日相对稳定上下文(当日规划、反思、关键 memory 摘要)
   - Layer 3:本次调用专属(当前观察、即时输入)
   每次调用前 3 层必须生成完全一致的 token 序列以触发 DeepSeek prompt cache。
3. **Action Queue 永不阻塞游戏循环**。Godot 端 60Hz tick 与 Python 端 LLM 调用全异步,
   通过 WebSocket 解耦,LLM 慢响应不能让 sim tick 停顿。
4. **Pro vs Flash 双模型分工**:Pro 用于反思 + 粗粒度规划,Flash 用于细粒度规划与对话。

---

## Block 路线图

| Block | 内容 | 状态 |
|---|---|---|
| **A** | 项目骨架(Python + Godot 占位 + 顶层脚本) | ✅ 已完成 |
| **B** | DeepSeek 客户端 + 4 层 prompt 构建器 | ⏳ 下一步 |
| **C** | SQLite schema + memory store CRUD + 关键词查询 | ⏳ |
| **D** | AgentRuntime + Action Queue 调度器 | ⏳ |
| **E** | 粗粒度 / 细粒度规划 | ⏳ |
| **F** | 同场所事件传播(perception) | ⏳ |
| **G** | 每日反思 + memory 压缩 | ⏳ |
| **H** | FastAPI 路由 + WebSocket + Godot 端联调 | ⏳ |

每个 Block 完成后由 Eric 验收并发下一个任务包。

---

## 给 Claude Code 的工作准则

- **只搭架子,不写业务逻辑**。占位函数都用 `raise NotImplementedError("Block X 实现")` 标注归属。
- **目录结构由设计文档决定**,不要新增 / 重命名顶层目录。
- **遇决策不确定**,在代码里留 `# TODO(Block X): ...` 注释继续推进,不打断 Eric。
- **不联网下载额外资源**,除 pip install 必要依赖外不拉镜像、不克隆其他仓库。
