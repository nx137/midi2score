# TODO.md — 可执行待办

> 状态：`todo` / `doing` / `blocked` / `done`。`blocking` 为前置依赖。
> **阶段推进必须等待用户逐阶段确认**；确认前不得进入下一阶段。
> 本文件只放待办；决策见 `DECISIONS.md`，假设见 `ASSUMPTIONS.md`。

## 2026-10-09 V3 原计划复位（当前）

> 权威决策：`D-0081`。以下条目替代下方旧轮次作为当前执行路径；旧 Round B/C/D、D1 sweep 与 score-consistency 主线保留为历史记录和诊断证据，不再作为当前主线。

| ID | 待办 | blocking | 状态 |
|:--|:--|:--|:--|
| V3R-1 | TASK_CHARTER v1.3：主指标恢复为回放保真度，谱面一致度改强制副指标 | — | done |
| V3R-2 | PedNotate_Plan v3.1：明确“成熟 MIDI→MusicXML + S2 踏板层”集成定位 | V3R-1 | done |
| V3R-3 | 冻结训练顺序：ASAP 初始训练 → PDMX 合成语料增强训练 | V3R-2 | done |
| CP-1 | Goal Contract + 来源内容哈希 | — | done |
| CP-2 | 有界 Context Packet + confirmed decisions 注入 | CP-1 | done |
| CP-3 | preflight policy：目标相关性、阶段、路径、命令 allowlist | CP-1 | done |
| CP-4 | argv / shell=False 命令执行器 + ExecutionRecord | CP-3 | done |
| CP-5 | candidate Evidence → postflight `verified` | CP-4 | done |
| CP-6 | 长上下文偏移、越权命令、缺证据、thread_id 覆盖测试 | CP-2,CP-5 | done |
| CP-7 | 写入 EVIDENCE / ACCEPTANCE / STATE，生成 governance baseline | CP-6 | done |
| LLM-1 | 可选 DeepSeek/OpenAI-compatible HTTP adapter；默认关闭 | — | done |
| LLM-2 | 环境变量配置 model/base URL/key；key 不入库 | LLM-1 | done |
| LLM-3 | live smoke：真实 API 返回受控计划文本 | LLM-2 | todo |
| V3R-4 | 把 Round B/C/D 标为历史诊断，停止其主线 claim/闸门用途 | V3R-3 | done |
| V3R-5 | 对齐 FIELD_DEFINITIONS / ACCEPTANCE / EVIDENCE | V3R-4 | done |
| V3R-7 | 保留 D-0059：回放通道不作本轮 loss | V3R-5 | done |
| V3R-8 | 采用 D-0024/D-0025：成功判据恢复、恒等式诊断、废弃带宽门 | V3R-5 | done |
| V3R-6 | 主线恢复为 S2 + S3 + S5；Round D 的 `model1` 仅作历史 harness 证据 | V3R-3 | todo |
| V3R-9 | 按 V3 原计划进入 M2 标签层 | V3R-5,V3R-7,V3R-8 | todo |

> 下方旧条目按日期保留，其中出现的旧主指标、旧 blocked 状态和旧路线不再自动生效；如与 D-0081 冲突，以 D-0081 为准。

## 阶段 1：项目规则与科研任务文件（历史）

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
| R1-3j | 分位点估计量 → 已裁定（D-0035 A+：estimator-free 主描述 + R-7 次描述；P5 不得进摘要/判据） | — | done |
| R1-4a-0 | 交付 5 第 0 步：通道自检 | — | todo |
| R1-4a-b | ①b 锚点还原 | — | done（解析验证通过；36 首 / 271 对） |
| R1-4a-c | 修匹配：贪心 → 最优指派 | — | done（F1 单调、错向=0） |
| R1-4a-d | ④ 基线 + bootstrap | — | done（**未通过 → 停机条件 ③ 触发**；见 `RESULT_phase4_baselines.md`） |
| R1-4a-f | Plan B 裁定：**收 B1**（反演降为诊断量，闸门回主指标）；B2/B3 驳回 | — | done（D-0048） |
| R1-4a-g | 修小节长度累加 bug | — | done（A 已重算为 632,110） |
| R1-4a-h | 第 0 步通道自检 | — | done（剥离后注入：计数 43/43、顺序 43/43、位置 40/43） |
| R1-4a-i | 主指标（回放保真度）；若仍输周期基线 → §9.3 降级路径 | R1-4a-h | todo |
| R1-4a-e | 第 0 步通道自检 | — | done（EV-S38；条件①未触发） |
| R1-4a-j | 主指标：渲染侧坐标化 | 改走**顺序对应 + tick/PPQ**（DTW 暂不建）；闭环 3 例中 2 例近乎精确，**Ravel 偏差 4.3 拍未归因 → 自检未过** | todo |
| R1-4a-k | 归因 Ravel 偏差 | 第 2 轮：确认为累加漂移，时号口径更差 → **未通过** | done |
| R1-4a-z | ~~触发预声明降级~~ **D-0049 已撤销**（D-0050 重开） | — | done |
| R1-5a | 43 首通道覆盖率表（逐首列名 + 特征 + 分类） | — | done（`coverage_43.md`；in_grid 18 / T2类 9 / deviation 8 / no_data 8） |
| R1-5b | 合成注入自检（43 首全覆盖） | — | done（顺序 43/43 不减；计数 10/43 精确，33 首未归因） |
| R1-5c | 归因计数偏差 | — | done（叠加注入 + 既有 T2 缺口；顺序 43/43） |
| R1-5e | 逐小节分叉点定位 | — | done（剥离后注入；3 首越界谱定位到首坏小节） |
| R1-5f | 主指标出数（事件级 + 容差曲线 + 三折） | — | done（`MAIN_METRIC_round1.md`；oracle 输全部基线 → 待裁定） |
| R1-5g | 待裁定：主指标输基线 → B4 降级 or 归因"指标病" | 主控 | blocked |
| R1-5d | 主指标：出数（不冻结有效域，带三折分布） | R1-5c | todo |
| R1-4a-b | ①b 锚点还原（复用分段线性规则，展开坐标由 nASAP 给出） | R1-4a-0 | todo |
| R1-4a | 交付 5：0/±1/±2 拍曲线 + micro/macro + 逐作曲家 + 绝对计数混淆 | R1-4a-b | todo |
| R1-4c | bootstrap 10,000 对 always_down / beat_periodic_N | R1-4a | todo |
| R1-3k | Main 口径 → 已裁定（D-0039：以谓词为准，§4.4 已勘误） | — | done |
| R1-3l | 坐标系 → 已裁定 **A4**（D-0045）：记号计数 as-written / 恒等式限 58 首 / 10 首 coordinate_ambiguous；4a(ii) 撤销 | — | done |
| R1-3m | 交付 6 收讫 + `assignment_sha256` 冻结标识 | — | done（EV-S34） |
| R1-3n | 欠账 #4 **结清**（8/13 在主轴、69/3840 = 1.8%；13 首全 `S=0` → 坐标不变，unfolded 半边不需要） | — | done |
| R1-3o | 决策权限边界规则入库（D-0044） | — | done |
| R1-4b | G1' 交付 6：主表划分冻结 | — | done（EV-S26；identity = `assignment_sha256 = 2a5ff6e8…`（D-0043/EV-S34；不再用文件字节哈希）） |

## 明确不做（YAGNI）

- `conversation_summary.md`、向量库 / 语义检索、Web API / UI、多智能体 supervisor、Postgres、LLM 供应商抽象层、未来需求脚手架。

## R1 当前窗口（2026-10-09，B2 Round A 后）

| ID | 待办 | blocking | 状态 |
|:--|:--|:--|:--|
| R1-B2-A1 | B2 分标签绝对计数 + `B2_perf.csv` 分标签列 + 逐值自校 | — | done（test ±1 合计 11006/32012/5272/352） |
| R1-B2-A2 | B2 全量 36 首列 + 两域 micro/bootstrap + 两域分标签 bootstrap | — | done（`B2_summary.*`、`B2_bootstrap_perlabel.json`） |
| R1-B2-A3 | floor 表 notation_reference 恒等行、回放轴独立表、注记 1 的 36 域分母更正、test 7 首清点 | — | done（`floor_reference_test.md`、`replay_fidelity_reference.md`、`fold_test_inventory.md`） |
| R1-B3-B | 轮 B：锚点级训练表（标签 + A/B/C 特征 + 命名空间检查；CHANGE 关闭并报合并对数） | R1-B2-A3 | todo |
| R1-B3-C | 轮 C：HistGradientBoosting 两独立二分类训练 + 两域评估 + 消融 | R1-B3-B | todo |

## 轮 B：canonical 统一域（2026-10-09，STOP ③）

| ID | 待办 | blocking | 状态 |
|:--|:--|:--|:--|
| R1-DU-1 | canonical `[0,score_end)` 定义与全部方法复算 | — | done（`results/E1/domain_unified/`；D-0074） |
| R1-DU-2 | B1 canonical CV argmax 披露 | — | done（argmax d_min=0.0 拍） |
| R1-DU-3 | 停机条件 ③ 判定：B2 full canonical−旧域 micro 差 | R1-DU-1 | **blocked/stop**（−0.03290759 > 0.03） |
| R1-B3-B | 训练表 A/B/C + 无泄漏自证 + LR | R1-DU-3 + V1 定义裁定 | blocked |
| R1-B3-C | 结构化模型与两域评估 | R1-B3-B | blocked |

> V1 定义冲突：§5.1 A 层源自 CC64，且 δ/局部 IBI 若取 performance beats 则触碰 `asap_annotations.json`；不得自行发明 score-grid IBI。

## 轮 B 完成（2026-10-09）

| ID | 待办 | blocking | 状态 |
|:--|:--|:--|:--|
| R1-B-DU | canonical 闭区间 `[0,score_end]`；full/test n_truth 对账 | — | done（28,603 / 16,278） |
| R1-B-FEAT | A/B/C 特征表、V1 剥离 pedal 逐值全等、命名空间检查 | R1-B-DU | done（hash 4c2ab764…） |
| R1-B-LR | LR(L2) 两档 class_weight、DOWN/UP 独立分类、val 阈值、0.5 对照 | R1-B-FEAT | done（选中 balanced；test micro 0.4661 / full 0.3646） |
| R1-B-V | V1/V2/V3/V4/V5 验收 | R1-B-LR | done（V1–V3 PASS；V5 8 对 bootstrap） |
| R1-C-B3 | 轮 C：结构化模型（B3）与两域评估 | R1-B-V | todo |

> 轮 C 门槛：canonical 域上 test 与 full 同时 micro 显著优于 B1（0.3935/0.2766）与 B2（0.3665/0.2641）；DOWN > 0.5445/0.4099，UP ≥ 0.3379/0.2528。主表三列并列。

## 轮 C 完成（2026-10-09）

| ID | 待办 | blocking | 状态 |
|:--|:--|:--|:--|
| R1-C-PROTO | train-CV 选择协议；val/test 不参与选择 | — | done |
| R1-C-LR | 重跑 LR(L2)，所有超参与阈值 train-CV | R1-C-PROTO | done（test micro 0.392995） |
| R1-C-GBDT | GBDT 行 | R1-C-PROTO | done（test micro 0.310068） |
| R1-C-STRUCT | LR + 确定性结构解码 | R1-C-PROTO | done（test micro 0.230132） |
| R1-C-B4 | BiLSTM-CRF 行 | R1-C-PROTO | done（test micro 0.080336；对 LR 门槛不过） |
| R1-C-WAIT | 主控终局判读/claim 确认 | R1-C-B4 | blocked（等待裁定） |

## 轮 D 修复（2026-10-09）

| ID | 待办 | 状态 |
|:--|:--|:--|
| R1-D-F1 | 全库 LR 统一 sklearn 约定；C 对数网格 train-CV | done（C=1.0；test 0.392995） |
| R1-D-F2 | V1 扩展到 53 列全矩阵 | done（hash 03821d67…） |
| R1-D-F3 | BiLSTM-CRF full-seq/hidden128/早停/类权重 | blocked（训练 loss=NaN，无可信模型） |
| R1-D-F4 | LR_struc 降为解释行 | todo（等待 F3 裁定后随主表整理） |
| R1-D-WAIT | 主控裁定 F3 NaN 的继续/停机路径 | blocked |

## T-MODEL-1（2026-10-09）

| ID | 待办 | 状态 |
|:--|:--|:--|
| T-MODEL-1-A | harness：seed/epochs200/patience10/inner-val micro/val/NONE+DOWN+UP+macro/checkpoint/config/clip | done |
| T-MODEL-1-B | NaN 阶梯：L1 NaN；L3 关闭 CRF 类权重后非 NaN | done |
| T-MODEL-1-C | 完整成功运行 + best_model.pt/config.json/test/val/per-score/wall/CSV | done |
