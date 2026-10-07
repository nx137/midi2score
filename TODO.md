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

## 阶段 3：目标偏离检测（已完成，待用户确认）

| ID | 待办 | blocking | 状态 |
|:--|:--|:--|:--|
| T3-1 | `task_alignment` 字段：`aligned` / `partially_aligned` / `conflicting` | — | done |
| T3-2 | verifier 校验：服务 GOAL-1、不违反 HC/GV、是否需要用户确认 | — | done |
| T3-3 | `conflicting` → `interrupt()` 暂停；普通 approve 不放行，需显式 override | — | done |
| T3-4 | 程序不得自动修改 `TASK_CHARTER.md`（无写路径 + 意图拦截 + 哈希校验） | — | done |

## 阶段 4：测试（已完成）

| ID | 待办 | blocking | 状态 |
|:--|:--|:--|:--|
| T4-1 | 相同 thread_id 恢复状态 | — | done（test_ac1） |
| T4-2 | 不同 thread_id 相互隔离 | — | done（test_ac2） |
| T4-3 | store 跨 thread 读取长期决策 | — | done（test_ac3） |
| T4-4 | `TASK_CHARTER.md` 不被普通任务自动修改 | — | done（test_ac4，哈希+mtime） |
| T4-5 | 目标冲突进入人工确认 | — | done（test_ac5） |
| T4-6 | 进程重启后从持久化后端恢复 | — | done（test_ac6，真双进程） |

## 科研侧起步（阶段 2–4 完成后启动，需另行批准）

| ID | 待办 | blocking | 状态 |
|:--|:--|:--|:--|
| R1-1 | 建独立环境并 pin 版本（`.venv-research` + `requirements-research.txt`） | — | done（EV-S14） |
| R1-2 | 获取 CPJKU/asap-dataset@v2.1.1：已完成（HEAD/tag/1,305 条/465,861,631 B 全部命中，见 EV-S4） | — | done |
| R1-3 | MuseScore Studio 4.7.5 安装核验（--version → 4.7.5, exit 0，见 EV-S5） | — | done |
| R1-3b | MuseScore CLI 导出探针（20 正样本 + 2 负对照，20/20 成功，0 真否决） | — | done（EV-S15/S16） |
| R1-3c | manifest SHA256 口径确认：已复现（CSV 列/排序/行尾 + 该 CSV 的 sha256），工具与产物入库 | — | done |
| R1-3d | R1-3b/G0 判据口径 → 已由 controller 裁定（D-0025：T1–T3 + 恒等式为诊断量 + 作废带宽） | — | done |
| R1-3e | 导出统一加 `-f`（规避 4/20 的 exit-1320） | — | done（EV-S15） |
| R1-3f | **全量 68 首 Tier 分级与分位点**（按 D-0025） | — | done（EV-S17） |
| R1-3g | T1/T3 互斥化 → 已裁定（D-0027 选 A + D-0029 五格谓词含 T4） | — | done |
| R1-3h | 二值化 / 反演指标 / 倒置对 / repeat 分组 → 已裁定（D-0030–D-0033） | — | done |
| R1-3i | **导出侧交付 1–4**（68+3 导出复现 / 五格 Tier / 分位点 / 裁定5 逐值一致） | — | done（EV-S19–S22） |
| R1-3j | **待裁定**：分位点估计量（D-0035；R-7 P5=0.91485 vs nearest_rank 0.8837） | controller 裁定 | blocked |
| R1-4a | G1' 交付 5：反演一致度（0/±1/±2 + micro/macro + 绝对计数） | R1-3j | blocked |
| R1-4b | G1' 交付 6：主表划分冻结（70/10/20、seed 20260101、曲目/变体同折、SHA256） | R1-3j | blocked |

## 明确不做（YAGNI）

- `conversation_summary.md`、向量库 / 语义检索、Web API / UI、多智能体 supervisor、Postgres、LLM 供应商抽象层、未来需求脚手架。
