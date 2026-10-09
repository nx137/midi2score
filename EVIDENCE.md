# EVIDENCE.md — 事实 / 文献 / 实验依据

> **验证状态（强制标注）**：`verified_in_this_repo` / `claimed_by_charter`（章程声称，本仓库未复核） / `not_run` / `not_verified`。
> 未在本仓库实际运行的实验**不得**写成 `verified`。每条证据须可复现：命令 / 退出码 / 环境版本 / 产物路径 / 哈希。
> 本文件只放**事实与依据**；决策放 `DECISIONS.md`，假设放 `ASSUMPTIONS.md`，待办放 `TODO.md`。

## 0. 文档状态与当前入口（2026-10-09 更正）

- 本文件是**追加式证据账本**：前面的 `EV-nn` 多为计划书来源的历史 `claimed_by_charter` 条目，不代表当前仓库尚未运行实验。
- 当前状态与下一步只看 `STATE.md`；当前确认决策只看 `DECISIONS.md`；字段口径只看 `FIELD_DEFINITIONS.md`。
- 当前仓库已获取 ASAP、已安装 MuseScore、已运行 G0/G1'/R1/E1 等实验；具体验证状态以各 `EV-S*` 条目的实际命令与产物为准。
- 未在本仓库实际运行的内容仍不得写成 `verified`；早期未复核的 `claimed_by_charter` 数字不得当作当前运行状态。

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
| EV-S1 | 权威规格源哈希（**三版链**）：`ED95FA15D104967AFD54A0156DC07B027E91AAFE9605C6EB470DAC7F142628A9`（v3.0 原始）→ `56E5BD45BC7143D9F8D1455571165C1BC2B40BBFCB3AF07FF2053EDAE9B086A2`（D-0039 §4.4 勘误）→ **`FE45D7BDA63ECA3059C15FE73FC8F2DEAC10866E2C5437D79586A4AF93D60B86`（当前：+ 修订记录表 + §4.1 划分措辞/Table X，D-0041）** | `Get-FileHash -Algorithm SHA256`（2026-10-07） | verified_in_this_repo |
| EV-S2 | 章程冻结哈希：`TASK_CHARTER.md` **v1.2** SHA256 = `8C24D88707385B8104505B28B898569AD6BC207F320D2B79960CD320CFD769CF`（v1.0 `4762A7ED…` → v1.1 `CC24794F…`（D-0021 新增 GV-07/08/09）→ **v1.2 `8C24D887…`（D-0058：主指标改为谱面一致度 + HC-17）**） | 同上；运行期由 `charter_sha256` 复核 | verified_in_this_repo |
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
| EV-S19 | **全量导出复现（68 + 3 负对照，统一 `-f`）**：68/68 成功；3/3 负对照为 0 条 CC64（`bwv_846`/`bwv_848`/`bwv_854`，与旧记录选样规则一致）；逐文件记录 exit code + 产物 bytes + **产物 SHA256** + 源 XML SHA256 + `S/T/C/I` + tier。`bwv_846` 仍报 `0xC0000005` 但产物 4822 B 与旧记录 bytes 一致、可解析 → 成功判据取"产物存在且可解析" | `python tools/musescore_export_probe.py --positive 68 --negative 3 --force --out-dir evidence/R1/full68v2`；`evidence/R1/G1-export/tiers.csv` | verified_in_this_repo |
| EV-S20 | **五格 Tier 表（D-0029 谓词）**：OK **42** / T1 **0** / T2（含 T2b=3）**13** / T3 **13** / T4 **0**，与主控预期表逐格一致；T2/T2b 七字段与 `explanatory_residual` 见 `tiers.csv`；**13 首残差全部 ≠ 0**（多为大幅负值，结构计数高估缺口）→ 进「机理未解释」名单，不新增 Tier | `python tools/pedal_export_audit.py --probe evidence/R1/full68v2/export_probe.json`；`evidence/R1/G1-export/tiers.{json,csv}` | verified_in_this_repo |
| EV-S21 | **裁定 5 逐值一致（全覆盖）**：与旧记录重叠 **71/71** 全部命中 CC64 条数（含 `Chopin/Ballades/1 = 432`、`Ballades/3 = 478`），产物 bytes 亦全部一致；不是只查 2 首 | `evidence/R1/G1-export/baseline_overlap.csv`（基准 `evidence/R1/reference/prior_cc64_details.csv`） | verified_in_this_repo |
| EV-S22 | **分位点（定义域 `min(S,T)>0`，n=55）**：`numpy linear`(R-7) → P5 **0.91485**、P50 1.0、P95 1.0；`lower`/`nearest_rank` → P5 **0.8837**。直方图：`g==0` 42 / `0<g≤1%` 3 / `1–5%` 5 / `5–10%` 2 / `>10%` 3。上升序前 8 值 = 0.70, 0.75, 0.8837, 0.9282, 0.9492, 0.9686, 0.9714, 0.9805。**主控预期"应显著低于 0.9148"未成立，按指令停机对齐（D-0035）**：13 首违反者确在样本内，差异来自估计量而非样本 | `evidence/R1/G1-export/tiers.json` 的 `percentiles_over_min_gt_0` / `sorted_ratios` / `gap_histogram` | verified_in_this_repo |
| EV-S23 | **缺陷 #6 自检 + 新式缺口分解**：旧式残差套到 **42 首 OK** 上 → **20 首 ≠ 0**（例 `Beethoven/14-3` S=19,T=19,C=38 → 旧式 −4），诊断证实。新式 `shortfall_pairs = m − C/2`、`unexplained = shortfall_pairs − inverted`：`>0` **4 首**（`Chopin/Ballades/1`+5、`Ballades/3`+1、`Scherzos/31`+1、`Scherzos/39`+6）、`==0` **31 首**、`<0` **33 首**（min −184）。**奇数 C = 0/68** | `python tools/export_pairing_audit.py --dataset data/asap-dataset --probe evidence/R1/full68v2/export_probe.json --out-dir evidence/R1/G1-export`；产物 `pairing_audit.{json,csv}` | verified_in_this_repo |
| EV-S24 | **三条候选配对规则（上限 3，D-0035 §3.4）**：全局文档顺序栈 / 按 staff 独立栈 / 贪心最近配对，**三者结果完全相同**（`unexplained==0` 各 36/68，`Cpred` 命中 51/68），**无一条能清零** → 按裁定记为「导出侧配对规则未能唯一确定」。正值 4 首集中在 Chopin 密集踏板作品，非全库系统性 | 同上 | verified_in_this_repo |
| EV-S25 | **Main 口径冲突与复现（D-0037）**：(a) 正文 `robust ∈ {0,1}` → 66 首 / 388 演奏 / 7666 元素；(b) 旧脚本谓词 `== "1.0"` + `aligned is True` + alignment 文件存在、**乐谱级**计数 → **43 首 / 291 演奏 / 3840 元素，与计划书 §4.4 逐值一致**。分解：合格演奏 284 → 命中乐谱 43 → 这 43 首的**全部** metadata 行 = 291 | 对照脚本 `corpus_manifest_quality.py`（只读）与本仓库复算；证据见 `evidence/R1/G1-split/` | verified_in_this_repo |
| EV-S26 | **主表划分冻结（交付 6，D-0033）**：Main 43 首 / 291 演奏 / 3840 元素；按 `(composer, normalized_title)` 分组；`other` 池 = {Brahms, Debussy, Ravel, Scriabin}（5 组 / 5 首）；划分 = **train 26 组 27 首 178 演奏 2448 元素 ／ val 6 组 6 首 31 演奏 143 元素 ／ test 9 组 10 首 82 演奏 1249 元素**；无空折、test > 1 组；冻结文件 `split_v1.json` + SHA256 `52ae1314d9e3caf2af0b94891ce1143858a0982f3b7593117b2cb559680dfa57` | `python tools/split_freeze.py --dataset data/asap-dataset --out evidence/R1/G1-split/split_v1.json` | verified_in_this_repo |
| EV-S27 | **exit code 披露（D-0035 §五）**：71 份中 exit≠0 共 **2 份**（`Chopin/Sonata_3/3rd` 与 `Bach/Fugue/bwv_846`，均 `3221225477`=0xC0000005）。`bwv_846` 连跑 3 次：**产物 3/3 同 SHA256 `99fd163c…`（4822 B）**，但**退出码 1 次 0、2 次 0xC0000005** → 产物可复现、退出码不可复现；判据以产物为准（FIELD_DEFINITIONS §8），该工具事实须写入论文可复现性一节 | `evidence/R1/G1-export/exitcode_disclosure.txt` | verified_in_this_repo |
| EV-S28 | **Main 谓词冻结与划分补报（D-0039 / 交付 6）**：演奏级谓词 ⇒ 284 条；乐谱级 ⇒ 43 首；纳入集 = 43 首全部 metadata 行 ⇒ **291 演奏 / 3840 元素**（逐值命中计划书）。**291 中 7 条不满足谓词**：`Beethoven/29-4/DANILO01`(robust 空,aligned False)、`Chopin/Ballades/1/MunA19M`(0.0,False)、`Chopin/Etudes_op_10/1/LuM02M`(**1.0**,False)、`Chopin/Scherzos/20/Wong04M`(0.0,False)、`Scriabin/Sonatas/5/{ChernovA06M,FALIKS06,Ko07M}`(0.0,False)。`split_v1.json` 已逐演奏记录 `robust_note_alignment` / `score_and_performance_aligned` / alignment 路径 / qualifying / fold；作曲家×折矩阵与 other 池分布见下 | `python tools/split_freeze.py --dataset data/asap-dataset --out evidence/R1/G1-split/split_v1.json`（enriched 版 SHA256 `0896c95130128fa92d81a3e98bbd89fbf279a411a27e06420cc4c1e8bcbf0c6c`） | verified_in_this_repo |
| EV-S29 | **①a 反复展开决定性测量**：`Beethoven/31-2` 书写非休止音符 **978**（raw XML `<note>` 1066）→ 导出 MIDI 音符 **1345**；partitura `unfold_part_maximal` 给 1428 → **导出会展开反复**。旁证：ASAP README 明确 `xml_id` 带 `-REPEAT_N` 且示例要求 `unfold_part_maximal`（对齐在展开坐标系）。**后果**：导出侧 `S/T` 在书写坐标、`C` 在展开坐标 → 混合坐标系（见 D-0040 停机） | `python tools/repeat_expansion_probe.py --dataset data/asap-dataset --out-dir evidence/R1/G1-coordsys --exitcode-file Chopin/Sonata_3/3rd/xml_score.musicxml --exitcode-repeat 3`；`evidence/R1/G1-coordsys/` | verified_in_this_repo |
| EV-S30 | **退出码对称复现（D-0035 §五）**：`Chopin/Sonata_3/3rd` ×3 → 产物 **3/3 同 bytes 14305 / 同 SHA256 `d7bf722885123989…`**，退出码 **2 次 0xC0000005 + 1 次 0**。与 `bwv_846`（3/3 同 SHA256、exit 1×0 + 2×crash）**同形** → 产物确定、退出码不确定；71 份中 exit≠0 共 **2 份** | `evidence/R1/G1-coordsys/coordsys_and_exitcode.txt`、`evidence/R1/G1-export/exitcode_disclosure.txt` | verified_in_this_repo |
| EV-S31 | **回溯自洽性检验（无关坐标系）**：含 `<repeat>` 标记乐谱恒等式命中 **6/10 = 60%**，不含 repeat **36/58 = 62%** → **无系统性差异**（若展开真的污染 pedal 计数，含 repeat 组应显著更差）。但这是"未检出效应"，不构成自洽证明 → 按停机条件下报 | `evidence/R1/G1-coordsys/coordsys_consistency.txt` | verified_in_this_repo |
| EV-S32 | **4a(i) 门：partitura 能否给出展开后的原始 S/T → 否（停机）**。(1) unfold **会**复制 pedal 方向：Liszt/Hungarian_Rhapsodies/6 181→187、Schumann/Arabeske 127→137、Beethoven/31-2 2→2（其反复内无 pedal）。(2) 但 `SustainPedalDirection` 是**成对合并**对象（31-2：XML 9 个元素 → 2 个对象），拿不到 start/stop 原始计数。(3) 绕道展开后回写 MusicXML **不可行**：`Chopin/Ballades/3` 原 S=240/T=240/480 元素 → 回写后 **T=0、454 元素**；**展开版 save 直接崩溃** `AttributeError: NoneType has no attribute 'actual_notes'` | `python tools/...`（见 `evidence/R1/G1-unfold/` 与 `evidence/R1/G1-coordsys/`）；会话内实测 | verified_in_this_repo |
| EV-S33 | **4a(ii) 门：计数口径对照 → 比值 ≠ 1.0（停机）**。4 首**不含 `<repeat>`** 的乐谱：`Ballades/3` 4810→4508（0.937）、`Scherzos/39` 5348→5238（0.979）、`Ravel/Miroirs/3_Une_Barque` 4698→4657（0.991）、`Beethoven/29-2` 2030→1842（0.907）。**系统性偏低最多 −9%** → 31-2 的 1.375 倍**不能仅凭此归因于反复** | `evidence/R1/G1-coordsys/gate_4a_ii_note_counting.txt` | verified_in_this_repo |
| EV-S34 | **冻结标识改造（交付 6 收讫条件）**：冻结对象 = 指派三元组集合 `{(piecegroup, performanceid, fold)}`，规范化 CSV（按 (piecegroup, performanceid) 排序、UTF-8 无 BOM、CRLF）→ **`assignment_sha256 = 2a5ff6e89f4407d578153b395d1bbffb28c9e9c08c1b5f5562b1fbf2eb08abbf`**（291 行 / 41 组 / CRLF 292 行）；文件字节哈希不再作为身份 | `python tools/split_assignment_hash.py --split evidence/R1/G1-split/split_v1.json --out-csv evidence/R1/G1-split/split_v1_assignment.csv` | verified_in_this_repo |
| EV-S35 | **欠账 #4（as-written 半边）**：68 首中零 CC64 共 **13 首**，其中 **8 首落在 43 主轴**、5 首不在。主轴内 8 首的折分布 = train 4 / test 3 / val 1；这 8 首合计 **69 / 3840 pedal 元素（1.8%）**。13 首全部 `min(S,T) == 0`（T3 构造上正确）。逐首 (S,T)：`Beethoven/21-3`(0,7)、`24-2`(0,2)、`28-1`(0,2)、`Chopin/Etudes_op_25/12`(0,1)、`Sonata_2/1st_no_repeat`(0,1)、`Sonata_2/2nd`(0,1)、`Sonata_2/2nd_no_repeat`(0,1)、`Sonata_3/2nd`(0,42)、`Sonata_3/4th`(0,14)、`Prokofiev/Toccata`(1,0)、`Schubert/Impromptu_op.90_D.899/3`(1,0)、`Schumann/Kreisleriana/3`(0,1)、`Kreisleriana/3_no_repeat`(0,1)。**unfolded 半边待 S/T 口径裁定后补** | `evidence/R1/G1-export/debt4_aswritten.txt` | verified_in_this_repo |
| EV-S36 | **D-0045 重贴标签 + 过滤（不重测）**：68 首含 pedal 乐谱 = **58 无 `<repeat>`（有效）+ 10 含 `<repeat>`（coordinate_ambiguous）**。58 首 Tier = OK 36 / T2(含T2b) 12 / T3 10。分位点定义域 = `min(S,T)>0 ∧ 不含 repeat`（**n=48**）：`linear`(R-7) P5 **0.899275** / P50 1.0 / P95 1.0；`lower`·`nearest_rank` P5 0.8837。直方图：gap==0 **36** / 0<g≤1% 3 / 1–5% 4 / 5–10% 2 / >10% 3。裁定 5 仍 **71/71**。产物：`tiers_effective.csv`（58 行）、`tiers_coordinate_ambiguous.csv`（10 行） | `python tools/pedal_export_audit.py --dataset data/asap-dataset --probe evidence/R1/full68v2/export_probe.json --out-dir evidence/R1/G1-export` | verified_in_this_repo |
| EV-S37 | **T1/T4 坐标不变性（推导）**：展开只复制既有内容 ⇒ `Su≥Sw ∧ Tu≥Tw`；`min(Sw,Tw)==0 ⇒ min(Su,Tu)==0` ⇒ T1（需 `min>0`）与 T4（需 `min==0`）判定坐标不变 ⇒ **T1=0 / T4=0 无需重算，路线作废判定正式结清**。旁证：13 首零 CC64 全部 `S=0` → 任何坐标系下都是 T3 | 纯推导，见 `FIELD_DEFINITIONS.md` §12 | verified_in_this_repo（推导） |
| EV-S38 | **第 0 步通道自检（含 repeat + pedal）**：`Beethoven/31-2` — 书写非休止音符 **978**；nASAP 展开音符位 **1340**；MuseScore 导出 MIDI 音符 **1345** → **导出/展开 = 1.0037**（残差 5 音符 / 0.37%），导出/书写 = 1.3753 ⇒ **导出确在展开坐标，通道成立**（停机条件 ① 未触发）。书写 pedal S/T = 2/7（共 9），导出 CC64 = 4 = 2×min(2,7) ✓ | `evidence/R1/G1-coordsys/step0_channel_check.txt` | verified_in_this_repo |

## 7. E1 / B2 Round A 收尾（2026-10-09）

| ID | 事实 | 证据 | 状态 |
|:--|:--|:--|:--|
| EV-S39 | **B2 收尾一次运行完成**：36 评测域 / 271 runs；CV K∈{1,2,3}；选中 K=3；test 折 ±1 micro F1=0.3712；全量域 ±1 micro F1=0.2971；test DOWN F1=0.4850，UP F1=0.2550；test ±1 聚合 tp/fp/fn/wrong = 11006/32012/5272/352；分标签 DOWN tp/fn/wrong = 7267/1190/228，UP = 3739/4082/124。`alignment_proof.PASS=true`，`bootstrap_equal=true`，`cache_miss=36` | `tools/b2_harmony_segments.py`；`results/E1/B2_perf.csv`、`B2_summary.json`、`B2_summary.md`；`evidence/R1/E1/B2_roundA_final.log`；`evidence/R1/E1/B2_roundA_completion.md` | verified_in_this_repo |
| EV-S40 | **B2 分标签 bootstrap**：按 score 重采样、逐 run 计数求和、seed=20260101、boot=10000；test DOWN(B2−bp4) Δ=0.0293 [−0.1021,0.1187]；test UP(B2−inversion) Δ=−0.0761 [−0.1538,0.0122]；full DOWN Δ=0.0188 [−0.0285,0.0734]；full UP Δ=−0.0125 [−0.0623,0.0366]。inversion 与 B2 的 span 域不同，相关行只作参照 | `tools/b2_perlabel_bootstrap.py`；`results/E1/B2_bootstrap_perlabel.json`；`evidence/R1/E1/B2_perlabel_bootstrap_roundA.log` | verified_in_this_repo |
| EV-S41 | **轴分离与 notation reference 收口**：谱面一致度轴 notation_reference 为构造恒等 F1=1.0（三档均 1.0）；回放轴副指标独立表使用 `MAIN_METRIC_round1.md` 的 0/±0.25/±0.5/±1.0 = 0.0552/0.1222/0.1807/0.2434。0.3146 是谱面轴 inversion ±2，不属回放表。36 域 train B1 CV d_min=0 #pred=74570，对应 166 runs；test pedal elements=1051/3615=29.1% | `results/E1/floor_reference_test.md`、`results/E1/replay_fidelity_reference.md`、`evidence/R1/E1/fold_test_inventory.md` | verified_in_this_repo |

## 8. 轮 B 统一域复算与停机（2026-10-09）

| ID | 事实 | 证据 | 状态 |
|:--|:--|:--|:--|
| EV-S42 | **canonical domain 复算完成**：271 runs / 36 scores；B1 canonical CV 的 d_min argmax 仍为 **0.0 拍**。±1 micro F1：test B1=0.39356363、B2=0.36657179、bp2=0.32207683、bp4=0.34172139；full B1=0.27665189、B2=0.26415214、bp2=0.22483178、bp4=0.23989437。**停机条件 ③ 触发**：full B2 canonical−旧域 = 0.26415214−0.29705973 = **−0.03290759**（>0.03）；test B2 差 −0.00465055；B1 full 差 +0.00009467。canonical `[0,score_end)` 排除 `Chopin/Etudes_op_10/10` 4 runs 各 1 个右端点 `UP`，full n_truth 28,599（旧 28,603） | `tools/canonical_domain.py`、`tools/canonical_unified_eval.py`、`results/E1/domain_unified/E1_main_canonical.{csv,json,md}`、`evidence/R1/E1/canonical_unified_eval.log` | verified_in_this_repo；**stop ③** |
| EV-S43 | **V1 可行性冲突（未排除）**：轮 B 指示 V1 要求特征只能由谱面音符+栅格算出、且不触碰任何演绎/标注文件；但 §5.1 A 层明确“源自该 run 的 CC64”，且 `δ_onset/δ_offset` 的“最近拍 / 局部 IBI”若取 performance beats 必然来自 `asap_annotations.json`。按“未写明的取值必须停机上报”，未自行发明 score-grid IBI，训练表与 LR 未开始 | `PedNotate_Plan_v3.0.md` §5.1、`FIELD_DEFINITIONS.md` §17、本轮停止记录 | not_run；等待裁定 |

## 9. 轮 B canonical 闭区间与 LR 首轮（2026-10-09）

| ID | 事实 | 证据 | 状态 |
|:--|:--|:--|:--|
| EV-S44 | **canonical 域改闭区间 `[0,score_end]`** 后复算：full n_truth=28,603、test n_truth=16,278，right-end 排除修复；B1 canonical CV argmax d_min 仍 0.0 拍。±1 micro F1（test/full）：B1 0.39353135 / 0.27657959；B2 0.36652909 / 0.26412246；bp2 0.32179490 / 0.22465639；bp4 0.34142376 / 0.23971261 | `tools/canonical_domain.py`、`tools/canonical_unified_eval.py`、`results/E1/domain_unified/E1_main_canonical.*`、`evidence/R1/E1/canonical_unified_eval_closed.log` | verified_in_this_repo |
| EV-S45 | **轮 B LR(L2) 首轮完成**：V1 特征剥离 `<pedal>` 后逐值全等（hash 4c2ab764…）；V2 训练/评测锚点 key hash 相同 669425c3…；V3 B2 canonical test ±1 复算 tp/fp/fn/wrong/n_pred/n_truth=11012/32798/5266/358/43810/16278，逐值等于 canonical JSON。选中 class_weight=balanced，thresholds DOWN/UP=0.7/0.75；test micro F1=0.46614888，DOWN=0.54452211，UP=0.33315439；full micro F1=0.36455978，DOWN=0.40986115，UP=0.27981286。V5 对 8 个 |Δmicro|≥0.05 方法对做 10,000 次 score bootstrap；test LR−B1 0.0735 [0.0125,0.1318]，full LR−B1 0.0839 [0.0362,0.1363]；CHANGE 关闭，若开启 merge 对数=3611 | `tools/round_b_features.py`、`tools/round_b_lr.py`、`results/E1/domain_unified/LR_model.{json,csv,md}`、`evidence/R1/E1/round_b_lr_full_v2.log` | verified_in_this_repo |

## 10. 轮 C 四阶梯与序列模型（2026-10-09）

| ID | 事实 | 证据 | 状态 |
|:--|:--|:--|:--|
| EV-S46 | **轮 C 完成**：LR/GBDT/LR+确定性结构解码/BiLSTM-CRF 全部在 canonical `[0,score_end]` 与 train-CV 选择协议下出数。test ±1 micro：LR **0.392995**、GBDT **0.310068**、LR_struc **0.230132**、BiLSTM-CRF **0.080336**；B1=0.393531、B2=0.366529。BiLSTM-CRF 对 LR Δ=−0.312659，CI low=−0.413922，预声明 claim 门槛**不过**；对 B1/B2 也不显著。V1/V3/V4 PASS；V5 对 28 个方法对按 |Δ|≥0.05 做 score 重采样 bootstrap | `tools/round_c_classical.py`、`tools/round_c_bilstm_crf.py`、`tools/round_c_combine.py`、`results/E1/domain_unified/round_c_main.{json,md}`、`round_c_classical.json`、`round_c_bilstm_crf.json`、`evidence/R1/E1/round_c_*.log` | verified_in_this_repo |

## 11. 轮 D 修复与阻塞（2026-10-09）

| ID | 事实 | 证据 | 状态 |
|:--|:--|:--|:--|
| EV-S47 | **F1**：sklearn LR 的 C 对数网格 train-CV 最优 C=1.0、阈值 0.85/0.80，test micro=0.392995；同一特征上 legacy custom fit_lr 在阈值 0.70/0.75 下 test micro=0.466149，而 sklearn 同阈值=0.340531，差异归因于优化器/正则/标准化路径。**F2**：53 列全矩阵剥离 `<pedal>` 后逐值相等，hash `03821d67ffd1f55c…` = `03821d67ffd1f55c…`（271 runs / 36 scores）。**F3**：BiLSTM-CRF 的 full-sequence/hidden128/内层早停/CRF 类权重版本训练 loss=NaN，未产生可用模型；该行阻塞 | `round_d_lr_grid.log/json/csv`、`round_d_v1_full.log/json`、`round_d_bilstm128.log` | F1/F2 verified；F3 blocked |

## 12. T-MODEL-1 harness 与成功运行（2026-10-09）

| ID | 事实 | 证据 | 状态 |
|:--|:--|:--|:--|
| EV-S48 | **T-MODEL-1**：train 标签 unique={0:NONE,1:DOWN,2:UP}，无 CHANGE；harness 新增 seed/epochs200/patience10/inner_val micro-F1/显式 val/NONE+DOWN+UP+macro/checkpoint/config/clip5.0。L1（hidden32,lr1e-4,batch32,chunk256,seed0,类权重开）epoch1 NaN；L3 关闭 CRF 类权重后成功运行 11 epochs（best_epoch=1）。val micro=0.0369778133、val macro=0.3209416801；test micro=0.1515981000、test macro=0.4058411901；wall=172.763279s。产物 `model1/best_model.pt`、`model1/config.json`、`round_d_sweep.csv` | `tools/round_c_bilstm_crf.py`、`evidence/R1/E1/round_model1_L1.log`、`round_model1_L3.log`、`round_model1_final.log`、`results/E1/domain_unified/model1/*` | verified_in_this_repo |

## 13. V3 原计划复位（2026-10-09）

| ID | 事实 | 证据 | 状态 |
|:--|:--|:--|:--|
| EV-S49 | 用户明确确认 V3 原计划复位：项目定位为在成熟 MIDI→MusicXML 流水线上增加 S2 踏板层；主指标恢复为回放保真度，谱面一致度为强制副指标；新增 `HC-18`，训练顺序冻结为 ASAP 初始训练 → PDMX 合成语料增强训练。Round B/C/D 的 score-consistency 与 `model1` 保留为历史诊断。 | `D-0081`；`TASK_CHARTER.md` sha256 `77D71D7FB1E6733AF0B5A26032CBF24AB36CCE33E8FAA0BF6730B55F5492D4B2`；`PedNotate_Plan_v3.0.md` sha256 `DBA71B01DB0BA5942C89BC89DBE4E5916D7ED12F32A9693E441C447F0A62A0C4`；`DECISIONS.md` sha256 `11DA89E4D45804EF951B102CD40FF4D7EBEEF9253A0147273B946105F5C460CE`；字段定义 sha256 `0F9F467A6E2B945845DFA5F9F908D05F9C4EB02783BB6E7D4423F82E17576DC4` | verified_in_this_repo（文档级复位；命令：9 项文档断言 + `.\.venv\Scripts\python.exe -m pytest -q -rA`；exit 0，测试 18 passed；新训练未运行） |

| EV-S50 | 用户明确确认保留 `D-0059` 并采用 `D-0024/D-0025`：回放保真度仍是主指标但本轮不作为训练 loss；导出 QC 成功 = 产物存在 ∧ 可解析 ∧ CC64 可枚举，`C == 2×min(S,T)` 仅作诊断，`[0.80,1.05]` 带宽及元素比约 1.0 作废。 | `D-0082`；`TASK_CHARTER.md` sha256 `AA248F20E0F754DE2D720459E33E4BE6468C77407D27DFC2896514E083CE8279`；`PedNotate_Plan_v3.0.md` sha256 `7FF4EC77D634E41F01D91B98E977C84F85E7DC562007ED79F3A3D94EC737A05A`；`DECISIONS.md` sha256 `B7D7F3B9EB335867403DC0572286F12C76A0FE0D41C05776789D05709B1C26F6`；`FIELD_DEFINITIONS.md` sha256 `FC3319848DCCD531B98FBE4BB030C2353408F88B4D0B7C383E800BD15E96C7E6`；`ACCEPTANCE.md` AC-R9/AC-R10 | verified_in_this_repo（文档级收口；命令：12 项文档断言 + `.\.venv\Scripts\python.exe -m pytest -q -rA`；exit 0，测试 18 passed；新训练未运行） |
| EV-S51 | LangGraph 控制平面 v1 已实现：Goal Contract、Context Packet、preflight policy、命令 allowlist、shell=False ExecutionRecord、candidate Evidence、postflight promotion、长上下文 bounded context 和 thread_id 防覆盖；新增 `tests/test_control_plane.py`。 | `pytest -q`（exit 0，31 passed，2026-10-09）；`TASK_CHARTER.md` sha256 `AC131E40DC3E60B38FB7F77B870873977C16E595FBA907991032406AB9B9D1A7`；`PedNotate_Plan_v3.0.md` sha256 `825E4C4F698FBFDB41FEC6BD728DDC740C7E159C4737CC59B7E3D5B0614AE6D8`；`DECISIONS.md` sha256 `5E336C4AA6162F5C4BFA52D5D8607A2B462DDDFF0898E36D5A43E8532C0D8E9B`；`FIELD_DEFINITIONS.md` sha256 `9B7831A6548232D918D85898DB5338C42C0CB3A4B676E2AAF5765B99003841FF`；`governance_baseline.json` sha256 `57B2023490D69B5B3B34E01BCA3124DFB303243ACB824E81774EF75820699B8D`；新增 `contract.py`、`control.py`；修改 schemas/nodes/graph/memory | verified_in_this_repo |
| EV-S52 | DeepSeek v4.1 flash 可选 LLM adapter 已实现：默认关闭；通过 OpenAI-compatible HTTP 调用；环境变量配置 model/base URL/key；不在仓库保存 key；新增 plan-only callable 接口和 adapter tests。 | `pytest -q`（exit 0，34 passed，2026-10-09）；`src/research_agent/llm/client.py`、`factory.py`、`config/llm.local.env`（gitignored）、`config/llm.env.example`；`TASK_CHARTER.md` sha256 `F261F8BD66957E815B8A0AF390766C4549A4295218713A5584D2FBF7AD947164`；`PedNotate_Plan_v3.0.md` sha256 `825E4C4F698FBFDB41FEC6BD728DDC740C7E159C4737CC59B7E3D5B0614AE6D8`；`DECISIONS.md` sha256 `406ECD063C1B5751E6CDB8360E28ECC051CD5A7B343A00FF02EE78FCB7246EE6`；`FIELD_DEFINITIONS.md` sha256 `744C66C5685511BBA123F8DC4D99B9885B27690BA4A77472A70662660CC5F16E`；`governance_baseline.json` sha256 `F0BFB300864B1CF1BD176C525E3BD2ADE7D5BC5EDE61FB4265351651BF06AA79` | verified_in_this_repo（代码级；live API smoke 尚未运行） |
| EV-S53 | DeepSeek 运行参数配置：model `deepseek-flash`、base URL `https://api.deepseek.com`、reasoning_effort `high`、disable_response_storage `true`、context chars `300000`、recent messages `8`、decisions `8`、output `65536` tokens；`disable_response_storage` 仅为本地上报/日志策略，不发送官方未定义的 `store` 字段；本地 key 文件为 `config/llm.local.env`。 | `D-0085`；`TASK_CHARTER.md` sha256 `F261F8BD66957E815B8A0AF390766C4549A4295218713A5584D2FBF7AD947164`；`PedNotate_Plan_v3.0.md` sha256 `825E4C4F698FBFDB41FEC6BD728DDC740C7E159C4737CC59B7E3D5B0614AE6D8`；`DECISIONS.md` sha256 `D33D983D6D935667A2C7C543DF7189D070E4C718867588AACF083E14822DEAA5`；`FIELD_DEFINITIONS.md` sha256 `2B6B68656CAAF80A573B1A95751109AF83F5F3BD051C7FCA343346C73A50A588`；`governance_baseline.json` sha256 `231D922DA289DF10EB364207952CB0BCC1BD0CF2CE7896B2C833A7D30FF761D0`；`config/llm.env.example` | verified_in_this_repo（代码/配置级；live API smoke 未运行） |
