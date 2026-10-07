# EVIDENCE.md — 事实 / 文献 / 实验依据

> **验证状态（强制标注）**：`verified_in_this_repo` / `claimed_by_charter`（章程声称，本仓库未复核） / `not_run` / `not_verified`。
> 未在本仓库实际运行的实验**不得**写成 `verified`。每条证据须可复现：命令 / 退出码 / 环境版本 / 产物路径 / 哈希。
> 本文件只放**事实与依据**；决策放 `DECISIONS.md`，假设放 `ASSUMPTIONS.md`，待办放 `TODO.md`。

## 0. 本仓库验证状态说明

当前仓库**尚未获取语料、未安装 MuseScore、未运行任何实验**。因此下列来自 `PedNotate_Plan_v3.0.md` 的数字一律标注
`claimed_by_charter；not_verified_in_this_repo`。它们可被引用，但引用时**必须保留该状态标注**。

## 1. 语料普查（来源：计划书 §4.1 / §10.2 / 附录 A）

| ID | 事实 | 状态 |
|:--|:--|:--|
| EV-01 | 语料身份：1,305 条身份记录（242 MusicXML + 1,063 alignment），总字节 `465,861,631`，manifest SHA256 `051713f7e60240be4d98389a7abc4655a69c8118e9d4231a262e7797f95914fa` | claimed_by_charter；not_verified_in_this_repo |
| EV-02 | CC64 全量普查：1,053/1,066 演奏含 CC64；总消息 4,511,940；**非端点值 92.3339%**（N = 370 组合）；13 条无 CC64 | claimed_by_charter；not_verified_in_this_repo |
| EV-03 | pedal 元素：7,669 个全部为 `start`/`stop`；非二值候选 **0**；`type` = start 3,910 / stop 3,759（未闭合 151）；`sign` 从未使用；`line` = yes 4,751 / 缺省 2,450 / no 468 | claimed_by_charter；not_verified_in_this_repo |
| EV-04 | MusicXML 版本分布：3.1 = 227 / 1.1 = 9 / 3.0 = 4 / 2.0 = 1 / 缺失 = 1；含 pedal 的 68 首中 3.1 = 61，7 首非 3.1 共 504 元素（**故不得笼统写"版本 3.1"**，`HC-10`） | claimed_by_charter；not_verified_in_this_repo |
| EV-05 | 含印刷 pedal 的乐谱 **68 / 242（28.1%）**；结构平衡 30 首（44.1%）/ 不平衡 38 首（55.9%） | claimed_by_charter；not_verified_in_this_repo |
| EV-06 | 主轴 Main = **43 首 / 291 演奏 / 3,840 元素**；剔除 25 首 / 125 演奏 / 3,829 元素；保留组密度 89.3 vs 剔除组 153.2 元素/首 | claimed_by_charter；not_verified_in_this_repo |

## 2. 渲染与导出链路（来源：计划书 §10.2 / 附录 A）

| ID | 事实 | 状态 |
|:--|:--|:--|
| EV-07 | MuseScore Studio 4.7.5：**71/71** 导出成功（68 含 pedal + 3 负对照）；511,250 条消息；7,168 条 CC64；非端点值 0%；负对照 3/3 含 0 条 CC64 | claimed_by_charter；not_verified_in_this_repo |
| EV-08 | `-f` 行为：clean 文件上惰性；带/不带 `-f` 产物 SHA256 相同 = `518942ebc97724e10fdeae04485595a5afe1252a946324b0fd5aded428a50360` | claimed_by_charter；not_verified_in_this_repo |
| EV-09 | `-f` 异常：23 个文件无 `-f` 时退出码 `1320`，stdout/stderr 为空、不生成 MIDI；独立进程复现 6/6。**机制未定，按证据记录、不猜测原因** | claimed_by_charter；not_verified_in_this_repo |
| EV-10 | 渲染器恒等式：`CC64 消息数 == 2 × min(pedal_start, pedal_stop)`，45 个 clean 文件中命中 40（88.9%）；5 个例外已列名 | claimed_by_charter；not_verified_in_this_repo |
| EV-11 | 逐文件映射：`Chopin/Ballades/3` 480 → 478（0.996）/ 476 跳变（0.992）；`Chopin/Ballades/1` 465 → 432（0.929）/ 389（0.837）→ 正确期望 ≈ **1.0 倍** | claimed_by_charter；not_verified_in_this_repo |

## 3. 对齐、偏差与风险证据（来源：计划书 §0.1 / §4.4 / §10.2 / §12）

| ID | 事实 | 状态 |
|:--|:--|:--|
| EV-12 | 对齐桥：时间轴契约最大 onset 残差 `1.0800249583553523e-12 s`（754 音符，13 个 MIDI id 未命中）≤ 1e-6 达标 | claimed_by_charter；not_verified_in_this_repo |
| EV-13 | 过滤器选择偏差：Cramér's V `0.6415`（p `0.00181`）；pedal 元素数 SMD `0.3629`；绑定演奏数 SMD `0.3120`；逐作曲家保留率 Chopin 95.2% / Beethoven 66.7% / Liszt 26.7% / Ravel 25.0% / Prokofiev、Rachmaninoff、Schubert 0% | claimed_by_charter；not_verified_in_this_repo |
| EV-14 | **无标注被误当负样本**（最高风险）：Beethoven Sonata 4-1 / 8-1 / 17-1 谱面 pedal 记号 = 0，而演奏 CC64 二值跳变 **674–700 次** → 必须有 unlabeled mask（`HC-08`） | claimed_by_charter；not_verified_in_this_repo |
| EV-15 | 密度变异跨三个数量级（1.49 → 1360）；压缩比中位数 57.3（N = 370）/ 62.6（对齐过滤后） | claimed_by_charter；not_verified_in_this_repo |

## 4. 外部文献（来源：计划书 §1.2 / §6.1）

| ID | 事实 | 状态 |
|:--|:--|:--|
| EV-16 | 音频 → 带踏板 MIDI 检测已饱和：MAESTRO 上二元踏板检测 activation-level F1 = 0.954（arXiv 2507.04230）。**只能作上下文锚点，不得与本任务并列比较**（`HC-14`） | 文献引用；未独立复核 |
| EV-17 | "MIDI → 乐谱踏板记谱"为空白：`MIDI2ScoreTransformer` 全部 16 个源文件 pedal/sustain/control_change 命中 0 次。**不得写"ScoreTranscriber 做得不好"**，只能写"未见公开说明，无法核对"（`HC-14`） | 文献/源码检索；未独立复核 |

## 5. 本仓库自产证据（verified_in_this_repo）

| ID | 事实 | 复现方式 | 状态 |
|:--|:--|:--|:--|
| EV-S1 | 权威规格源哈希：`PedNotate_Plan_v3.0.md` SHA256 = `ED95FA15D104967AFD54A0156DC07B027E91AAFE9605C6EB470DAC7F142628A9` | `Get-FileHash -Algorithm SHA256`（2026-10-07） | verified_in_this_repo |
| EV-S2 | 章程冻结哈希：`TASK_CHARTER.md` SHA256 = `4762A7EDCD55CA7FC7F862CA2FC0C2EDCDAFC9F743BA01EAC0322160A756C9A8` | 同上；运行期由 `charter_sha256` 复核 | verified_in_this_repo |
| EV-S3 | 阶段 1 文档级校验：9/9 文件存在；`TASK_CHARTER.md` 硬约束可机读（HC 16 条 + GV 6 条）；`AGENTS.md` 覆盖全部必需规则；无 `conversation_summary.md`；全部文档 UTF-8 无 BOM | PowerShell 校验脚本（2026-10-07），结果 **PASS** | verified_in_this_repo |