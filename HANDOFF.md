# 本地会话接手入口（2026-10-09）

> 本文件只做新会话短入口，不保存 LangGraph 机器状态。

## 接手顺序

1. `TASK_CHARTER.md`
2. `PedNotate_Plan_v3.0.md`
3. `DECISIONS.md`
4. `STATE.md`
5. `FIELD_DEFINITIONS.md`

只把当前仓库文档、代码和产物当事实。网页端粘贴历史、旧会话摘要和旧 SHA 只作背景，不作权威。

## 当前架构

- LangGraph 控制层：`src/research_agent/`。
- 短期状态：`SqliteSaver`；长期决策：`SqliteStore`。
- 稳定 `thread_id`：`research:{project_id}:{task_id}`，禁止调用方覆盖。
- 人工闸门：`interrupt()` / `Command(resume=...)`；verifier/人工确认保留。
- **不计划迁移 Postgres**；接受 SQLite 本地单进程边界。
- Goal Contract、Context Packet、allowlist、ExecutionRecord 和 postflight verifier 已接入。
- 可选 DeepSeek/OpenAI-compatible LLM 默认关闭；配置见 `config/llm.local.env`，该文件被 Git 忽略。
- 当前仓库为私人仓库：模型权重允许存在；API key/token、凭据、原始语料和虚拟环境仍禁止入库。

## 当前科研状态

- 目标：在成熟 MIDI→MusicXML 流水线上增加 S2 踏板层。
- 主指标：回放保真度；强制副指标：谱面一致度。
- 训练顺序：ASAP 初始训练 → PDMX 合成语料增强训练。
- 当前测试：34/34 PASS；DeepSeek live smoke 与 LangGraph 全链路已通过。
- Round B/C/D 的 score-consistency 与旧 `model1` 只作历史诊断，不作当前主线 claim。
- 下一步：进入 V3 原计划的 M2 标签层。

## 写入纪律

- 事实、决策、假设、建议、待办分开存放。
- 同一文件同一时刻只允许主代理写入。
- 子 agent 默认只读；产出经主代理核验后写入账本。
- `TASK_CHARTER.md` 非人工明确确认不得修改。
