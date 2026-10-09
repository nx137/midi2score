# midi2score — 科研任务管理与执行系统

基于 **LangGraph** 的科研任务管理 / 执行系统，用结构化状态 + checkpointer + store 管理以
`PedNotate_Plan_v3.0.md` 为总纲的科研任务。

## 先读这些

0. `HANDOFF.md` — 本地会话接手入口与当前状态摘要
1. `TASK_CHARTER.md` — 最高优先级目标与硬约束（**不可变**）
2. `AGENTS.md` — 仓库规则与工作流
3. `STATE.md` — 当前阶段与下一步
4. `DECISIONS.md` / `ASSUMPTIONS.md` / `EVIDENCE.md` / `TODO.md` / `ACCEPTANCE.md`

## 快速开始

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest -q          # 测试
.\.venv\Scripts\python.exe -m research_agent.demo  # 运行 + 中断 + 恢复示例
```

## 架构

```
START → planner → executor → verifier ─┬─ passed ──────────────→ human_review → END
                  ↑                     └─ failed 且未超迭代上限 → planner
                                        （超过 max_iterations → human_review）
```

| 组件 | 实现 | 说明 |
|:--|:--|:--|
| 短期状态 | `SqliteSaver`（`data/checkpoints.db`） | 每个 super-step 落盘；按 thread 隔离 |
| 长期记忆 | `SqliteStore`（`data/store.db`） | 跨 thread 的已确认决策 / 事实 |
| thread_id | `research:{project_id}:{task_id}` | **稳定可推导**，禁止随机生成 |
| 上下文 | `messages` 保留最近 20 条 | 更早信息进结构化字段；**不建 conversation_summary.md** |
| 状态模型 | `src/research_agent/schemas.py` | TypedDict 根状态 + Pydantic 记录 |

状态字段（任务对象，不塞进 messages）：`charter_*`（不可变章程）、`research_questions`、
`work_packages`、`decisions`、`assumptions`、`evidence`、`todos`、`acceptance`、
`current_phase`、`verification`、`alignment`、`recalled_decisions`、`approval`。

## 控制平面（D-0083）

真实科研执行前必须先通过以下链路：

```text
TASK_CHARTER + Plan + DECISIONS + FIELD_DEFINITIONS
        ↓
Goal Contract（只读、带来源哈希）
        ↓
Context Packet（目标/阶段/约束/confirmed decisions/recent messages）
        ↓
preflight policy → command allowlist → shell=False argv execution
        ↓
ExecutionRecord + candidate Evidence
        ↓
postflight verifier → verified / partial / conflicting
        ↓
human_review（hard deny 不可 override）
```

- 未挂接 `GOAL-1`、目标相关性不足或命令越权的 work package 会在执行前进入 `blocked_by_policy`。
- executor 只能产生 candidate Evidence；只有 verifier 能把完整证据提升为 `verified`。
- 所有命令记录 `argv`、cwd、exit code、stdout/stderr hash、环境摘要和产物 hash。
- `thread_id` 由 `project_id/task_id` 稳定推导，调用方不得覆盖。

## 可选 LLM（DeepSeek / OpenAI-compatible）

默认关闭；未配置时使用 stub。启用示例：

```powershell
$env:MIDI2SCORE_LLM_ENABLED="true"
$env:MIDI2SCORE_LLM_PROVIDER="deepseek"
$env:MIDI2SCORE_LLM_MODEL="deepseek-flash"
$env:MIDI2SCORE_LLM_BASE_URL="https://api.deepseek.com"
$env:MIDI2SCORE_LLM_REASONING_EFFORT="high"
$env:MIDI2SCORE_LLM_DISABLE_RESPONSE_STORAGE="true"
$env:MIDI2SCORE_LLM_MAX_CONTEXT_CHARS="300000"
$env:MIDI2SCORE_LLM_MAX_TOKENS="65536"
$env:DEEPSEEK_API_KEY="<local-secret>"
```

本工作区的本地配置文件是 `config/llm.local.env`（已 gitignore）：只需把其中的 `DEEPSEEK_API_KEY` 占位符替换为真实 key。也可参考 `config/llm.env.example`。LLM 只作为 planner/说明器，不能执行命令、修改权限或产生 `verified` Evidence；API key 不进入仓库。


## 中断与恢复

`human_review` 节点用 `interrupt()` 暂停，恢复时传 `Command(resume=...)`：

```python
from langgraph.types import Command
cfg = thread_config("midi2score", "PHASE-2")      # stable thread_id
graph.invoke(initial_state("midi2score"), cfg)     # 停在 human_review
graph.invoke(Command(resume="approve"), cfg)       # 恢复
graph.get_state(cfg)                               # 读回状态
list(graph.get_state_history(cfg))                 # 检查点历史
```

## 边界

- verifier 输出三值目标偏离判定：`aligned` / `partially_aligned` / `conflicting`。
  `conflicting`（章程哈希漂移、或检测到修改章程的意图）一律暂停；**普通 approve 不放行，必须显式 override**，
  且会记为 `source=human_override` 的决策。
- 默认使用 stub 模型，**不引入任何 LLM 供应商 SDK**。
- 原始语料 `data/asap-dataset/` 与本地 SQLite 均**不入库**。

## 目标偏离检测（阶段 3）

| 判定 | 触发条件 | 处置 |
|:--|:--|:--|
| `aligned` | 服务于 GOAL-1，且无 HC/GV 违规、无待确认问题 | 进入人在环闸门批准 |
| `partially_aligned` | 未违反硬约束，但存在待确认项（如证据 `verified` 无 command、工作包未挂到任何 RQ） | 暂停，需人工确认 |
| `conflicting` | 违反 HC/GV：章程哈希漂移、或检测到修改 `TASK_CHARTER.md` 的意图 | **暂停，普通 approve 不放行**；只有显式 `override` 才继续 |

章程保护是三重机制：① 代码中不存在写 `TASK_CHARTER.md` 的路径；② 执行器对"修改章程"意图直接拒绝
（关键词启发式，保守起见宁可误报）；③ verifier 每次比对文件 sha256，漂移即 `conflicting`。