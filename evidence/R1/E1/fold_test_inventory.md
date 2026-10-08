# test 折 7 首逐曲清点（D-0071 收口）

口径：Main 评测域 = 43 首剔 7 首含 `<repeat>`；再取 fold=test，得到 7 首。`runs` 为 split 中的演奏数；`evaluable runs` 为同时具有 alignment/MIDI、对齐音符序列长度 ≥2 且乐谱有 pedal 元素的 run 数。`pedal elements` 为 `parse_score` 读出的谱面 pedal 元素数（as-written）。

| 乐谱 | runs | evaluable runs | pedal elements |
|:--|--:|--:|--:|
| `Beethoven/Piano_Sonatas/28-1/xml_score.musicxml` | 5 | 5 | 2 |
| `Beethoven/Piano_Sonatas/29-4/xml_score.musicxml` | 2 | 1 | 22 |
| `Chopin/Ballades/1/xml_score.musicxml` | 18 | 18 | 465 |
| `Chopin/Etudes_op_10/8/xml_score.musicxml` | 28 | 28 | 72 |
| `Chopin/Scherzos/31/xml_score.musicxml` | 12 | 12 | 479 |
| `Chopin/Sonata_2/2nd_no_repeat/xml_score.musicxml` | 2 | 2 | 1 |
| `Liszt/Transcendental_Etudes/5/xml_score.musicxml` | 11 | 11 | 10 |
| **合计** | **78** | **77** | **1051** |

缺失的 1 条 run 属 `Beethoven/Piano_Sonatas/29-4`，因 alignment/MIDI 不齐，不进入可评估 runs；不是“跑不出数就丢”。

两种分母：1051 / 3615 = 29.1%（test pedal elements 占 36 域全部 pedal elements）；标签数占比 56.9% 见 `B2_summary.md`，两者不得混用。

完整命令：
```text
.venv-research\Scripts\python.exe -c "<按 split_v1.json 过滤 main_scores、repeat、fold=test；逐曲调用 inversion_consistency.parse_score 和 parse_alignment 清点>"
```
