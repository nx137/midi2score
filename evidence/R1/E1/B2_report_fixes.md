# B2 报数缺陷修正（主控第三节 7 项）— 逐项

## ① CV 分折数组：以 JSON 为准（我上一条消息 K=2/K=3 的数组有误）

| K | JSON fold_f1_at_1 | 均值 |
|--:|:--|--:|
| 1 | 0.41281, 0.18365, 0.45046, 0.03826, 0.45793 | 0.30862 |
| 2 | 0.41230, 0.18253, 0.44955, 0.03905, 0.45906 | 0.30850 |
| 3 | 0.41409, 0.18271, 0.44863, 0.03926, 0.46108 | 0.30915 |

（主控撤回的「fold 4 对 K 完全无响应」不成立：0.03826 / 0.03905 / 0.03926。）

## ② 分标签绝对计数：**未补**（需重跑带计数的版本）；空壳 per_label_test 待删或填 —— 记待办

## ③ bootstrap：**已修**

- 重跑 `inversion_baselines.py --boot 10000`（覆盖）→ `alignment_proof.bootstrap_equal = **True**`，`PASS = True`
- **D-0064 的四组 CI 逐值复现**：always_down 0.1183 / bp1 0.0504 / bp2 −0.0296 / bp4 −0.0439；mean 0.2280/0.1196/0.0188/0.0111；p_gt_0 1.0/1.0/0.752/0.6144 ⇒ **D-0064 无需更正**

## ④ 对照表 0/±2 行：见 results/E1/floor_reference_test.md（本就含 ±0/±1/±2 全曲线、五个方法）

## ⑤ 43 → 36：逐原因名单

主轴 43 首中含 `<repeat>` 被剔 7 首：
`Beethoven/31-2`、`31-2_no_repeat`、`32-1`、`Brahms/Six_Pieces_op_118/2`、`Chopin/Sonata_2/2nd`、`Schumann/Arabeske`、`Schumann/Kreisleriana/7`
（其余 continue：alignment/MIDI 缺失、len(seq) < 2。）**D 账本中确无专条** → 已补 D-0069。

## ⑥ fold 4 低分（0.0393）的解释：待办（按 fold 列曲目 + 对照踏板密度）

## ⑦ 「3.7 / 63.8 / 32.5」单位与出处：待办对账

现知出自 Table X 的 **pedal 元素占比**；与主控反推的**真值标签占比 40.9 / 2.2 / 56.9** 是**两个不同量**（元素数 vs 锚点标签数），需逐值对账后落库。

## 附加：语料事实披露（主控反推，已自洽）

train 真值 11,686（40.9%）／val 639（2.2%）／test 16,278（56.9%），合计 28,603 ✓
⇒ val「健全性检查」强度弱；E1 主表由少数高密度曲目主导。**不得重划分**，只进 Limitations。

## Round A 完成注记（2026-10-09）

- ② **已补**：`B2_perf.csv` 现有 DOWN/UP 分标签 `n_pred/n_truth/tp/fp/fn/wrong` 列；test ±1 分标签合计逐值回到聚合计数（11006/32012/5272/352），见 `results/E1/B2_summary.md` §3.2。
- B2 全量 36 首列、两域 micro bootstrap、两域分标签 bootstrap 已出数；见 `results/E1/B2_summary.md` §4–§5.1、`results/E1/B2_bootstrap_perlabel.json`。
- ⑥⑦ 已收口：test 折 7 首逐曲清点见 `evidence/R1/E1/fold_test_inventory.md`；元素占比 1051/3615=29.1%，标签占比 56.9% 分列。
- 本文件上方“未补/待办”文字保留为当时状态，Round A 以本注记及 `B2_roundA_completion.md` 为准。
