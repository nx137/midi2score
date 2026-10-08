# 第 2 项：谱面解析扩展（B2 前置）— 回归检查通过

## 实现（不变量由构造保证）

- **新增独立模块** `tools/score_features.py`，**未改动** `parse_score` 的签名与返回
- `parse_score_extended(xml)` → `notes[id] = {measure, pos, pitch, chord, voice, staff, duration}`
  （`pitch` = 整数 MIDI 音高；`duration` 单位 = 四分音符）
- `anchor_features(notes, t)` → `{n_notes, bass, bass_pc, pcs}`（锚点 t 的音符集合 = `onset ∈ [t, t+GRID)`，跨 staff/voice）
- **消费者数 = 0**：新字段未进入锚点构造 / 匹配 / 划分或任何既有路径

自测（`Chopin/Ballades/3`）：`n1 pitch=63 voice=1 staff=1 dur=1.0`、`n3 chord=True`；
`anchor_features(notes, 0.0) = {n_notes:1, bass:63, bass_pc:3, pcs:{3}}`

## 回归检查（硬约束：既有输出必须逐值不变）

```
python tools/inversion_baselines.py --dataset data/asap-dataset --split evidence/R1/G1-split/split_v1.json --out-dir evidence/R1/G1-inversion --tol 1.0 --boot 200
```

| 项 | 冻结基准 | 实测 | |
|:--|--:|--:|:--|
| inversion F1 | 0.2766 | **0.2766** | ✅ |
| **#pred** | **132,116** | **132,116** | ✅ |
| always_down / bp1 | 0.0438 / 0.1546 | 0.0438 / 0.1546 | ✅ |
| bp2 / bp4 | 0.2589 / 0.2682 | 0.2589 / 0.2682 | ✅ |

⇒ **逐值不变，硬约束满足**，可进入 B2。
