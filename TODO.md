# TODO.md — 可执行待办

> 状态：`todo` / `doing` / `blocked` / `done`。`blocking` 为前置依赖。
> **阶段推进必须等待用户逐阶段确认**；确认前不得进入下一阶段。
> 本文件只放待办；决策见 `DECISIONS.md`，假设见 `ASSUMPTIONS.md`。

## 阶段 1：项目规则与科研任务文件（当前）

| ID | 待办 | owner | blocking | 状态 |
|:--|:--|:--|:--|:--|
| T1-1 | `git init`（main）与 `.gitignore` | codex | — | done |
| T1-2 | `AGENTS.md`：章程最高优先、五类信息分区、偏离先报告、完工更新、证据诚实、每改必测 | codex | — | done |
| T1-3 | `TASK_CHARTER.md`：总目标 / 范围 / 非目标 / 硬约束 HC-01–HC-16 + GV-01–GV-06 / 修改流程 | codex | — | done |
| T1-4 | `RESEARCH_QUESTIONS.md`、`STATE.md`、`DECISIONS.md`、`ASSUMPTIONS.md`、`EVIDENCE.md`、`TODO.md`、`ACCEPTANCE.md` | codex | — | done |
| T1-5 | 文档级校验（文件齐全 / 硬约束可机读 / 无 conversation_summary.md）并记录证据 | codex | — | done |
| T1-6 | 展示 `git diff` 并提交阶段 1 | codex | — | done |

## 阶段 2：LangGraph 最小骨架（已完成，待用户确认）

| ID | 待办 | blocking | 状态 |
|:--|:--|:--|:--|
| T2-1 | 定义结构化 `TaskState`（TypedDict）+ Pydantic 记录模型 | — | done |
| T2-2 | planner / executor / verifier / human_review 四节点 | — | done |
| T2-3 | checkpointer（SqliteSaver）+ store（SqliteStore）+ 稳定 thread_id | — | done |
| T2-4 | messages 窗口裁剪（上限 20；不建 conversation_summary.md） | — | done |
| T2-5 | 最小运行示例 + 中断/恢复会话示例 | — | done |

## 阶段 3：目标偏离检测（未启动）

| ID | 待办 | blocking | 状态 |
|:--|:--|:--|:--|
| T3-1 | `task_alignment` 字段：`aligned` / `partially_aligned` / `conflicting` | 阶段 2 确认 | todo |
| T3-2 | verifier 校验：服务 GOAL-1、不违反 HC/GV、是否需要用户确认 | T3-1 | todo |
| T3-3 | `conflicting` → `interrupt()` 暂停并要求人工确认 | T3-1 | todo |
| T3-4 | 程序不得自动修改 `TASK_CHARTER.md`（charter_sha256 校验 + 只读） | T3-1 | todo |

## 阶段 4：测试（未启动）

| ID | 待办 | blocking | 状态 |
|:--|:--|:--|:--|
| T4-1 | 相同 thread_id 恢复状态 | 阶段 3 确认 | todo |
| T4-2 | 不同 thread_id 相互隔离 | T4-1 | todo |
| T4-3 | store 跨 thread 读取长期决策 | T4-1 | todo |
| T4-4 | `TASK_CHARTER.md` 不被普通任务自动修改 | T4-1 | todo |
| T4-5 | 目标冲突进入人工确认 | T4-1 | todo |
| T4-6 | 进程重启后从持久化后端恢复 | T4-1 | todo |

## 科研侧起步（阶段 2–4 完成后启动，需另行批准）

| ID | 待办 | blocking | 状态 |
|:--|:--|:--|:--|
| R1-1 | 建独立环境，按计划书 §10.1 pin 版本（partitura 1.9.0 / mido 1.3.3 / music21 10.5.0 / parangonar 3.3.3） | 系统可用 | todo |
| R1-2 | 获取 CPJKU/asap-dataset@v2.1.1：已完成（HEAD/tag/1,305 条/465,861,631 B 全部命中，见 EV-S4） | — | done |
| R1-3 | MuseScore Studio 4.7.5 安装核验（--version → 4.7.5, exit 0，见 EV-S5） | — | done |
| R1-3b | 测通 MuseScore CLI 导出（3 首样本产生 CC64，比值 ≈1.0） | R1-2 / R1-3 | todo |
| R1-3c | manifest SHA256 口径确认：已复现（CSV 列/排序/行尾 + 该 CSV 的 sha256），工具与产物入库 | — | done |
| R1-4 | **G1'**：43/43 主轴乐谱回放通道端到端 + 反演基线 + 划分冻结（先决闸门） | R1-2 / R1-3 | todo |

## 明确不做（YAGNI）

- `conversation_summary.md`、向量库 / 语义检索、Web API / UI、多智能体 supervisor、Postgres、LLM 供应商抽象层、未来需求脚手架。
