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

- 最新模型产物：`results/E1/domain_unified/model1/best_model.pt`、`config.json`、`round_c_bilstm_crf.json`、`round_d_sweep.csv`。
- `model1` 当前配置：`hidden=32, layers=1, lr=1e-4, batch=32, chunk=256, seed=0, class_weight=none, AdamW, clip=5.0`。
- 之前轮 B/C 产物保留作历史证据；不要把旧 `round_c_main` 的模型数字当当前模型状态。
- 下一步由用户指定：D1 sweep，或结构/特征/标签三方向之一，不叠加。

## 子 agent 纪律

- 鼓励并行：只读盘点、代码审阅、独立复算、证据整理可交给子 agent。
- 同一文件同一时刻只允许主代理写入；子 agent 默认只读。
- 子 agent 产出必须可核验，主代理验证后再写 `EVIDENCE.md` / 提交。
