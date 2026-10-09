# 统一评测域：E1 主表（canonical）

canonical domain = `[0, score_end]` 内的 score-grid 全部格点；`GRID=0.25`，含无音符格点。`score_end` 仅由 MusicXML 小节长度累加决定。

runs = 271; scores = 36; B1 CV canonical argmax d_min = 0.0 拍

## test 折 / ±1 拍

| 方法 | micro F1 | DOWN F1 | UP F1 |
|:--|--:|--:|--:|
| inversion_B1 | 0.3935 | 0.4477 | 0.3379 |
| B2_K3 | 0.3665 | 0.4787 | 0.2519 |
| beat_periodic_2 | 0.3218 | 0.3781 | 0.0000 |
| beat_periodic_4 | 0.3414 | 0.4417 | 0.0000 |

## full 36 首 / ±1 拍

| 方法 | micro F1 | DOWN F1 | UP F1 |
|:--|--:|--:|--:|
| inversion_B1 | 0.2766 | 0.3002 | 0.2527 |
| B2_K3 | 0.2641 | 0.3159 | 0.2121 |
| beat_periodic_2 | 0.2247 | 0.2535 | 0.0000 |
| beat_periodic_4 | 0.2397 | 0.2940 | 0.0000 |
