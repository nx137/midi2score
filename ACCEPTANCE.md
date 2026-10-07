# ACCEPTANCE.md — 验收标准

> `result` ∈ {`pass`, `fail`, `not_run`}。**未运行一律 `not_run`**，不得填 `pass`（`GV-05` / `HC-16`）。
> 每条须有可复现的判定方法（命令 / 检查方式 / 产物）。评定人须能仅凭本文件与 `EVIDENCE.md` 复现结论。

## A. 科研交付验收（对应计划书 §9.3 闸门与 §13）

| ID | 验收标准 | 判定方法 | result |
|:--|:--|:--|:--|
| AC-R1 | **G1'** 通过：43/43 主轴乐谱「印刷记号 → MuseScore 4.7.5 → CC64」全部成功 | G1' 判据 1（脚本 + 逐曲结果表） | not_run |
| AC-R2 | **G1'** 通过：反演路径（CC64 二值区间 → 逐锚点标签）与谱面记号的**一致度基线数报出**（Q2 天花板） | G1' 判据 2 | not_run |
| AC-R3 | **G1'** 通过：分层划分文件冻结并公开 hash | G1' 判据 3 | not_run |
| AC-R4 | **G2** 通过：B4 主指标（事件 F1 @ ±50ms）显著优于 B1/B2，**且逐作曲家最差折不低于基线** | E1 主表 + §6.6 统计口径 | not_run |
| AC-R5 | **G3** 通过：E1–E10 消融表齐备；域差对照 ≥1 条单调趋势；许可核实完成；复现脚本一键跑通 | G3 四条 | not_run |
| AC-R6 | 论文产出：1 篇 SCI 三区任务论文（模型为主，C1–C4） | 投稿完成 | not_run |
| AC-R7 | 开源系统可复现（代码 + 派生标注 + 复现步骤，不含原始语料/权重） | 干净环境一键复现 | not_run |

## B. 系统（LangGraph）验收

| ID | 验收标准 | 判定方法 | result |
|:--|:--|:--|:--|
| AC-S1 | 相同 `thread_id` 可以恢复任务状态 | 阶段 4 测试 1 | pass（阶段 2：test_resume_same_thread） |
| AC-S2 | 不同 `thread_id` 互相隔离 | 阶段 4 测试 2 | pass（阶段 2：test_thread_isolation） |
| AC-S3 | store 可以跨 thread 读取长期决策 | 阶段 4 测试 3 | pass（阶段 2：test_store_cross_thread） |
| AC-S4 | `TASK_CHARTER.md` 不会被普通任务自动修改（运行前后 sha256 一致） | 阶段 4 测试 4 | pass（阶段 2：test_charter_not_modified） |
| AC-S5 | 目标冲突时进入人工确认（`interrupt()`，不自动继续） | 阶段 4 测试 5 | pass（阶段 3：三值判定 + conflicting 普通 approve 不放行，需显式 override；test_alignment_* / test_conflicting_*） |
| AC-S6 | 进程重启后可从持久化后端恢复 | 阶段 4 测试 6（独立进程二次运行） | 部分（阶段 2：demo [5] 重开 SQLite 读回同一 thread；独立进程测试待阶段 4） |
| AC-S7 | 状态 schema 明确：结构化字段承载任务对象，**不是把所有信息塞进 messages** | 代码审查（阶段 2） | pass（schemas.py：TypedDict + Pydantic 记录，任务对象不入 messages） |
| AC-S8 | 多轮运行不无限追加消息上下文（裁剪 / 摘要 / 结构化） | messages 窗口裁剪测试（阶段 2） | pass（test_messages_window_bounded，上限 20） |
| AC-S9 | 稳定 thread_id：`research:midi2score:<task_id>`，非每次随机生成 | 代码审查（阶段 2） | pass（graph.stable_thread_id → research:{project}:{task}） |
| AC-S10 | `task_alignment` 三值可用且有明确口径 | 代码审查 + test_alignment_* | pass（阶段 3） |

## C. 治理验收（阶段 1）

| ID | 验收标准 | 判定方法 | result |
|:--|:--|:--|:--|
| AC-G1 | `AGENTS.md` 覆盖用户要求的 7 条硬规则 | 逐条对照（见 `STATE.md` 阶段 1 测试记录） | pass（2026-10-07） |
| AC-G2 | 科研状态文件齐全：`TASK_CHARTER.md` / `RESEARCH_QUESTIONS.md` / `STATE.md` / `DECISIONS.md` / `ASSUMPTIONS.md` / `EVIDENCE.md` / `TODO.md` / `ACCEPTANCE.md` | 文件存在性检查 | pass（2026-10-07） |
| AC-G3 | 事实 / 决策 / 假设 / 建议 / 待办严格分区；未运行实验标注 `not_run` | 文档审查 | pass（2026-10-07） |
| AC-G4 | 提交前展示 `git diff` | 阶段 1 提交记录 | not_run |
| AC-G5 | 不存在 `conversation_summary.md`；记忆不实现为无限增长的摘要文件 | 文件系统检索 | pass（2026-10-07） |
## D. 环境前置验收（计划书 §10.3）

| ID | 验收标准 | 判定方法 | result |
|:--|:--|:--|:--|
| AC-E1 | 语料 pin 一致：本地 HEAD = 4097b457…，tag = v2.1.1 | git rev-parse HEAD / describe --tags | pass（2026-10-07） |
| AC-E2 | 语料文件集一致：242 MusicXML + 1,063 alignment = 1,305 条；总字节 465,861,631 | 文件计数 + Measure-Object -Sum | pass（2026-10-07） |
| AC-E3 | manifest SHA256 051713f7… 复核 | 需原作者提供 manifest 生成口径 | not_run（格式未规定） |
| AC-E4 | MuseScore Studio 4.7.5 本机可用（HC-05） | MuseScore4.exe --version → MuseScore4 4.7.5, exit 0 | pass（2026-10-07） |
| AC-E5 | 原始语料未进入 git（HC-06 / 计划书 §4.3 许可） | git check-ignore -v data/asap-dataset + git status | pass（2026-10-07） |
