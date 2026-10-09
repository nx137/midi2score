#!/usr/bin/env python
"""Round D F2: full 53-column strip-pedal V1 check against cached original features."""
from __future__ import annotations
import argparse, hashlib, json, pickle, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
from inversion_consistency import parse_alignment
from round_b_features import load_score, make_stripped_score, build_run_features

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--dataset', type=Path, default=Path('data/asap-dataset'))
    ap.add_argument('--split', type=Path, default=Path('evidence/R1/G1-split/split_v1.json'))
    ap.add_argument('--cache', type=Path, default=Path('data/derived/round_c_cache.pkl'))
    ap.add_argument('--out', type=Path, default=Path('results/E1/domain_unified/round_d_v1_full.json'))
    args=ap.parse_args()
    built=pickle.load(args.cache.open('rb')); runs=built['runs']
    split=json.loads(args.split.read_text(encoding='utf-8'))
    perf={ (p['xml_score'],p['midi_performance']):p for p in split['per_performance'] }
    tmp=args.out.parent/'_v1_stripped_xml'
    score_cache={}; bad=[]
    ho=hashlib.sha256(); hs=hashlib.sha256()
    for i,r in enumerate(runs):
        p=perf[(r['score'],r['perf'])]; xml=args.dataset/r['score']; midi=args.dataset/r['perf']
        if r['score'] not in score_cache:
            sc=load_score(xml); sp=make_stripped_score(xml,tmp); ss=load_score(xml,sp)
            score_cache[r['score']]=(sc,ss)
        sc,ss=score_cache[r['score']]
        seq=sorted((o,sc['notes'][b]['pos']) for b,_,o in parse_alignment(args.dataset/p['alignment_path']) if b in sc['notes'])
        seqs=sorted((o,ss['notes'][b]['pos']) for b,_,o in parse_alignment(args.dataset/p['alignment_path']) if b in ss['notes'])
        X=np.asarray(r['X'],dtype=np.float32)
        Xs,_,_=build_run_features(ss,midi,seqs)
        ho.update(X.tobytes()); hs.update(Xs.tobytes())
        if X.shape!=Xs.shape or not np.array_equal(X,Xs,equal_nan=True):
            bad.append({'score':r['score'],'perf':r['perf'],'shape_x':list(X.shape),'shape_s':list(Xs.shape)})
        if i%25==0: print('checked',i,flush=True)
    out={'pass':not bad,'n_runs':len(runs),'n_scores':len(score_cache),'bad':bad,
         'orig_sha256':ho.hexdigest(),'strip_sha256':hs.hexdigest(),'columns':53}
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps(out,ensure_ascii=False),flush=True)
    return 0 if not bad else 1
if __name__=='__main__':
    raise SystemExit(main())
