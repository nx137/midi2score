#!/usr/bin/env python
"""Build/persist Round C feature data once (local derived cache, gitignored)."""
from __future__ import annotations
import argparse, json, pickle, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from round_b_lr import build_all_runs

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--dataset', type=Path, default=Path('data/asap-dataset'))
    ap.add_argument('--split', type=Path, default=Path('evidence/R1/G1-split/split_v1.json'))
    ap.add_argument('--annotation-json', type=Path, default=Path('data/asap-dataset/asap_annotations.json'))
    ap.add_argument('--out', type=Path, default=Path('data/derived/round_c_cache.pkl'))
    args=ap.parse_args()
    tmp=args.out.parent/'_v1_stripped_xml'
    built,err=build_all_runs(args.dataset,args.split,args.annotation_json,tmp)
    if err:
        print(json.dumps(err,ensure_ascii=False)); return 2
    args.out.parent.mkdir(parents=True,exist_ok=True)
    with args.out.open('wb') as fh:
        pickle.dump(built,fh,protocol=5)
    print(json.dumps({'runs':len(built['runs']),'scores':built['n_scores'],'v1_equal':built['v1_equal'],'out':str(args.out)},ensure_ascii=False))
    return 0
if __name__=='__main__':
    raise SystemExit(main())
