# 统一评测域：E1 主表（canonical）

canonical domain = `[0, score_end)` 的 score-grid 全部格点；`GRID=0.25`，含无音符格点。`score_end` 仅由 MusicXML 小节长度累加决定。

runs = 271; scores = 36; B1 CV canonical argmax d_min = 0.0 拍

## test 折 / ±1 拍

| 方法 | micro F1 | DOWN F1 | UP F1 |
|:--|--:|--:|--:|
| inversion_B1 | 0.3936 | 0.4477 | 0.3379 |
| B2_K3 | 0.3666 | 0.4787 | 0.2520 |
| beat_periodic_2 | 0.3221 | 0.3785 | 0.0000 |
| beat_periodic_4 | 0.3417 | 0.4422 | 0.0000 |

## full 36 首 / ±1 拍

| 方法 | micro F1 | DOWN F1 | UP F1 |
|:--|--:|--:|--:|
| inversion_B1 | 0.2767 | 0.3002 | 0.2528 |
| B2_K3 | 0.2642 | 0.3159 | 0.2121 |
| beat_periodic_2 | 0.2248 | 0.2537 | 0.0000 |
| beat_periodic_4 | 0.2399 | 0.2942 | 0.0000 |
