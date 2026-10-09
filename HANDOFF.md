# 本地会话接手入口（2026-10-09）

> 本文件只做新会话的短入口。权威顺序仍以 `TASK_CHARTER.md` → `DECISIONS.md` → `STATE.md` → `FIELD_DEFINITIONS.md` 为准。

## 读什么、忽略什么

1. 先读：`TASK_CHARTER.md`、`PedNotate_Plan_v3.0.md`、`STATE.md`、`DECISIONS.md`、`FIELD_DEFINITIONS.md`。
2. 只把仓库内文档、代码、产物当事实；网页端粘贴历史、旧会话摘要、旧 SHA 只作背景，不作权威。
3. `EVIDENCE.md` 是追加式证据账本；旧 `EV-nn` 条目不等于当前状态。
4. 不要编辑 `TASK_CHARTER.md`。遇到章程/计划书冲突先停报。

## 当前架构与持久化

- 保留 LangGraph：`src/research_agent/`，checkpointer/短期状态、store/跨线程长期记忆、稳定 `thread_id`、`interrupt`/`Command(resume=...)`、verifier/人工确认。
- 当前本地持久化：`SqliteSaver` + `SqliteStore`；单进程本地档位正确。
- 生产/多进程部署前应换 `PostgresSaver`/PostgresStore；SQLite 不是生产级并发方案。
- 本地 `data/checkpoints.db`、`data/store.db` 已在接手清理时删除，避免恢复旧会话状态；需要时由代码重建。

## 当前科研状态

- **路线已由用户复位到 V3 原计划（D-0081）**：目标是在成熟 MIDI→MusicXML 流水线上增加 S2 踏板层，不是重做完整 S1。
- **主指标恢复为回放保真度**；谱面一致度为强制副指标。
- **训练顺序冻结为 ASAP 初始训练 → PDMX 合成语料增强训练**；不再用 PDMX 预训练 → ASAP 微调作为当前主线。
- 保留 `D-0059`：回放保真度是主指标，但本轮不做回放自监督 loss。
- 采用 `D-0024/D-0025`：导出成功=产物存在+可解析+CC64可枚举；恒等式仅诊断；无 `[0.80,1.05]` 带宽门。
- `results/E1/domain_unified/model1/*` 与 Round B/C/D 的 score-consistency 结果保留为历史诊断；旧 `round_c_main` 的模型数字不是当前主线结论。
- LangGraph 控制平面 v1 已实现：Goal Contract、Context Packet、preflight policy、命令 allowlist、ExecutionRecord/candidate Evidence、postflight verifier。
- 目标偏移和越权命令为 hard deny；`thread_id` 不可由调用方覆盖；长上下文测试 29/29 PASS。
- 可选 LLM 适配器已接入：DeepSeek / OpenAI-compatible，默认关闭；配置见 `config/llm.env.example`。
- LLM 只作 planner/说明器，不能执行命令、修改权限或产生 verified Evidence。
- 下一步：设置环境变量并做 live smoke；确认后进入 M2。

## 子 agent 纪律

- 鼓励并行：只读盘点、代码审阅、独立复算、证据整理可交给子 agent。
- 同一文件同一时刻只允许主代理写入；子 agent 默认只读。
- 子 agent 产出必须可核验，主代理验证后再写 `EVIDENCE.md` / 提交。
