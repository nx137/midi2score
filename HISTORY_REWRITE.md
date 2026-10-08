# HISTORY_REWRITE.md — 历史重写记录

**日期**：2026-10-08（客户端时区 Asia/Shanghai）
**原因**：执行端误将 43 个合成注入的中间产物（MusicXML，**68.09 MB**）提交并推送。
**处置**：`git filter-branch --index-filter` 剥离 `evidence/R1/G1-synthetic/xml/` 路径，重写全部 33 个提交；随后 `git push --force origin main`。

## 版本标识（**按 D-0051，不以 commit SHA 作引用**）

| 项 | 值 |
|:--|:--|
| 重写前 tip | `0f433b9f3736632d6477f4f67ce6ca465967ad2c` |
| 重写后 tip | `e480406919c8857c30c925b38ce2102f806846e9` |
| 剥离路径 | `evidence/R1/G1-synthetic/xml/`（43 个 `.musicxml`，68.09 MB） |
| 本地对象清理 | `refs/original/*` 删除 + `reflog expire --expire=now --all` + `gc --prune=now`；pack 从 68 MB → **455 KiB** |

## ⚠️ 重要事实：远端未真正删除

**`git push --force` 不会让 GitHub 删除对象。** 重写后的提交虽不在任何 ref 上，但对象仍在 GitHub 对象库中，**按旧 SHA 直链可读**（主控已实测三个直链均返回内容）。
因此本仓库的"公开窗口"内，被剥离的中间产物在**技术上仍可被检索**。

彻底清除的三条路（按彻底程度排序）：

1. **删库重建**（最彻底、最快；本阶段成本低）——**尚未执行**
2. 向 GitHub Support 提交敏感数据清除请求
3. 等 GitHub 自行 gc（无 SLA，可能很久）

## 许可与论文声明要点

- 被剥离内容是**由本项目自行生成的合成注入产物**（在 ASAP 原谱上按固定规则插入 pedal 记号），
  **不含**原始语料、不含第三方再分发内容；剥离依据为 **ASAP 许可与再分发边界**（计划书 §4.3 / G3 硬闸门）。
- 论文"数据可用性"一节应写明：仓库历史曾包含生成的中间产物，已于 2026-10-08 剥离；
  中间 SHA 不可作为引用标识（D-0051）；当前受跟踪规模 99 文件 / 2.58 MB。

## 公开窗口（已闭合）

- 起始：误入库提交被推送之时（2026-10-08）
- **结束：2026-10-08 13:03:54**（仓库删除并同名重建；见下方验证）

## 最终处置：删库重建（已执行）

用户于 **2026-10-08 13:03:54** 删除并同名重建 `nx137/midi2score`（API `created_at` 为证），执行端随后推送干净历史。

**验证（API，非 HEAD）**：

| 检查 | 结果 |
|:--|:--|
| 含 68 MB 的旧 tip `0f433b9…` | **API 422 = 不存在** ✅（整条含 XML 的线已随删库消失） |
| 当前 main | `99c014e…`（干净历史） |
| 远端 refs | 仅 `refs/heads/main`，无 tags |
| 当前树条目 | 131（不含 `evidence/R1/G1-synthetic/xml/`） |

**重要澄清（曾误判）**：`git filter-branch` **只重写包含被剥路径的提交**；不含该路径的早期提交**保留原 SHA**（如 `eb65b79…`、`21befb9…`）。
因此"按旧 SHA 仍能取到某些 commit"是**正常且正确**的——那些提交从未含被剥离内容。**只有含 68 MB 的那条线消失了。**

## 防复发（D-0052）

已装**版本化 pre-push 闸门**：`.githooks/pre-push` → `tools/prepush_check.ps1`
（`git config core.hooksPath .githooks`）——拒绝 >1 MB 受跟踪文件、禁止路径（`evidence/**/{xml,mid}/`）、密钥模式。
自测：`prepush_check: OK (105 tracked files)`。
