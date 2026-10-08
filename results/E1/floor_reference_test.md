# 地板与参照（test 折，与 E1 主表同域）

runs = 77（域：Main 43 首中不含 repeat 者，fold=test）

## micro（P=tp/(tp+fp)，wrong 不进分母；D-0063）

| 方法 | ±0 F1 | ±1 F1 | ±2 F1 |
|:--|--:|--:|--:|
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

## 注记 1：#pred 口径（CV 表）

- **全量 271 runs**：inversion #pred = **132,116**（= 论文"全量参照"口径）
- **train 折 CV（178 runs）**：d_min=0 档 #pred = **74,570**（= 132,116 的 **56.4%**）
- 差异来源：CV 只在 **train 折** 上汇总（train 占 271 runs 的 65.7%，且 train 折 pedal 元素占比 63.8%），
  **不是**任何 run 被丢弃。test 折换算：44,693 / 132,116 = 33.8%（与 Table X 的 test 元素占比 32.5% 量级一致）。

## 注记 2：分标签表的直接含义

周期基线（always_down / bp1 / bp2 / bp4）**只预测 DOWN，UP 恒为 0**
⇒ 它们在 micro 上与 inversion"打平"**全部发生在 DOWN 类**；inversion 是唯一同时产出 UP 的方法（test 折 UP F1 = 0.3379）。
⇒ **方向更正（主控裁定，判定 D）**：超越 UP=0 是**免费的、不构成证据**；真正的门槛在 **DOWN 类**（bp4 0.4457）。B2 正是该框架的实测反例：UP 输（0.2550 < 0.3379）、DOWN 赢（0.4850 > 0.4457）。

## 注记 3：完整命令行（D-0038）

```
python tools/inversion_baselines.py --dataset data/asap-dataset --split evidence/R1/G1-split/split_v1.json --out-dir evidence/R1/G1-inversion --tol 1.0 --boot 10000
python tools/b1_dejitter.py --dataset data/asap-dataset --split evidence/R1/G1-split/split_v1.json --out-dir results/E1
python tools/e1_test_domain.py --dataset data/asap-dataset --split evidence/R1/G1-split/split_v1.json --fold test --out results/E1/floor_reference_test.md
python tools/prepush_check.ps1        # 推送前闸门（密钥/大件/禁止路径）
```
