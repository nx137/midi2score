#!/usr/bin/env python
"""Round D F1: sklearn LR C grid + legacy/custom diagnostic."""
from __future__ import annotations
import argparse, csv, json, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
from round_c_classical import (load_cache, fit_lr_for_label, concat, labels, split_probs,
                               select_label_threshold, eval_probs, per_run_counts)
from round_b_lr import fit_lr as legacy_fit_lr, sample_weight as legacy_weights, apply_scaler

C_GRID = [1e-6, 1e-5, 1e-4, 1e-3, 1e-2, 1e-1, 1.0, 10.0, 100.0]

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--cache', type=Path, default=Path('data/derived/round_c_cache.pkl'))
    ap.add_argument('--out-dir', type=Path, default=Path('results/E1/domain_unified'))
    args=ap.parse_args()
    built=load_cache(args.cache); runs=built['runs']
    train=[r for r in runs if r['fold']=='train']; test=[r for r in runs if r['fold']=='test']
    groups=sorted({r['group'] for r in train}); fold_id={g:i%5 for i,g in enumerate(groups)}
    rows=[]
    for C in C_GRID:
        folds=[]
        for k in range(5):
            tr=[r for r in train if fold_id.get(r['group'])!=k]; va=[r for r in train if fold_id.get(r['group'])==k]
            sd,md=fit_lr_for_label(tr,'DOWN',C,'balanced'); su,mu=fit_lr_for_label(tr,'UP',C,'balanced')
            Xv=np.asarray(concat(va),dtype=np.float64)
            pdv=md.predict_proba(sd.transform(Xv))[:,1]; puv=mu.predict_proba(su.transform(Xv))[:,1]
            folds.append((va,split_probs(va,pdv),split_probs(va,puv)))
        td,df1=select_label_threshold(folds,'DOWN'); tu,uf1=select_label_threshold(folds,'UP')
        cv_vals=[eval_probs(rr,pd,pu,td,tu)['micro']['F1'] for rr,pd,pu in folds]
        sd,md=fit_lr_for_label(train,'DOWN',C,'balanced'); su,mu=fit_lr_for_label(train,'UP',C,'balanced')
        Xt=np.asarray(concat(test),dtype=np.float64)
        pd=split_probs(test,md.predict_proba(sd.transform(Xt))[:,1]); pu=split_probs(test,mu.predict_proba(su.transform(Xt))[:,1])
        te=eval_probs(test,pd,pu,td,tu)
        rows.append({'C':C,'td':td,'tu':tu,'cv_mean_micro':float(np.mean(cv_vals)),'cv_folds':cv_vals,
                     'test_micro':te['micro']['F1'],'test_DOWN':te['DOWN']['F1'],'test_UP':te['UP']['F1'],
                     'test_n_pred':te['micro']['n_pred'],'test_n_truth':te['micro']['n_truth']})
        print('C',C,rows[-1],flush=True)
    best=max(rows,key=lambda r:(r['cv_mean_micro'],-abs(r['C']-1.0)))
    Xtr=np.asarray(concat(train),dtype=np.float64); Xte=np.asarray(concat(test),dtype=np.float64)
    mean=np.mean(Xtr,axis=0); std=np.std(Xtr,axis=0); std[std<1e-8]=1.0
    Xtrs=(Xtr-mean)/std; Xtes=(Xte-mean)/std
    wd,bd=legacy_fit_lr(Xtrs,labels(train,'DOWN'),legacy_weights(labels(train,'DOWN'),'balanced'),C=1.0)
    wu,bu=legacy_fit_lr(Xtrs,labels(train,'UP'),legacy_weights(labels(train,'UP'),'balanced'),C=1.0)
    from scipy.special import expit
    lpd=[]; lpu=[]; i=0
    for r in test:
        n=len(r['anchors']); z=Xtes[i:i+n]; i+=n
        lpd.append(expit(z@wd+bd)); lpu.append(expit(z@wu+bu))
    legacy={}
    for name,td,tu in (('threshold0.5',0.5,0.5),('threshold0.7_0.75',0.7,0.75),('selected',best['td'],best['tu'])):
        m=eval_probs(test,lpd,lpu,td,tu); legacy[name]={'micro':m['micro']['F1'],'DOWN':m['DOWN']['F1'],'UP':m['UP']['F1']}
    sd,md=fit_lr_for_label(train,'DOWN',1.0,'balanced'); su,mu=fit_lr_for_label(train,'UP',1.0,'balanced')
    spd=split_probs(test,md.predict_proba(sd.transform(Xte))[:,1]); spu=split_probs(test,mu.predict_proba(su.transform(Xte))[:,1])
    sk={}
    for name,td,tu in (('threshold0.5',0.5,0.5),('threshold0.7_0.75',0.7,0.75),('selected',best['td'],best['tu'])):
        m=eval_probs(test,spd,spu,td,tu); sk[name]={'micro':m['micro']['F1'],'DOWN':m['DOWN']['F1'],'UP':m['UP']['F1']}
    out={'c_grid':rows,'best':best,'diagnostic':{'legacy':legacy,'sklearn':sk,
         'note':'same 53-column features and same train/test split; legacy uses custom objective/optimizer; sklearn uses L2 logistic objective'}}
    (args.out_dir/'round_d_lr_grid.json').write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    with (args.out_dir/'round_d_lr_grid.csv').open('w',encoding='utf-8',newline='') as fh:
        w=csv.DictWriter(fh,fieldnames=['C','td','tu','cv_mean_micro','test_micro','test_DOWN','test_UP','test_n_pred','test_n_truth']); w.writeheader()
        w.writerows([{k:r[k] for k in w.fieldnames} for r in rows])
    print(json.dumps({'best':best,'diagnostic':out['diagnostic']},ensure_ascii=False),flush=True)
    return 0
if __name__=='__main__':
    raise SystemExit(main())
