# Block-7 · 暮谷镇

> 基于 [Stanford《Generative Agents: Interactive Simulacra of Human Behavior》](https://arxiv.org/abs/2304.03442) 的中文复刻 + 创造性扩展。**12 个由 LLM 驱动的 NPC,在一个有限世界(暮谷镇)里自主活动、对话、互相感知、跨日反思,产生涌现叙事**。

---

## 它能做什么

- **12 个独立人格**:每个 agent 22 字段富 schema(背景 / 性格 / 秘密 / 内心冲突 / 关系网),由 DeepSeek V4-Pro 驱动
- **暮谷镇世界观**:架空异世界 / 类近代奇幻 / 循环 horror。预言中的"大魔潮"临近,治愈者梦境同步,寂塔遗迹的字迹被人擦掉……
- **完整的 sim 循环**:Planner(粗+细两层规划)→ Scheduler(永不阻塞游戏循环)→ Perception(同场所事件传播)→ DialogueSession(多轮 LLM 对白)→ Reflection(跨日反思 + memory 压缩)
- **真实 API 实测产出涌现剧情**(例:千绫和小璎师徒对话谈"网绳磨损"/"巡逻不能再乱跑")
- **Godot 4 客户端**:4 个场所背景图、对话气泡、12 agent 实时显示、暂停按钮、反思计数、记忆面板、成本监控

## 截图

> Eric 后续补图

## 技术亮点

| 设计 | 解决什么 |
|---|---|
| **快动作慢思考** + Action Queue | 游戏循环永不等 LLM(asyncio.create_task 后台跑) |
| **4 层 Prompt 缓存** + 字节稳定前缀 | DeepSeek 缓存命中价是未命中价的 1/10,**实测命中率 92.9%** |
| **不引入向量检索** | DeepSeek V4-Pro 1M 上下文,memory 召回用 SQLite LIKE + LLM in-context recall |
| **跨日并行反思**(asyncio.Semaphore 限并发 3) | 12 agent × Pro think_high 不饿死 fine plan |
| **DialogueSession 状态机** | talk_to 触发后双方 Action Queue 暂停,LLM 多轮生成,完后写双方 memory |
| **成本可控** | 默认 paused 启动 + Godot 暂停按钮 + 阈值优化,预算 ~¥0.4/游戏日 |

## 快速开始

详见 [SETUP.md](SETUP.md)。**3 分钟即可看到 12 个 agent 在你电脑上活起来。**

简版:
```bash
# 1. clone
git clone https://github.com/<your-username>/block7-sim
cd block7-sim

# 2. 配置 DeepSeek API key(详细见 SETUP.md)
cp .env.example .env
# 编辑 .env,填入 DEEPSEEK_API_KEY=sk-...

# 3. 安装 Python 依赖
cd backend && pip install -e ".[dev]"

# 4. 启 backend(默认 paused,零成本)
python -m uvicorn src.main:app --host 127.0.0.1 --port 8000

# 5. 在 Godot 4.3+ 打开 godot_client/project.godot,按 F5
```

## 项目结构

```
block7-sim/
├── backend/                Python + FastAPI + DeepSeek
│   ├── src/
│   │   ├── agent/         scheduler / planner / perception / dialogue / reflection
│   │   ├── llm/           deepseek 客户端 + prompt builder
│   │   ├── memory/        SQLite store + compression
│   │   ├── api/           routes + websocket
│   │   └── sim/           SimEngine 主入口
│   ├── data/              世界观 yaml(world / locations / 12 personas)
│   └── tests/             122 mock + 3 真实 API 集成测试
├── godot_client/          Godot 4 客户端
│   ├── scripts/
│   ├── scenes/
│   └── assets/            场景背景 + 角色 sprite(部分占位)
├── docs/                  设计文档 / 交接包 / 历史回顾
├── scripts/               启动脚本
└── README.md / SETUP.md
```

## 文档索引

- [SETUP.md](SETUP.md) — 详细安装、配置、启动指南
- [docs/CLAUDE.md](docs/CLAUDE.md) — 项目工作守则 + 红线
- [docs/Project_Design_Document_v0_2.md](docs/Project_Design_Document_v0_2.md) — 架构总纲
- [docs/工作展望.md](docs/工作展望.md) — 接手指南 + 剩余 Block 详规
- [docs/Day1_工作总结.md](docs/Day1_工作总结.md) — 历史轨迹 + 实测数据 + 踩坑

## 致谢

- **学术基础**:Park, Joon Sung, et al. *Generative agents: Interactive simulacra of human behavior* (Stanford, 2023)
- **协作 AI**:Claude Code(Opus 4.7) × Codex(GPT 5.5)
- **LLM 提供方**:DeepSeek V4(2026-04 发布,1M 上下文 / 384K 输出)

## License

MIT(见 LICENSE 文件)。
