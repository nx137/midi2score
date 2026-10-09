# M2 canonical 标签数据集

- Version: m2-v1
- Main scores: 43
- Evaluation-eligible scores: 36
- Coordinate-ambiguous scores: 7
- Main runs: 291
- Evaluation-domain runs: 271
- Supervised runs: 271
- Label rows: 114401
- Supervised label rows: 101542
- Ambiguous label rows: 18
- Raw pedal elements: 3840
- Raw DOWN: 1950
- Raw UP: 1890
- Derived CHANGE pairs: 1058
- Canonical truth elements full: 28603
- Canonical truth elements test: 16278

## Label counts (all emitted rows)

| label | anchors |
|:--|--:|
| NONE | 111656 |
| DOWN | 882 |
| UP | 805 |
| CHANGE | 1058 |

## Label counts (supervision_mask=1)

| label | anchors |
|:--|--:|
| NONE | 99039 |
| DOWN | 731 |
| UP | 717 |
| CHANGE | 1055 |

## Boundary notes

- `mask` is the Main 43 membership marker: Main runs = 1, all other runs = 0.
- `supervision_mask` is the M2 v1 loss mask: 1 only for Main, non-repeat, printed-pedal, alignment+MIDI available runs.
- The 7 repeat scores remain in the label audit but are `coordinate_ambiguous` and have `supervision_mask=0` until repeat unfolding is implemented.
- Residual same-anchor mixed events are emitted with a valid 4-class label, `label_status=ambiguous_multi_event`, and `supervision_mask=0`.
