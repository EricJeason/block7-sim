# Day 1 Block B — DeepSeek 客户端 + 4 层 Prompt 缓存 + 命中率验证

> **派发对象**:Claude Desktop App 的 Code session(关闭 worktree,直接在 main 分支工作)
> **预计时长**:45–75 分钟(包含真实 API 调用等待)
> **预计真实 API 成本**:¥1–3(用于命中率验证)
> **依赖**:Block A 已实落 + `.env` 中 `DEEPSEEK_API_KEY` 已填真实 key

---

## 任务上下文

**项目**:Block-7 生成式智能体社会模拟器
**当前阶段**:Day 1, Block B(整个项目最关键的硬关卡)
**架构总纲**:`docs/Project_Design_Document_v0_2.md`,**重点章节 §2.2(4 层 Prompt 缓存)、§2.3(LLM 调度策略)、§3.2(成本预算)**

**Block A 已交付**:
- ✅ FastAPI 骨架 + 健康检查
- ✅ `backend/src/llm/deepseek.py` 占位类
- ✅ `backend/src/llm/prompt_builder.py` 占位 4 层签名
- ✅ pytest 框架就绪

**本 Block 必须在 Block A 基础上**实现 LLM 客户端,**不要新增不相关功能**(Memory/Action Queue/Reflection 是 Block C/D/E 的事)。

---

## 任务目标(必须全部达成才算 Block B 通过)

| # | 目标 | 验收标准 |
|---|---|---|
| 1 | DeepSeek 异步客户端可用 | 单次调用成功返回结果,延迟 < 5 秒 |
| 2 | 思考模式分级正确 | non-think / think-high 都能调通,响应包含正确字段 |
| 3 | 4 层 prompt 缓存结构正确实现 | 单测验证 4 层顺序、内容、可追加性 |
| 4 | **缓存命中率 ≥ 90%** | 30 次模拟调用的 cache_hit_tokens / total_input_tokens ≥ 0.90 |
| 5 | 单次调用成本日志可信 | 每次调用打印输入/输出 token 数与折算成本 |
| 6 | 失败重试与超时处理 | 网络异常时按指数退避重试,30 秒总超时 |

**第 4 项是硬关卡**——达不到 90% 不算通过,但**任务包内已写好回退方案**,Claude Code 应自动执行回退,不要中途询问。

---

## 详细规格

### B.1 DeepSeek 异步客户端 — `backend/src/llm/deepseek.py`

#### B.1.1 接口设计

```python
"""DeepSeek API 异步客户端,支持 think-high / non-think 双模式与 4 层缓存。"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any
import httpx
import asyncio
import time
import logging

class ThinkMode(str, Enum):
    NON_THINK = "non_think"      # 用于对话生成、importance 打分等延迟敏感任务
    THINK_HIGH = "think_high"    # 用于 planning、reflection 等质量敏感任务
    # 注意:不实现 THINK_MAX,见 v0.2 文档 §2.3

@dataclass
class LLMUsage:
    """单次调用的 token 与成本统计。"""
    input_tokens: int
    output_tokens: int
    cache_hit_tokens: int        # DeepSeek 返回的 prompt_cache_hit_tokens
    cache_miss_tokens: int       # DeepSeek 返回的 prompt_cache_miss_tokens
    cost_yuan: float             # 按当前 75% 折扣 + 缓存价格折算
    latency_ms: float

@dataclass
class LLMResponse:
    content: str
    usage: LLMUsage
    raw: dict[str, Any] = field(default_factory=dict)

class DeepSeekClient:
    def __init__(self, api_key: str, base_url: str, timeout: float = 30.0):
        ...

    async def chat(
        self,
        messages: list[dict[str, str]],   # [{"role":"system","content":...}, ...]
        model: str = "deepseek-v4-pro",
        mode: ThinkMode = ThinkMode.NON_THINK,
        temperature: float = 0.7,
        max_tokens: int = 1000,
    ) -> LLMResponse:
        """发起一次 chat completion 调用。
        
        - 自动按 mode 设置 thinking 参数(参见 DeepSeek 官方 thinking_mode 文档)
        - 失败时指数退避重试,最多 3 次,base 1s,max 8s
        - 总超时 30s
        - 返回 LLMResponse,内含 usage 统计
        """
        ...

    async def aclose(self) -> None:
        """关闭 httpx client。"""
        ...
```

#### B.1.2 实现要点

1. **使用 httpx.AsyncClient** 单例(避免每次调用都重建连接池)
2. **base_url 拼接**:`{base_url}/v1/chat/completions`(OpenAI 兼容端点)
3. **请求头**:`Authorization: Bearer {api_key}`,`Content-Type: application/json`
4. **请求体**:
   - `model`: 传入参数
   - `messages`: 传入参数
   - `temperature`、`max_tokens`: 传入参数
   - **思考模式控制**:
     - `mode=NON_THINK` → 在 body 加 `"thinking": {"type": "disabled"}`(若 DeepSeek 当前规范不同,见下方 fallback)
     - `mode=THINK_HIGH` → 在 body 加 `"thinking": {"type": "enabled", "effort": "high"}`
5. **思考模式 API 形态可能与文档预期不一致** — 实现时按 DeepSeek 官方 `thinking_mode` 文档为准。如果发现实际 API 用 `reasoning_effort` 或 `enable_thinking` 这类字段名,以实测为准并在代码注释里记录。**这不是 bug,是 API 演化**。
6. **响应解析**:
   - `content = data["choices"][0]["message"]["content"]`
   - `usage` 字段:`prompt_tokens`、`completion_tokens`、`prompt_cache_hit_tokens`、`prompt_cache_miss_tokens`(若某字段缺失,以 0 兜底,**不要崩溃**)
7. **成本折算**(基于当前公开价格,Claude Code 实现时**直接写死这些常数**,避免引入额外配置):
   - V4-Pro 输入(cache miss):¥2 / M tokens(75% 折扣后)
   - V4-Pro 输入(cache hit):¥0.2 / M tokens(原价 1/10)
   - V4-Pro 输出:¥8 / M tokens(75% 折扣后)
   - V4-Flash 输入(cache miss):¥0.5 / M tokens
   - V4-Flash 输入(cache hit):¥0.05 / M tokens
   - V4-Flash 输出:¥2 / M tokens
   - **如果实测发现价格已变**,更新这些常数并在代码注释里写"实测于 2026-05-02"
8. **重试策略**:`tenacity` 库或手写循环都行。重试触发条件:`httpx.TimeoutException`、`httpx.ConnectError`、HTTP 5xx。**不要重试**:HTTP 4xx(那是请求错误,重试无意义)。
9. **日志**:每次调用结束后用 `logging` 输出一行结构化日志:`[deepseek] model={} mode={} input={} output={} cache_hit={} cost=¥{} latency={}ms`

---

### B.2 4 层 Prompt 缓存结构 — `backend/src/llm/prompt_builder.py`

#### B.2.1 设计原则(v0.2 文档 §2.2)

DeepSeek 的 prompt 缓存按**前缀匹配**:从 messages 数组开头开始,逐 token 匹配,直到第一个不匹配的 token 为止。**因此越靠前的内容越要稳定**。

4 层结构(从前到后):

| Layer | 内容 | 变化频率 | 期望命中率 |
|---|---|---|---|
| 0 — 静态系统 prompt | 世界观设定、行为规则、输出格式 | 永不变(占位文案 OK) | ~100% |
| 1 — Agent persona | 单个 agent 的姓名、性格、职业、背景 | 一个 agent 一份,会话内不变 | ~100% |
| 2 — 近期记忆/状态 | 最近 N 条 memory、当前位置、当前情绪 | 每次调用都可能变 | 30–60% |
| 3 — 本次具体任务 | "现在请决定下一步行动" 这种指令 | 每次都不同 | 0% |

**关键**:Layer 0 + Layer 1 的内容必须在 messages 数组里**作为同一个 system message**,且**完全字节相等**(空格、换行、标点都不能变)才能命中缓存。

#### B.2.2 接口设计

```python
"""4 层 Prompt 缓存结构构建器,严格按 v0.2 文档 §2.2 实现。"""
from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class AgentPersona:
    agent_id: str
    name: str
    age: int
    occupation: str
    personality: str  # 自由文本,例如"沉稳、谨慎、关心他人"
    background: str   # 自由文本,3–5 句话

@dataclass
class AgentRuntimeState:
    """一次 prompt 调用时 agent 的动态状态。"""
    current_location: str
    current_mood: str
    recent_memories: list[str]   # 最近 N 条 memory 的文字摘要
    game_time: str               # 例如"Day 3, 14:30"

class PromptBuilder:
    # Layer 0:静态系统 prompt(整个项目唯一一份,永不修改)
    LAYER_0_SYSTEM = """你是一个生活在虚构小镇的 NPC。
你的回答必须基于你的人格设定与当前情境,不要打破角色。
所有输出使用简体中文。
当被要求做决策时,严格按要求的 JSON 格式返回,不要添加任何解释性文字。
"""

    @classmethod
    def build_layer_1_persona(cls, persona: AgentPersona) -> str:
        """Layer 1:把 persona 渲染成稳定的文本块。同一 agent 调用中应字节相等。"""
        return (
            f"【你的人格设定】\n"
            f"姓名:{persona.name}\n"
            f"年龄:{persona.age}\n"
            f"职业:{persona.occupation}\n"
            f"性格:{persona.personality}\n"
            f"背景:{persona.background}\n"
        )

    @classmethod
    def build_layer_2_state(cls, state: AgentRuntimeState) -> str:
        """Layer 2:动态状态。每次调用都可能变化。"""
        memories_text = "\n".join(f"- {m}" for m in state.recent_memories)
        return (
            f"【当前情境】\n"
            f"游戏时间:{state.game_time}\n"
            f"所在位置:{state.current_location}\n"
            f"当前情绪:{state.current_mood}\n"
            f"近期记忆:\n{memories_text}\n"
        )

    @classmethod
    def assemble_messages(
        cls,
        persona: AgentPersona,
        state: AgentRuntimeState,
        task_prompt: str,
    ) -> list[dict[str, str]]:
        """组装 4 层结构的 messages 数组。
        
        关键:Layer 0+1 必须是同一个 system message 且字节稳定。
        Layer 2+3 作为 user message。这样 system message 整体可被 DeepSeek 缓存命中。
        """
        system_content = cls.LAYER_0_SYSTEM + "\n" + cls.build_layer_1_persona(persona)
        user_content = cls.build_layer_2_state(state) + "\n【当前任务】\n" + task_prompt
        return [
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_content},
        ]
```

**注意事项**:
1. `LAYER_0_SYSTEM` 和 `build_layer_1_persona` 输出**必须是字节稳定的纯文本**——不要在里面插入时间戳、UUID 或任何会变的东西
2. `assemble_messages` 拼接顺序固定:`Layer 0` → `Layer 1` → 作为 system message;`Layer 2` → `Layer 3` → 作为 user message

---

### B.3 缓存命中率验证脚本 — `backend/tests/test_cache_hit_rate.py`

**这是 Block B 的硬关卡**。必须真实调用 DeepSeek API。

#### B.3.1 脚本设计

```python
"""B.3 缓存命中率验证 — 真实 API 调用。

运行方式:
    cd backend
    pytest tests/test_cache_hit_rate.py -v -s --no-header

要求:
    .env 中 DEEPSEEK_API_KEY 已填真实 key
    
预期成本:¥1–3
"""
import asyncio
import os
import pytest
from src.config import settings
from src.llm.deepseek import DeepSeekClient, ThinkMode
from src.llm.prompt_builder import PromptBuilder, AgentPersona, AgentRuntimeState

# 跳过条件:没真实 key
pytestmark = pytest.mark.skipif(
    settings.deepseek_api_key in ("", "your_api_key_here"),
    reason="需要真实 DEEPSEEK_API_KEY 才能运行命中率验证",
)


@pytest.fixture
async def client():
    c = DeepSeekClient(api_key=settings.deepseek_api_key, base_url=settings.deepseek_base_url)
    yield c
    await c.aclose()


# 固定 persona — 30 次调用复用同一个,Layer 0+1 应被缓存命中
TEST_PERSONA = AgentPersona(
    agent_id="test_agent_01",
    name="李明",
    age=32,
    occupation="小镇杂货店老板",
    personality="沉稳、热情、对小镇老主顾如数家珍",
    background="李明在镇东头开了 8 年杂货店。妻子在镇医院做护士。喜欢和客人闲聊,但晚上 8 点准时打烊回家。",
)


def make_state(turn: int) -> AgentRuntimeState:
    """生成第 turn 轮的动态状态(每轮都不同,模拟真实游戏循环)。"""
    return AgentRuntimeState(
        current_location="杂货店",
        current_mood="平静",
        recent_memories=[
            f"刚刚有个客人买了第 {turn} 包香烟",
            f"妻子打来电话提醒晚上吃饭",
        ],
        game_time=f"Day 1, {10 + turn // 6}:{(turn * 10) % 60:02d}",
    )


@pytest.mark.asyncio
async def test_cache_hit_rate(client):
    """跑 30 次调用,验证总体缓存命中率 ≥ 90%。"""
    total_input = 0
    total_cache_hit = 0
    total_cost = 0.0
    latencies = []

    for turn in range(30):
        state = make_state(turn)
        messages = PromptBuilder.assemble_messages(
            persona=TEST_PERSONA,
            state=state,
            task_prompt="请用一句话描述你现在最想做的事(20 字以内)。",
        )
        resp = await client.chat(
            messages=messages,
            model=settings.deepseek_model_pro,
            mode=ThinkMode.NON_THINK,  # 命中率测试用 non-think,快且便宜
            max_tokens=80,
        )
        total_input += resp.usage.input_tokens
        total_cache_hit += resp.usage.cache_hit_tokens
        total_cost += resp.usage.cost_yuan
        latencies.append(resp.usage.latency_ms)
        print(
            f"[turn {turn:2d}] input={resp.usage.input_tokens} "
            f"cache_hit={resp.usage.cache_hit_tokens} "
            f"cost=¥{resp.usage.cost_yuan:.4f} "
            f"lat={resp.usage.latency_ms:.0f}ms"
        )

    hit_rate = total_cache_hit / total_input if total_input else 0.0
    avg_latency = sum(latencies) / len(latencies)
    p95_latency = sorted(latencies)[int(len(latencies) * 0.95)]

    print(f"\n===== 命中率验证总结 =====")
    print(f"总输入 tokens:{total_input}")
    print(f"总缓存命中 tokens:{total_cache_hit}")
    print(f"命中率:{hit_rate:.1%}")
    print(f"总成本:¥{total_cost:.4f}")
    print(f"平均延迟:{avg_latency:.0f} ms")
    print(f"P95 延迟:{p95_latency:.0f} ms")

    # 硬验收
    assert hit_rate >= 0.90, f"命中率 {hit_rate:.1%} 未达 90%"
    assert avg_latency < 5000, f"平均延迟 {avg_latency:.0f}ms 超过 5s"
```

#### B.3.2 命中率不达标时的回退方案(必须自动执行)

如果第一次跑完 `hit_rate < 0.90`,**Claude Code 不要直接报告失败**,按以下顺序自动尝试修复:

**回退 1**:第 1 次调用通常是"冷启动",缓存还没建立。修改测试脚本:
- 总轮数从 30 改为 35
- 命中率统计**只计算第 5 轮之后的 30 轮**(跳过前 5 轮预热)

**回退 2**:如果仍 < 90%,检查 Layer 0+1 是否真的字节稳定:
- 在 `PromptBuilder.assemble_messages` 内加一行 `print(repr(messages[0]['content'][:200]))`
- 跑 3 次,确认输出**完全一致**(包括所有空格换行)
- 若不一致,定位是哪个 f-string 引入了变化

**回退 3**:如果命中率仍 < 90%,可能是 DeepSeek 缓存的最小 token 阈值问题。把 `LAYER_0_SYSTEM` 加长到 ≥ 1024 tokens(填充更详细的小镇世界观与行为规则),再测。

**回退 4(终止条件)**:如果上述三个都试过仍 < 90%,**停止重试**,在最终报告里贴出三次测试的完整数据,并标注:
> ⚠️ 缓存命中率未达 90% 目标,实测最高 X%。建议 Eric 检查 DeepSeek 当前缓存策略文档,确认价格模型是否仍按 v0.2 文档预算。

---

### B.4 配置文件更新 — `backend/pyproject.toml`

如果 `httpx`、`tenacity`、`pytest-asyncio` 不在依赖里,加上。需要重新跑一次 `pip install -e ".[dev]"`。

---

### B.5 `.env` 检查

**Claude Code 不要修改 `.env` 内容**(API key 是用户敏感数据)。

但要在 Block B 开始前**主动验证**:

```python
from src.config import settings
assert settings.deepseek_api_key not in ("", "your_api_key_here"), \
    "请先在 .env 中填入真实 DEEPSEEK_API_KEY"
```

如果 assertion 失败,立即停止并提示 Eric。

---

### B.6 烟测扩展 — 更新 `backend/tests/test_smoke.py`

在原有 `test_health` / `test_imports` 基础上,**增加但不替换**:

```python
def test_prompt_builder_layer_stability():
    """Layer 0+1 在两次构建中字节相等。"""
    from src.llm.prompt_builder import PromptBuilder, AgentPersona, AgentRuntimeState
    persona = AgentPersona(
        agent_id="x", name="测试", age=30, occupation="测试员",
        personality="测试性格", background="测试背景",
    )
    state1 = AgentRuntimeState(current_location="A", current_mood="平静",
                                recent_memories=["m1"], game_time="Day 1, 10:00")
    state2 = AgentRuntimeState(current_location="B", current_mood="开心",
                                recent_memories=["m2"], game_time="Day 1, 11:00")
    msgs1 = PromptBuilder.assemble_messages(persona, state1, "任务1")
    msgs2 = PromptBuilder.assemble_messages(persona, state2, "任务2")
    # system message(Layer 0+1)必须完全一致
    assert msgs1[0]["content"] == msgs2[0]["content"]
    # user message(Layer 2+3)必须不同
    assert msgs1[1]["content"] != msgs2[1]["content"]


def test_deepseek_client_init():
    """DeepSeekClient 能被实例化(不发起真实调用)。"""
    from src.llm.deepseek import DeepSeekClient
    c = DeepSeekClient(api_key="dummy", base_url="https://example.com")
    assert c is not None
```

这两个测试**不烧 API 钱**,可以在每次 push 前跑。

---

## 执行流程(必须按顺序)

1. ✅ 验证 Block A 仍完好:`pytest tests/test_smoke.py -v` 全绿
2. 🛠 实现 `prompt_builder.py`(纯逻辑,不烧钱)
3. 🛠 实现 `deepseek.py`(httpx 客户端,不烧钱)
4. 🧪 跑 `test_smoke.py` 新增的两个测试(不烧钱)
5. 🛠 实现 `test_cache_hit_rate.py`
6. 🔥 **首次烧钱**:跑 `pytest tests/test_cache_hit_rate.py -v -s`
7. 📊 看命中率结果:
   - ≥ 90% → 进入第 8 步
   - < 90% → 自动执行 B.3.2 的回退 1/2/3
8. ✅ git commit:`Day 1 Block B: DeepSeek client + 4-layer prompt cache + cache hit rate {X}%`

---

## 报告格式(Block B 完成时必须包含)

1. **创建/修改的文件清单**(按 backend/src/llm、backend/tests、其他分类)
2. **不烧钱的测试结果**(`test_smoke.py` 全部 PASSED)
3. **烧钱测试的真实结果**:
   - 30 次调用的逐行日志(input/cache_hit/cost/latency)
   - 总命中率(精确到小数点后 1 位)
   - 总成本(精确到 0.0001 元)
   - 平均/P95 延迟
4. **回退路径执行情况**(如果走过)
5. **新 commit hash**
6. **下一步建议**

报告末尾必须包含:

> Block B 完成。请 Eric 在主对话回复"Block B 完成,请发 Block C 任务包"。

---

## 严禁事项

1. **不要修改 `.env`**(API key 是用户私密)
2. **不要 mock DeepSeek API**——B.3 必须是真实调用
3. **不要在测试里跑超过 35 次调用**(成本控制,任何额外调用先问 Eric)
4. **不要引入 langchain / llamaindex / openai-python 库**——本项目只用 httpx 直连
5. **不要引入 embedding / 向量检索相关依赖**(参见 v0.2 文档约束)
6. **不要并发调用 DeepSeek 测试缓存命中率**——并发会污染统计,必须串行
7. **不要修改 Block A 已交付的功能**(FastAPI、健康检查、Godot 端)
8. **遇到决策不确定**,留 `# TODO(Block C/D/E)` 注释继续推进,**绝对不要中途询问 Eric**——除非命中率回退方案全部失败(终止条件)
