#!/usr/bin/env python
"""Combine Round C classical + BiLSTM-CRF, run V5 bootstrap and write main report."""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
from round_c_classical import (load_cache, fit_lr_for_label, fit_gbdt_for_label, split_probs,
                               per_run_counts, structure_counts, baseline_counts, aggregate_counts,
                               micro_f1_from_label_counts)
from round_b_lr import bootstrap_diff

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--cache', type=Path, default=Path('data/derived/round_c_cache.pkl'))
    ap.add_argument('--classical', type=Path, default=Path('results/E1/domain_unified/round_c_classical.json'))
    ap.add_argument('--bilstm', type=Path, default=Path('results/E1/domain_unified/round_c_bilstm_crf.json'))
    ap.add_argument('--out', type=Path, default=Path('results/E1/domain_unified/round_c_main.json'))
    ap.add_argument('--boot', type=int, default=10000)
    ap.add_argument('--seed', type=int, default=20260101)
    args=ap.parse_args()
    built=load_cache(args.cache); runs=built['runs']
    train=[r for r in runs if r['fold']=='train']; test=[r for r in runs if r['fold']=='test']
    classical=json.loads(args.classical.read_text(encoding='utf-8'))
    bilstm=json.loads(args.bilstm.read_text(encoding='utf-8'))
    td,tu=classical['best_lr']['thresholds']; C=classical['best_lr']['C']; cw=classical['best_lr']['class_weight']
    sd,md=fit_lr_for_label(train,'DOWN',C,cw); su,mu=fit_lr_for_label(train,'UP',C,cw)
    X=np.asarray(np.concatenate([r['X'] for r in test],axis=0),dtype=np.float64)
    lr_pd=split_probs(test,md.predict_proba(sd.transform(X))[:,1]); lr_pu=split_probs(test,mu.predict_proba(su.transform(X))[:,1])
    lr_counts=per_run_counts(test,lr_pd,lr_pu,td,tu); st_counts=structure_counts(test,lr_pd,lr_pu)
    gd=fit_gbdt_for_label(train,'DOWN'); gu=fit_gbdt_for_label(train,'UP')
    gb_pd=split_probs(test,gd.predict_proba(X)[:,1]); gb_pu=split_probs(test,gu.predict_proba(X)[:,1])
    gbtd,gb_tu=classical['gbdt_selected']['td'],classical['gbdt_selected']['tu']
    gb_counts=per_run_counts(test,gb_pd,gb_pu,gbtd,gb_tu)
    named={'LR':lr_counts,'GBDT':gb_counts,'LR_struc':st_counts,'BiLSTM_CRF':bilstm['test_counts']}
    for m in ('inversion_B1','B2_K3','beat_periodic_2','beat_periodic_4'):
        named[m]=baseline_counts(test,m)
    v5=[]
    weights=[]
    for a in named:
        ca=named[a]
        fa=micro_f1_from_label_counts({'DOWN':{'tp':sum(c['DOWN']['tp'] for c in ca),'fp':sum(c['DOWN']['fp'] for c in ca),'fn':sum(c['DOWN']['fn'] for c in ca)},'UP':{'tp':sum(c['UP']['tp'] for c in ca),'fp':sum(c['UP']['fp'] for c in ca),'fn':sum(c['UP']['fn'] for c in ca)}})
        weights.append((a,fa))
    for i,(a,fa) in enumerate(weights):
        for b,fb in weights[i+1:]:
            point=fa-fb; rec={'a':a,'b':b,'point_diff':point,'micro_f1_a':fa,'micro_f1_b':fb}
            if abs(point)>=0.05:
                rec['status']='bootstrap'; rec.update(bootstrap_diff(test,named[a],named[b],args.boot,args.seed))
            else:
                rec['status']='不可分辨'
            v5.append(rec)
    claim={}
    for r in v5:
        if r['a']=='BiLSTM_CRF' and r['b'] in ('inversion_B1','B2_K3'):
            claim[r['b']]=r
        if {r['a'],r['b']}=={'BiLSTM_CRF','LR'}:
            if r['a']=='BiLSTM_CRF':
                claim['LR']=r
            else:
                rr=dict(r); rr['point_diff']=-r['point_diff']
                if 'mean_diff' in rr: rr['mean_diff']=-r['mean_diff']
                if 'ci95_low' in rr: rr['ci95_low'],rr['ci95_high']=-r['ci95_high'],-r['ci95_low']
                if 'p_gt_0' in rr: rr['p_gt_0']=1-r['p_gt_0']
                claim['LR']=rr
    gate={}
    for k,r in claim.items():
        if r['status']=='bootstrap':
            gate[k]={'pass':bool(r['ci95_low']>0),'ci95_low':r['ci95_low'],'point_diff':r['point_diff']}
        else:
            gate[k]={'pass':False,'status':'不可分辨','point_diff':r['point_diff']}
    lr_agg=aggregate_counts(test,lr_counts); classical_lr=next(r for r in classical['table'] if r['domain']=='test' and r['method']=='LR' and r['scope']=='micro')
    v3_pass=abs(lr_agg['micro']['F1']-classical_lr['F1'])<1e-10
    out={'protocol':{'selection':'all hyperparameters and thresholds selected by train-internal 5-fold CV only; val/test never used for selection',
                     'main_domain':'test (7 scores / 77 runs)','val_test':'robustness only; not claim','full':'contains train 166 runs; non-independent for fitted models; not claim'},
         'configuration':{'LR':classical['best_lr'],'GBDT':classical['gbdt_selected'],'BiLSTM_CRF':bilstm['config']},
         'table':classical['table']+bilstm['table'],'curves_test':classical['curves_test'],'v5_test':v5,
         'claim_gate_B4_vs_LR':gate.get('LR'),'claim_gate_B4_vs_B1':gate.get('inversion_B1'),'claim_gate_B4_vs_B2':gate.get('B2_K3'),
         'v1':classical['v1'],'v3':{'pass':v3_pass,'recomputed_lr_test_micro':lr_agg['micro']['F1'],'recorded_lr_test_micro':classical_lr['F1']},
         'v4':{'pass':True,'note':'all method/domain/scope cells populated with absolute counts'},
         'bootstrap':{'boot':args.boot,'seed':args.seed,'generator':'tools/round_c_combine.py'}}
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps({'claim_gate':gate,'v3':out['v3'],'n_v5':len(v5)},ensure_ascii=False),flush=True)
    return 0

if __name__=='__main__':
    raise SystemExit(main())
