# STATE.md — 当前工作状态（短状态页，非日志）

> 每阶段更新。保持简短：当前在哪、卡在哪、下一步做什么。详细证据放 `EVIDENCE.md`。
> **本文件不是实验日志，也不是记忆摘要。**

## 当前

- **更新时间**：2026-10-07（阶段 1 + 语料下载 / 渲染器核验）
- **当前阶段**：阶段 2 —— LangGraph 最小骨架（已完成，待用户确认）
- **阶段状态**：阶段 1 已提交；阶段 2 骨架完成、测试 6/6 PASS、示例 exit 0；**等待用户确认后进入阶段 3**
- **活动任务**：`PHASE-2`
- **分支**：`main` → `origin/main`（https://github.com/nx137/midi2score.git，已推送）
- **thread_id 约定**（阶段 2 实现）：`research:midi2score:<task_id>`，稳定可推导，禁止每次随机生成

## 阶段 1 交付物

| 文件 | 状态 |
|:--|:--|
| `AGENTS.md` | 完成（7 条硬规则 + 权威顺序 + 文件地图 + 多智能体写者约束） |
| `TASK_CHARTER.md` | 完成（GOAL-1 / 范围 / 非目标 / HC-01–HC-16 / GV-01–GV-06 / 修改流程），**不可变** |
| `RESEARCH_QUESTIONS.md` | 完成（RQ-1–RQ-7 + 已排除问题） |
| `DECISIONS.md` | 完成（D-0001–D-0005 本次确认 + D-0006–D-0019 沿袭计划书，只追加） |
| `ASSUMPTIONS.md` | 完成（AS-01–AS-07，均 open） |
| `EVIDENCE.md` | 完成（EV-01–EV-17 标注 claimed；EV-S1–EV-S3 本仓库已验证） |
| `TODO.md` | 完成（阶段 1–4 + 科研侧 R1） |
| `ACCEPTANCE.md` | 完成（科研 A / 系统 B / 治理 C 三组） |

## 测试记录

| 时间 | 范围 | 命令 | 结果 |
|:--|:--|:--|:--|
| 2026-10-07 | 阶段 1（无代码，文档级校验） | 文件存在性 + 硬约束可机读 + AGENTS 规则覆盖 + 无 `conversation_summary.md` + UTF-8 无 BOM | **PASS**：9/9 文件存在；HC 条目 16 条、GV 条目 6 条；AGENTS 规则全覆盖；无摘要文件；无 BOM |
| 2026-10-07 | 语料 manifest 口径 | `python tools/corpus_manifest.py --dataset data/asap-dataset --out evidence/corpus_manifest.csv` | **PASS**：复现出计划书哈希 `051713f7e60240be4d98389a7abc4655a69c8118e9d4231a262e7797f95914fa`（1,305 条 / 465,861,631 B；EV-S6、EV-S10、D-0020） |
| 2026-10-07 | 阶段 2：骨架测试 | `.\.venv\Scripts\python.exe -m pytest -q` | **PASS 6/6**：恢复 / 隔离 / 跨线程 store / 章程不可变 / 消息窗口≤20 / 章程漂移停在人工确认（EV-S7） |
| 2026-10-07 | 阶段 2：运行示例 | `python -m research_agent.demo` | **exit 0**：停在 human_review → resume approve → phase=reviewed → 写入 D-WP-1 → 重开 SQLite 读回（EV-S8）；无 msgpack 警告（EV-S9） |
| 2026-10-07 | 语料 + 渲染器（R1） | git clone --depth 1 --branch v2.1.1；git rev-parse HEAD；文件计数 + 字节求和；MuseScore4.exe --version | **PASS**：HEAD 4097b457…、tag v2.1.1、242 MusicXML + 1,063 alignment = 1,305、**465,861,631 B 与计划书一致**、10,314 文件、23 个 repeat 变体目录；MuseScore4 4.7.5 exit 0。**未复现** manifest SHA256（格式未规定，见 EV-S6） |

> 阶段 1 没有可执行代码，因此没有单元测试可跑；`pytest` 将在阶段 2 随依赖引入。
> 上表为真实执行结果，复现方式见 `EVIDENCE.md` 的 `EV-S3`。

## 已完成

- 仓库勘察（命令实际执行）：确认 `E:\midi2score` 非 git 仓库、无 README/依赖/测试；`E:\PedNotate` 按用户指示视为**已废弃，不参与**。
- `git init -b main`（本地，无远程）。
- 通读 `PedNotate_Plan_v3.0.md` 全文（§0–§13 + 附录 A/B/C），据此固化章程、研究问题、决策、假设、证据、待办、验收。
- 源文件哈希留痕：计划书 `ED95FA15…`、章程 `4762A7ED…`（见 `EVIDENCE.md` EV-S1/EV-S2）。

## 阻塞 / 待确认

- **阶段 1 提交**：已完成（提交前已展示 `git diff --cached --stat`；完整 diff 用 `git show HEAD` 查看）。
- **Git 身份 / 远程**：已完成 —— 提交身份 `nx137 <nx137@users.noreply.github.com>`；remote `origin` 已配置并推送 `main`。
- 阶段 2–4 代码与 6 项测试：**未开始**。

## 阶段 2 交付物（2026-10-07）

| 文件 | 内容 |
|:--|:--|
| `pyproject.toml` | 依赖 langgraph>=1.2,<2 / langgraph-checkpoint-sqlite>=3.1,<4 / pydantic>=2.13,<3；dev: pytest |
| `src/research_agent/schemas.py` | `TaskState`(TypedDict) + 9 个 Pydantic 记录模型 + `merge_by_id` reducer |
| `src/research_agent/memory.py` | 章程加载/hash、硬约束解析、消息窗口裁剪、store 读写 helper |
| `src/research_agent/nodes.py` | planner / executor / verifier / human_review |
| `src/research_agent/graph.py` | 图装配、条件路由、SqliteSaver+SqliteStore、稳定 thread_id、serde 白名单 |
| `src/research_agent/demo.py` | 运行 + 中断 + 恢复 + 历史 + 跨线程 store + 重启恢复示例 |
| `tests/test_graph.py` | 6 项骨架测试 |

## 下一步（确认后）

1. 提交阶段 1 —— 已完成（单次干净提交，已 amend 掉早前的本地草稿提交）。
2. 阶段 3：实现 `task_alignment` 三值判定 + `conflicting` 强制人工确认 + 禁止程序修改 `TASK_CHARTER.md`。

## 关键路径提醒

- **G1'（回放通道端到端）是所有科研工作的先决闸门**（计划书 §9.3）。
- 语料与渲染器已就位（见下节）；但**尚未运行任何科研实验**，所有实验结论仍为 `not_run`。
- `TASK_CHARTER.md` 不得被程序自动修改（`GV-01`）；违反即为 `conflicting`。

## 数据与渲染器（2026-10-07）

- 语料：data/asap-dataset/（CPJKU/asap-dataset@v2.1.1，HEAD 4097b45757bed854818cf87e77b92323ebf90615，工作树 clean）——**已 gitignore，绝不提交**（HC-06）。
- 渲染器：D:\MuseScore 4\bin\MuseScore4.exe = MuseScore4 4.7.5（HC-05 钉死版本）。
- manifest 口径已解决：`evidence/corpus_manifest.csv` 的 sha256 = `051713f7…`（复现命令见 EV-S6；R1-3c 关闭）。
