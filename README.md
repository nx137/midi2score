# midi2score — 科研任务管理与执行系统

基于 **LangGraph** 的科研任务管理 / 执行系统，用结构化状态 + checkpointer + store 管理以
`PedNotate_Plan_v3.0.md` 为总纲的科研任务。

## 先读这些

1. `TASK_CHARTER.md` — 最高优先级目标与硬约束
2. `AGENTS.md` — 仓库规则与工作流
3. `STATE.md` — 当前阶段与下一步
4. `DECISIONS.md` / `ASSUMPTIONS.md` / `EVIDENCE.md` / `TODO.md` / `ACCEPTANCE.md`

## 状态

当前：**阶段 1（项目规则与科研任务文件）**。LangGraph 骨架（阶段 2）、目标偏离检测（阶段 3）、
测试（阶段 4）尚未开始；运行说明将在阶段 2 补齐。

## 治理原则

- `TASK_CHARTER.md` 不可被程序自动修改。
- 事实 / 决策 / 假设 / 建议 / 待办严格区分。
- 未运行的实验一律标注 `not_run` / `not_verified`，不冒充已验证结论。