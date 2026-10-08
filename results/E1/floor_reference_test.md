# 地板与参照（test 折，与 E1 主表同域）

runs = 77（域：Main 43 首中不含 repeat 者，fold=test）

## micro（P=tp/(tp+fp)，wrong 不进分母；D-0063）

| 方法 | ±0 F1 | ±1 F1 | ±2 F1 |
|:--|--:|--:|--:|
| notation_reference | 1.0000 | 1.0000 | 1.0000 |
| inversion | 0.0555 | 0.3935 | 0.4701 |
| always_down | 0.0560 | 0.0560 | 0.0560 |
| beat_periodic_1 | 0.1915 | 0.1926 | 0.1926 |
| beat_periodic_2 | 0.2065 | 0.3247 | 0.3248 |
| beat_periodic_4 | 0.1805 | 0.3438 | 0.4313 |

## 分标签 P/R/F1（±1 拍）—— 解释 bp2/bp4 为何能打平

| 方法 | DOWN P | DOWN R | DOWN F1 | UP P | UP R | UP F1 |
|:--|--:|--:|--:|--:|--:|--:|
| inversion | 0.308 | 0.818 | 0.4477 | 0.228 | 0.650 | 0.3379 |
| always_down | 0.030 | 1.000 | 0.0574 | 0.000 | 0.000 | 0.0000 |
| beat_periodic_1 | 0.118 | 1.000 | 0.2114 | 0.000 | 0.000 | 0.0000 |
| beat_periodic_2 | 0.236 | 1.000 | 0.3821 | 0.000 | 0.000 | 0.0000 |
| beat_periodic_4 | 0.328 | 0.695 | 0.4457 | 0.000 | 0.000 | 0.0000 |

> notation_reference 在回放轴上输给地板（0.2434 < beat_periodic_2 0.4640），在谱面轴上退化为恒等（构造上 F1 ≡ 1.0，无判别力）。两轴上均不可作判据参照——这就是 HC-17 的举证形式。
> 回放轴数字不得并入本表；见 `results/E1/replay_fidelity_reference.md`（引 `evidence/R1/G1-replay/MAIN_METRIC_round1.md`）。

## 注记 1：域与 #pred（D-0071 更正）
- 36 评测域折内规模：train 166 runs / 2423 pedal elements；val 28 runs / 141；test 78 runs / 1051（78 中 1 条无对齐，可评估 77）。
- B1 CV d_min=0 档 #pred = 74,570，已按 `B1_perf.csv` 核为 train 折 166 runs 的合计；B1 CV 与 B2 CV 均使用同一 36 评测域。
- test pedal elements 占比 = 1051 / 3615 = 29.1%（不是用 271 runs 的 33.8%）。
