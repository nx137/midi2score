# B1 回归锚失败：根因与作废声明（2026-10-08）

## 运行记录（**not-a-result，不得引用**）

`tools/b1_dejitter.py` 首次运行（271 runs，d_min=0 档）：

| 项 | 冻结基准（旧） | 实测 | 差 |
|:--|--:|--:|--:|
| #pred | 132,116 | **95,047** | −37,069（−28%） |
| ±0 拍 F1 | 0.0568 | 0.0427 | ❌ |
| ±1 拍 F1 | 0.2766 | 0.2849 | ❌ |
| ±2 拍 F1 | 0.3146 | 0.3389 | ❌ |

CV（train 内 5 折）**选中 d_min = 0**（0 与 1 格并列，按规则取更小）；val/test 各跑一次。
**但回归锚不中 ⇒ 以上 CV/val/test 数字全部标 not-a-result**，不进 E1 主表。

## 根因（主控直取核实，比执行端报告更深一层）

**反演的口径是 `(锚点, 标签)` 对集合，不是"每锚点一个状态"。**
`inversion_consistency.py` 原文：
```python
pred = set()
for t, kind in cc64_transitions(midi):
    got = to_anchor(t, seq, [])
    pred.add((snap(pos), "DOWN" if kind == "start" else "UP"))
```
- 同锚点同标签 → **去重**；同锚点 DOWN+UP → **保留两个元素**。匹配器按标签独立匹配（DOWN 只配 DOWN）。
- 所以"同锚点先踩后松"（正是 `CHANGE` 要覆盖的情形）**本来就允许**。
- 而主控规格里写的"去抖作用于**锚点二值状态序列**"暗含"每锚点最多一个标签"——**与既有匹配器和真值构造冲突**。

⇒ 结论：**方案 (a) 不只是"能对上锚"，它是唯一保持口径一致的选项**（主控缺陷 #10 认领）。

## 两处实现不一致（比回归锚更要紧）

| # | 位置 | 问题 | 影响 |
|:--|:--|:--|:--|
| **A** | `inversion_consistency.py`: `prec = tp/(tp+fp+wrong)` vs `inversion_baselines.py`: `f1_of = tp/(tp+fp)` | **反演被多扣"错向"，基线没有** ⇒ 两者不可直接比 | `wrong` 只在 `tol>0` 计算 ⇒ **0 拍档不受影响**，「0 拍下反演输全部周期基线 ⇒ 病在任务」**仍成立**；但 **±1/±2 的对比可能是口径造成的**，「±2 输 bp_4、优势脆弱」**不能当定论** |
| **B** | `inversion_consistency.py` 末行 `print(f"microF1={sum(vals)/len(vals)}")` | 那是**逐 run 平均（macro）**，标签写成 micro；`inversion_baselines.py` 的 `2tp/(2tp+fp+fn)` 才是真 micro | `RESULT_density.md` 的行**可能混口径**（inversion 行与基线行来自不同脚本、不同汇总、不同 wrong 处理）——性质同 D-0040 的混合坐标系 |
| 附 | `inversion_consistency.py` 的 `reps = sorted(...)` | **死代码**（注释声称"书写坐标 × playthrough"，未实现） | 在"不含 repeat"范围内无害，记一行 |

## 处置（主控裁定，待执行）

1. **统一 `f1_of`** 为共享函数（保留 `wrong` 绝对计数），两处同用；重出对照表 `tol ∈ {0,1,2} × {inversion, always_down, bp1, bp2, bp4}`，**同一 micro、同一 wrong 项** → 这张表即 B1 的对照基准
2. **B1 按 (a) 改**：pred 逐字复用 `cc64_transitions`/`to_anchor`/`snap`；**去抖插在 `cc64_transitions` 与 `to_anchor` 之间**，作用于事件序列段长。规则写死：段 = 相邻两事件之间的区间；时长 < d_min 拍的段 → 移除界定它的两个事件并与前后段合并；从前向后单遍、不递归；首事件前取反状态、末事件后保持末状态。`d_min=0` ⇒ 无事件移除 ⇒ pred 与反演逐元素相同
3. **回归锚替换**：`d_min=0` 必须精确复现 ① 重出后的 inversion 行（#pred + 三档 P/R/F1）。**旧的 132,116 标「未审计口径」作废，不再作锚**
