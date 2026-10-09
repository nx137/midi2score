# ASSUMPTIONS.md — 暂定假设

> **假设 ≠ 决策。** 假设可被证据推翻；一旦升级为已确认决策，必须写入 `DECISIONS.md` 并在本文件标记 `promoted_to`。
> 状态取值：`open` / `supported` / `refuted` / `promoted`。
> 本仓库尚未运行任何实验，故全部为 `open`（工程假设 AS-06 除外，见备注）。

| ID | 假设（暂定） | 置信度 | 失效条件 / 验证方式 | 状态 |
|:--|:--|:--|:--|:--|
| AS-01 | ASAP 的 MusicXML 是 *score-edition proxy*（数字重排版、来源不可核验），但仍可作为**副指标**的弱标签源使用 | medium | 若其 pedal 元素被证明可追溯至可核验出版源，或副指标与主指标结论系统性冲突 | open |
| AS-02 | 谱面锚点（量化步长默认十六分音符）是合适的标签单位 | medium-high | E10 步长敏感性显示结论随步长翻转 | open |
| AS-03 | 半踏板（CC64 中间值）可用"显式二值化阈值 + 连续深度特征"近似处理，无需完整连续建模 | medium | E3 阈值敏感性显示结论不稳（阈值改变导致主指标排序翻转） | open |
| AS-04 | 反向回放通道（记号 → MuseScore 导出 MIDI → CC64）可作为无偏主指标 | medium-high | G1' 三条判据未通过（含 `-f` 退出码 1320 命中） | open |
| AS-05 | 导出 MIDI 的 CC64 消息数 ≈ pedal 元素数（≈1.0 倍），可作导出链路验收点 | high | 抽样显著偏离 1.0 | open |
| AS-06 | LangGraph `SqliteSaver` + `SqliteStore` 足以支撑本地单进程科研任务管理 | high | 用户明确不迁移 Postgres；若未来重新变更部署范围再评估 | supported（D-0087） |
| AS-07 | 43 首主轴规模足以支撑方法有效性结论（G2 可判定） | medium | G2 若因样本量不足而统计不可判定 | open |

## 备注

- AS-01 / AS-03 / AS-04 直接对应论文 Limitations 章节的披露义务。
- AS-06 是本仓库工程侧的 `ponytail:` 取舍：先用最简持久化，触发条件明确后再升级，不预建抽象层。