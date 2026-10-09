# 轮 B：canonical 域 LR(L2) 首轮模型结果

## 设置
- 特征：A/B/C 三组，53 列；CHANGE 关闭。
- 选择：train 内 5 折 CV 选择 class_weight，threshold 在 val 选；同时报 threshold=0.5。
- canonical domain：`[0, score_end]`，GRID=0.25。
- V1/V2/V3 均 PASS。

## CV
| class_weight | mean F1@±1 | 5 折 |
|:--|--:|:--|
| none | 0.0000 | 0.0000, 0.0000, 0.0000, 0.0000, 0.0000 |
| balanced | 0.1398 | 0.1839, 0.0893, 0.0967, 0.0179, 0.3113 |

- 选中 class_weight：**balanced**
- thresholds：{"none": [0.5, 0.5], "balanced": [0.7, 0.75]}
- annotation-beats 对照 thresholds：[0.7, 0.75]

## test 折（±1）
| 方法 | 阈值 | scope | P | R | F1 | n_pred | n_truth | tp | fp | fn | wrong |
|:--|:--|:--|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| LR_balanced | selected | micro | 0.3815 | 0.5992 | 0.4661 | 25567 | 16278 | 9753 | 15814 | 6525 | 691 |
| LR_balanced | selected | DOWN | 0.4011 | 0.8475 | 0.5445 | 17867 | 8457 | 7167 | 10700 | 1290 | 685 |
| LR_balanced | selected | UP | 0.3358 | 0.3306 | 0.3332 | 7700 | 7821 | 2586 | 5114 | 5235 | 6 |
| LR_annotation_beats | selected | micro | 0.3819 | 0.5986 | 0.4663 | 25515 | 16278 | 9744 | 15771 | 6534 | 704 |
| LR_annotation_beats | selected | DOWN | 0.4010 | 0.8466 | 0.5442 | 17857 | 8457 | 7160 | 10697 | 1297 | 698 |
| LR_annotation_beats | selected | UP | 0.3374 | 0.3304 | 0.3339 | 7658 | 7821 | 2584 | 5074 | 5237 | 6 |
| inversion_B1 | na | micro | 0.2684 | 0.7370 | 0.3935 | 44693 | 16278 | 11997 | 32696 | 4281 | 597 |
| inversion_B1 | na | DOWN | 0.3082 | 0.8179 | 0.4477 | 22445 | 8457 | 6917 | 15528 | 1540 | 195 |
| inversion_B1 | na | UP | 0.2283 | 0.6495 | 0.3379 | 22248 | 7821 | 5080 | 17168 | 2741 | 402 |
| B2_K3 | na | micro | 0.2514 | 0.6765 | 0.3665 | 43810 | 16278 | 11012 | 32798 | 5266 | 358 |
| B2_K3 | na | DOWN | 0.3317 | 0.8595 | 0.4787 | 21912 | 8457 | 7269 | 14643 | 1188 | 234 |
| B2_K3 | na | UP | 0.1709 | 0.4786 | 0.2519 | 21898 | 7821 | 3743 | 18155 | 4078 | 124 |
| beat_periodic_2 | na | micro | 0.2331 | 0.5194 | 0.3218 | 36271 | 16278 | 8455 | 27816 | 7823 | 5000 |
| beat_periodic_2 | na | DOWN | 0.2331 | 0.9998 | 0.3781 | 36271 | 8457 | 8455 | 27816 | 2 | 5000 |
| beat_periodic_2 | na | UP | 0.0000 | 0.0000 | 0.0000 | 0 | 7821 | 0 | 0 | 7821 | 0 |
| beat_periodic_4 | na | micro | 0.3237 | 0.3612 | 0.3414 | 18166 | 16278 | 5880 | 12286 | 10398 | 1875 |
| beat_periodic_4 | na | DOWN | 0.3237 | 0.6953 | 0.4417 | 18166 | 8457 | 5880 | 12286 | 2577 | 1875 |
| beat_periodic_4 | na | UP | 0.0000 | 0.0000 | 0.0000 | 0 | 7821 | 0 | 0 | 7821 | 0 |

## full 36 首（±1）
| 方法 | 阈值 | scope | P | R | F1 | n_pred | n_truth | tp | fp | fn | wrong |
|:--|:--|:--|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| LR_balanced | selected | micro | 0.2783 | 0.5284 | 0.3646 | 54315 | 28603 | 15115 | 39200 | 13488 | 1500 |
| LR_balanced | selected | DOWN | 0.2800 | 0.7652 | 0.4099 | 39548 | 14470 | 11072 | 28476 | 3398 | 1467 |
| LR_balanced | selected | UP | 0.2738 | 0.2861 | 0.2798 | 14767 | 14133 | 4043 | 10724 | 10090 | 33 |
| LR_annotation_beats | selected | micro | 0.2783 | 0.5284 | 0.3646 | 54304 | 28603 | 15114 | 39190 | 13489 | 1520 |
| LR_annotation_beats | selected | DOWN | 0.2799 | 0.7653 | 0.4098 | 39570 | 14470 | 11074 | 28496 | 3396 | 1489 |
| LR_annotation_beats | selected | UP | 0.2742 | 0.2859 | 0.2799 | 14734 | 14133 | 4040 | 10694 | 10093 | 31 |
| inversion_B1 | na | micro | 0.1682 | 0.7770 | 0.2766 | 132103 | 28603 | 22224 | 109879 | 6379 | 742 |
| inversion_B1 | na | DOWN | 0.1829 | 0.8378 | 0.3002 | 66295 | 14470 | 12123 | 54172 | 2347 | 281 |
| inversion_B1 | na | UP | 0.1535 | 0.7147 | 0.2527 | 65808 | 14133 | 10101 | 55707 | 4032 | 461 |
| B2_K3 | na | micro | 0.1613 | 0.7278 | 0.2641 | 129036 | 28603 | 20818 | 108218 | 7785 | 545 |
| B2_K3 | na | DOWN | 0.1934 | 0.8624 | 0.3159 | 64532 | 14470 | 12479 | 52053 | 1991 | 366 |
| B2_K3 | na | UP | 0.1293 | 0.5900 | 0.2121 | 64504 | 14133 | 8339 | 56165 | 5794 | 179 |
| beat_periodic_2 | na | micro | 0.1459 | 0.4883 | 0.2247 | 95738 | 28603 | 13967 | 81771 | 14636 | 7618 |
| beat_periodic_2 | na | DOWN | 0.1459 | 0.9652 | 0.2535 | 95738 | 14470 | 13967 | 81771 | 503 | 7618 |
| beat_periodic_2 | na | UP | 0.0000 | 0.0000 | 0.0000 | 0 | 14133 | 0 | 0 | 14133 | 0 |
| beat_periodic_4 | na | micro | 0.1914 | 0.3208 | 0.2397 | 47947 | 28603 | 9175 | 38772 | 19428 | 2897 |
| beat_periodic_4 | na | DOWN | 0.1914 | 0.6341 | 0.2940 | 47947 | 14470 | 9175 | 38772 | 5295 | 2897 |
| beat_periodic_4 | na | UP | 0.0000 | 0.0000 | 0.0000 | 0 | 14133 | 0 | 0 | 14133 | 0 |

## V5（只对 |Δmicro F1| ≥ 0.05 做 bootstrap）
| 域 | A | B | Δpoint | 状态 | mean Δ | CI low | CI high | P(Δ>0) |
|:--|:--|:--|--:|:--|--:|--:|--:|--:|
| test | LR_balanced | inversion_B1 | 0.0726 | bootstrap | 0.0735 | 0.0125 | 0.1318 | 0.9785 |
| test | LR_balanced | B2_K3 | 0.0996 | bootstrap | 0.0981 | 0.0440 | 0.1514 | 0.9785 |
| test | LR_balanced | beat_periodic_2 | 0.1444 | bootstrap | 0.1352 | 0.0529 | 0.1670 | 0.9785 |
| test | LR_balanced | beat_periodic_4 | 0.1247 | bootstrap | 0.1144 | 0.0202 | 0.1588 | 0.9814 |
| full | LR_balanced | inversion_B1 | 0.0880 | bootstrap | 0.0839 | 0.0362 | 0.1363 | 0.9999 |
| full | LR_balanced | B2_K3 | 0.1005 | bootstrap | 0.0958 | 0.0472 | 0.1458 | 0.9999 |
| full | LR_balanced | beat_periodic_2 | 0.1399 | bootstrap | 0.1355 | 0.0825 | 0.1796 | 1.0000 |
| full | LR_balanced | beat_periodic_4 | 0.1249 | bootstrap | 0.1225 | 0.0618 | 0.1806 | 1.0000 |

## V1-V3
- V1：特征表 hash vs 剥离 pedal 后特征表 hash = 4c2ab764235146d265ad1b98dca4776460b597917b494caa078f33b0ec19365b == 4c2ab764235146d265ad1b98dca4776460b597917b494caa078f33b0ec19365b，equal=True.
- V2：feature keys sha256 == reference keys sha256 = 669425c3619b279b02b064643bd6769a44b085e1605b183ddd933b93d3b5e621.
- V3：B2 canonical test ±1 复算逐值等于新 JSON；recomputed={"tp": 11012, "fp": 32798, "fn": 5266, "wrong": 358, "n_pred": 43810, "n_truth": 16278}.
- CHANGE 关闭；若开启将合并 stop→start 间隔 <1 拍的对数 = 3611。

## 命令
```text
.venv-research\Scripts\python.exe tools/round_b_lr.py --dataset data/asap-dataset --split evidence/R1/G1-split/split_v1.json --out-dir results/E1/domain_unified --boot 10000 --seed 20260101
```
