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
| EV-01 | 语料身份：1,305 条身份记录（242 MusicXML + 1,063 alignment），总字节 `465,861,631`，manifest SHA256 `051713f7e60240be4d98389a7abc4655a69c8118e9d4231a262e7797f95914fa` | 文件集与字节数：verified_in_this_repo（EV-S4）；manifest 哈希：未复现（EV-S6） |
| EV-02 | CC64 全量普查：1,053/1,066 演奏含 CC64；总消息 4,511,940；**非端点值 92.3339%**（N = 370 组合）；13 条无 CC64 | claimed_by_charter；not_verified_in_this_repo |
| EV-03 | pedal 元素：7,669 个全部为 `start`/`stop`；非二值候选 **0**；`type` = start 3,910 / stop 3,759（未闭合 151）；`sign` 从未使用；`line` = yes 4,751 / 缺省 2,450 / no 468 | claimed_by_charter；not_verified_in_this_repo |
| EV-04 | MusicXML 版本分布：3.1 = 227 / 1.1 = 9 / 3.0 = 4 / 2.0 = 1 / 缺失 = 1；含 pedal 的 68 首中 3.1 = 61，7 首非 3.1 共 504 元素（**故不得笼统写"版本 3.1"**，`HC-10`） | claimed_by_charter；not_verified_in_this_repo |
| EV-05 | 含印刷 pedal 的乐谱 **68 / 242（28.1%）**；结构平衡 30 首（44.1%）/ 不平衡 38 首（55.9%） | claimed_by_charter；not_verified_in_this_repo |
| EV-06 | 主轴 Main = **43 首 / 291 演奏 / 3,840 元素**；剔除 25 首 / 125 演奏 / 3,829 元素；保留组密度 89.3 vs 剔除组 153.2 元素/首 | claimed_by_charter；not_verified_in_this_repo |

## 2. 渲染与导出链路（来源：计划书 §10.2 / 附录 A）

| ID | 事实 | 状态 |
|:--|:--|:--|
| EV-07 | MuseScore Studio 4.7.5：**71/71** 导出成功（68 含 pedal + 3 负对照）；511,250 条消息；7,168 条 CC64；非端点值 0%；负对照 3/3 含 0 条 CC64 | 渲染器版本可用性：verified_in_this_repo（EV-S5）；71/71 导出结果：claimed_by_charter |
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
| EV-S2 | 章程冻结哈希：`TASK_CHARTER.md` **v1.1** SHA256 = `CC24794F24AFC1A6DBE21782FF844BEE1871097A9C2C730EF84360852397C214`（v1.0 曾为 `4762A7ED…`；v1.1 经用户明确确认新增 GV-07/08/09，见 D-0021） | 同上；运行期由 `charter_sha256` 复核 | verified_in_this_repo |
| EV-S3 | 阶段 1 文档级校验：9/9 文件存在；`TASK_CHARTER.md` 硬约束可机读（HC 16 条 + GV 6 条）；`AGENTS.md` 覆盖全部必需规则；无 `conversation_summary.md`；全部文档 UTF-8 无 BOM | PowerShell 校验脚本（2026-10-07），结果 **PASS** | verified_in_this_repo |
| EV-S4 | 语料 CPJKU/asap-dataset 已克隆到 data/asap-dataset（本地、已 gitignore）：HEAD 4097b45757bed854818cf87e77b92323ebf90615、tag v2.1.1（远端 tag 经 GitHub API 核实指向同一 commit）；*.musicxml = 242、note_alignment.tsv = 1,063、合计 1,305；两者总字节 = 465,861,631（与计划书完全一致）；仓库文件总数 = 10,314；repeat 变体独立目录 = 23；工作树 clean | git clone --depth 1 --branch v2.1.1 + git rev-parse HEAD + 文件计数 + Measure-Object -Sum | verified_in_this_repo |
| EV-S5 | 渲染器本机可用：D:\MuseScore 4\bin\MuseScore4.exe --version 输出 MuseScore4 4.7.5，exit code 0（与 HC-05 钉死版本一致） | Start-Process --version（2026-10-07） | verified_in_this_repo |
| EV-S6 | manifest SHA256 051713f7… **已复现**：口径 = 242 musicxml + 1063 note_alignment 各记 (entry_type,relative_path,bytes,sha256) 写成 CSV（UTF-8 无 BOM / CRLF / 按 (entry_type, path.lower()) 排序），manifest 哈希 = 该 CSV 文件自身的 sha256 | python tools/corpus_manifest.py --dataset data/asap-dataset --out evidence/corpus_manifest.csv，输出哈希与计划书一致（2026-10-07） | verified_in_this_repo |
| EV-S7 | 阶段 2 测试：`pytest -q` → **6 passed**（恢复、隔离、跨线程 store、章程不可变、消息窗口 ≤20、章程漂移停在人工确认） | `.\.venv\Scripts\python.exe -m pytest -q`（exit 0，2026-10-07） | verified_in_this_repo |
| EV-S8 | 阶段 2 示例：`python -m research_agent.demo` exit 0；`thread_id=research:midi2score:PHASE-2`；首次 invoke 停在 `human_review`，`Command(resume='approve')` 后 `phase=reviewed`、写入 `D-WP-1`；重开 SQLite 后读回同一 thread | 见 STATE.md 阶段 2 测试记录 | verified_in_this_repo |
| EV-S9 | checkpoint 自定义类型反序列化：`JsonPlusSerializer(allowed_msgpack_modules=[...])` 显式登记 9 个 schema 类，消除 "unregistered type" 警告（未用 True 全放行） | `python -m research_agent.demo` 无警告输出 | verified_in_this_repo |

| EV-S10 | 口径溯源：生成器为已废弃仓库的 `data/corpus_manifest_quality.py`（manifest 子命令），其产物 `corpus_manifest.csv` 的 sha256 即 `051713f7…`（已用 Get-FileHash 直接复核原文件）；本仓库据其格式写出等价工具 `tools/corpus_manifest.py` 并复现同一哈希 | Get-FileHash 原 CSV + 重跑本仓库工具 | verified_in_this_repo |

- 冻结产物：`evidence/corpus_manifest.csv`（1,305 行 + 表头）与 `evidence/corpus_manifest_summary.json`（含 dataset commit 与 manifest_sha256）。
- 注意：summary 里的 `script_sha256` 记录的是**当时**的脚本字节（`5dd9f12b…`），现盘脚本已变化（`42A45F39…`）；因此该口径的可复现性依赖**格式 + 命令**，不依赖脚本字节不变。
| EV-S11 | 阶段 3 测试：`pytest -q` → **12 passed**（新增三值判定：aligned / partially_aligned / conflicting、conflicting 普通 approve 不放行、override 放行并记 source=human_override、修改章程意图被拒绝且文件哈希不变） | `.\.venv\Scripts\python.exe -m pytest -q`（exit 0，2026-10-07） | verified_in_this_repo |
| EV-S12 | 阶段 3 示例：demo [6] 章程哈希漂移 → `alignment=conflicting`、`violates=['GV-01: ...']`、普通 approve 后 `phase=blocked_by_human`（未放行）；[7] 显式 override 后 `phase=reviewed`、`decision=D-WP-1 source=human_override` | `python -m research_agent.demo`（exit 0） | verified_in_this_repo |
| EV-S13 | 阶段 4 验收测试：`pytest -q` → **18 passed**；其中 `test_ac6_state_survives_process_restart` 用 `subprocess` 起两个真实进程（断言 PID 不同），进程 1 停在 `human_review`，进程 2 重新打开同一 SQLite 后 `Command(resume="approve")` → `phase=reviewed`；`test_ac4` 校验章程 sha256 与 mtime 均不变 | `.\.venv\Scripts\python.exe -m pytest -q`（exit 0，2026-10-07） | verified_in_this_repo |
| EV-S14 | 科研环境就绪：`.venv-research`（Python 3.14.6）+ `requirements-research.txt` 全部 pin 命中（partitura 1.9.0 / mido 1.3.3 / music21 10.5.0 / parangonar 3.3.3 / lxml 6.1.3 / numpy 2.5.3 / pandas 3.0.6） | `pip freeze` → `evidence/R1/research_env.txt` | verified_in_this_repo |
| EV-S15 | **R1-3b 导出链路独立复现**：20 首含 pedal 乐谱 + 2 首负对照；不加 `-f` → 16/20 成功（4 例 exit 1320 无产物）；**加 `-f` → 20/20 成功**；负对照 2/2 为 0 条 CC64；**真否决（start>0 却 0 条 CC64）= 0/20**；恒等式 `CC64 == 2×min(start,stop)` 命中 16/20（计划书自身为 40/45=88.9%）；字面 `CC64/元素数≥0.8` 仅 11/20（样本 14/20 结构不平衡）。交叉验证：`Chopin/Ballades/1` = **432**、`Chopin/Ballades/3` = **478**，与计划书附录 A 记录逐值一致 | `python tools/musescore_export_probe.py --positive 20 --negative 2 [--force]`；证据 `evidence/R1/R1-3b*/`；说明 `evidence/R1/R1-3b_summary.md` | verified_in_this_repo |
| EV-S16 | 新形态退出码异常：`Bach/Fugue/bwv_846` 导出 exit `0xC0000005`(ACCESS_VIOLATION) 但 **MIDI 正常生成且可解析**（该曲无 pedal，0 条 CC64 属正确）；加/不加 `-f` 均复现。计划书 §10.2 只记录"exit 1320 且无产物"，本例为**非零退出 + 有效产物** | 同上，`export_probe.json` 的 `exit_code` / `output_exists` 字段 | verified_in_this_repo |
| EV-S17 | **全量 68 首导出（按 D-0025 判据）**：加 `-f` → **68/68 成功**；负对照 2/2 为 0 条 CC64；恒等式命中 55/68；Tier 分布 = OK 42 / T2 10 / T2b 3 / T3 11 / T1 2（字面口径）；修正分母后的分位点 P5=0.9148、P50=1.0、P95=1.0（n=55，仅含 min>0）；**裁定 5 逐值一致子判据命中**：`Chopin/Ballades/1 = 432`、`Ballades/3 = 478` | `python tools/musescore_export_probe.py --positive 68 --negative 2 --force --out-dir evidence/R1/full68`；`python tools/pedal_export_audit.py`；产物 `evidence/R1/G1-tiers/{tiers.json,tiers.csv}` | verified_in_this_repo |
| EV-S18 | **T1 命题取证**：字面 T1（`start>0` 且 `CC64==0`）= 2 首，且两者均为 `start=1, stop=0` → **同时满足 T3 定义**（`min==0` 且 `CC64==0`），T1∩T3 重叠 = 2；两者重跑两次结果一致（exit 0、产物存在、CC64=0、MIDI 内除 6/7/10/91/93/100/101/121 外无其他 CC）；**加 `min>0` 条件后 T1 = 0/68**；13 首零 CC64 全部 `min==0` | `python tools/t1_diagnostic.py` → `evidence/R1/T1-probe/t1_diagnostic.txt`；重叠统计见 `evidence/R1/G1-tiers/tiers.json` 的 `t1_t3_overlap_*` / `strict_t1_*` | verified_in_this_repo |
