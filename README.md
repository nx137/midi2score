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