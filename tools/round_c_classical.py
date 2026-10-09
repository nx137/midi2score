#!/usr/bin/env python
"""Round C classical ladder: LR(L2), GBDT, deterministic structure decoding."""
from __future__ import annotations
import argparse, csv, json, pickle, sys
from pathlib import Path
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.preprocessing import StandardScaler
sys.path.insert(0, str(Path(__file__).resolve().parent))
from b2_perlabel_bootstrap import per_label_counts
from round_b_lr import bootstrap_diff, micro_f1_from_label_counts

THRESHOLDS = [round(0.05 * i, 2) for i in range(1, 20)]
DOMAINS = ("test", "val_test", "full")
METHODS = ("LR", "GBDT", "LR_struc")
BASELINES = ("inversion_B1", "B2_K3", "beat_periodic_2", "beat_periodic_4")


def load_cache(path):
    with Path(path).open("rb") as fh:
        return pickle.load(fh)


def concat(runs, key="X"):
    return np.concatenate([r[key] for r in runs], axis=0)


def labels(runs, lab):
    return np.concatenate([r["y_" + lab] for r in runs], axis=0)


def fit_scaler(X):
    return StandardScaler().fit(np.asarray(X, dtype=np.float64))


def fit_lr(runs, C, cw):
    sc = fit_scaler(concat(runs))
    X = sc.transform(np.asarray(concat(runs), dtype=np.float64))
    m = LogisticRegression(penalty="l2", C=C, solver="lbfgs", max_iter=500, class_weight=cw, random_state=20260101)
    m.fit(X, labels(runs, "DOWN"))
    return sc, m


def fit_gbdt(runs, cw="balanced"):
    m = HistGradientBoostingClassifier(learning_rate=0.1, max_iter=200, max_leaf_nodes=31,
                                        min_samples_leaf=50, l2_regularization=1.0,
                                        early_stopping=False, class_weight=cw, random_state=20260101)
    m.fit(np.asarray(concat(runs), dtype=np.float64), labels(runs, "DOWN"))
    return m


def probs_lr(sc, m, runs):
    X = sc.transform(np.asarray(concat(runs), dtype=np.float64))
    return m.predict_proba(X)[:, 1]


def probs_gbdt(m, runs):
    return m.predict_proba(np.asarray(concat(runs), dtype=np.float64))[:, 1]


def summarize_counts(parts):
    out = {}
    for lab in ("DOWN", "UP"):
        c = parts[lab]
        pp = c["tp"] / c["n_pred"] if c["n_pred"] else 0.0
        rr = c["tp"] / c["n_truth"] if c["n_truth"] else 0.0
        out[lab] = {**c, "P": pp, "R": rr, "F1": 2 * pp * rr / (pp + rr) if (pp + rr) else 0.0}
    tp = out["DOWN"]["tp"] + out["UP"]["tp"]
    fp = out["DOWN"]["fp"] + out["UP"]["fp"]
    fn = out["DOWN"]["fn"] + out["UP"]["fn"]
    wrong = out["DOWN"]["wrong"] + out["UP"]["wrong"]
    n_pred = out["DOWN"]["n_pred"] + out["UP"]["n_pred"]
    n_truth = out["DOWN"]["n_truth"] + out["UP"]["n_truth"]
    pp = tp / n_pred if n_pred else 0.0
    rr = tp / n_truth if n_truth else 0.0
    out["micro"] = {"tp": tp, "fp": fp, "fn": fn, "wrong": wrong, "n_pred": n_pred, "n_truth": n_truth,
                    "P": pp, "R": rr, "F1": 2 * pp * rr / (pp + rr) if (pp + rr) else 0.0}
    return out


def eval_probs(runs, pd_list, pu_list, td, tu):
    parts = {"DOWN": {"tp":0,"fp":0,"fn":0,"wrong":0,"n_pred":0,"n_truth":0},
             "UP": {"tp":0,"fp":0,"fn":0,"wrong":0,"n_pred":0,"n_truth":0}}
    for r, pd, pu in zip(runs, pd_list, pu_list):
        pred = set()
        for i, a in enumerate(r["anchors"]):
            if pd[i] >= td: pred.add((a, "DOWN"))
            if pu[i] >= tu: pred.add((a, "UP"))
        c = per_label_counts(pred, r["truth"], 1.0)
        for lab in ("DOWN", "UP"):
            for k in parts[lab]: parts[lab][k] += c[lab][k]
    return summarize_counts(parts)
# test append

def label_f1_fold(runs, pd_list, pu_list, lab, tau, tol=1.0):
    tp = fp = fn = 0
    for r, pd, pu in zip(runs, pd_list, pu_list):
        pred = set()
        for i, a in enumerate(r["anchors"]):
            if lab == "DOWN" and pd[i] >= tau: pred.add((a, "DOWN"))
            if lab == "UP" and pu[i] >= tau: pred.add((a, "UP"))
        tr = {x for x in r["truth"] if x[1] == lab}
        m = __import__("inversion_baselines", fromlist=["f1_of"]).f1_of(pred, tr, tol)
        tp += m["tp"]; fp += m["fp"]; fn += m["fn"]
    p = tp / (tp + fp) if (tp + fp) else 0.0
    r = tp / (tp + fn) if (tp + fn) else 0.0
    return 2 * p * r / (p + r) if (p + r) else 0.0

def select_label_threshold(folds, lab):
    best = None
    for tau in THRESHOLDS:
        vals = [label_f1_fold(runs, pd, pu, lab, tau) for runs, pd, pu in folds]
        mean = float(np.mean(vals))
        key = (mean, -abs(tau - 0.5), -tau)
        if best is None or key > best[0]:
            best = (key, tau, mean)
    return best[1], best[2]


def select_lr_config(folds_by_config, configs):
    results = {}
    for cfg in configs:
        folds = folds_by_config[cfg]
        td, df1 = select_label_threshold(folds, "DOWN")
        tu, uf1 = select_label_threshold(folds, "UP")
        micro_vals = []
        for runs, pd, pu in folds:
            micro_vals.append(eval_probs(runs, pd, pu, td, tu)["micro"]["F1"])
        results[cfg] = {"td": td, "tu": tu, "mean_micro": float(np.mean(micro_vals)),
                        "down_f1": df1, "up_f1": uf1}
    return results

def viterbi_decode(pd, pu):
    n = len(pd)
    eps = 1e-12
    p_none = np.maximum(1.0 - np.maximum(pd, pu), eps)
    em = np.log(np.stack([p_none, np.maximum(pd, eps), np.maximum(pu, eps)], axis=1))
    allowed = np.array([[1,1,1],[1,0,1],[1,1,0]], dtype=bool)
    neg = -1e18
    dp = em[0].copy(); back = np.zeros((n, 3), dtype=np.int8)
    for i in range(1, n):
        ndp = np.full(3, neg); bk = np.zeros(3, dtype=np.int8)
        for s in range(3):
            best_prev = -1; best_val = neg
            for p in range(3):
                if allowed[p, s] and dp[p] > best_val:
                    best_val = dp[p]; best_prev = p
            ndp[s] = best_val + em[i, s]
            bk[s] = best_prev
        dp = ndp; back[i] = bk
    s = int(np.argmax(dp)); tags = [s]
    for i in range(n-1, 0, -1):
        s = int(back[i, s]); tags.append(s)
    tags.reverse()
    return np.asarray(tags, dtype=np.int8)

def eval_structure(runs, pd_list, pu_list):
    parts = {"DOWN": {"tp":0,"fp":0,"fn":0,"wrong":0,"n_pred":0,"n_truth":0},
             "UP": {"tp":0,"fp":0,"fn":0,"wrong":0,"n_pred":0,"n_truth":0}}
    for r, pd, pu in zip(runs, pd_list, pu_list):
        tags = viterbi_decode(pd, pu)
        pred = set()
        for i, a in enumerate(r["anchors"]):
            if tags[i] == 1: pred.add((a, "DOWN"))
            if tags[i] == 2: pred.add((a, "UP"))
        c = per_label_counts(pred, r["truth"], 1.0)
        for lab in ("DOWN", "UP"):
            for k in parts[lab]: parts[lab][k] += c[lab][k]
    return summarize_counts(parts)

def per_run_counts(runs, pd_list, pu_list, td, tu):
    out = []
    for r, pd, pu in zip(runs, pd_list, pu_list):
        pred = set()
        for i, a in enumerate(r["anchors"]):
            if pd[i] >= td: pred.add((a, "DOWN"))
            if pu[i] >= tu: pred.add((a, "UP"))
        out.append(per_label_counts(pred, r["truth"], 1.0))
    return out


def aggregate_counts(runs, counts):
    parts = {"DOWN": {"tp":0,"fp":0,"fn":0,"wrong":0,"n_pred":0,"n_truth":0},
             "UP": {"tp":0,"fp":0,"fn":0,"wrong":0,"n_pred":0,"n_truth":0}}
    for c in counts:
        for lab in ("DOWN", "UP"):
            for k in parts[lab]: parts[lab][k] += c[lab][k]
    return summarize_counts(parts)

def baseline_counts(runs, method):
    return [r["baseline_counts"][method] for r in runs]


def threshold_curve(runs, pd_list, pu_list, fixed_down, fixed_up, vary):
    out = []
    for tau in THRESHOLDS:
        td, tu = (tau, fixed_up) if vary == "DOWN" else (fixed_down, tau)
        m = eval_probs(runs, pd_list, pu_list, td, tu)
        out.append({"threshold": tau, "micro_F1": m["micro"]["F1"], "DOWN_F1": m["DOWN"]["F1"], "UP_F1": m["UP"]["F1"]})
    return out


def fit_lr_for_label(runs, lab, C, cw):
    sc=fit_scaler(concat(runs))
    X=sc.transform(np.asarray(concat(runs),dtype=np.float64))
    m=LogisticRegression(penalty='l2',C=C,solver='lbfgs',max_iter=500,class_weight=cw,random_state=20260101)
    m.fit(X,labels(runs,lab))
    return sc,m


def fit_gbdt_for_label(runs, lab, cw='balanced'):
    m=HistGradientBoostingClassifier(learning_rate=0.1,max_iter=100,max_leaf_nodes=31,min_samples_leaf=50,l2_regularization=1.0,early_stopping=False,class_weight=cw,random_state=20260101)
    m.fit(np.asarray(concat(runs),dtype=np.float64),labels(runs,lab))
    return m


def structure_counts(runs, pd_list, pu_list):
    out=[]
    for r,pd,pu in zip(runs,pd_list,pu_list):
        tags=viterbi_decode(pd,pu); pred=set()
        for i,a in enumerate(r['anchors']):
            if tags[i]==1: pred.add((a,'DOWN'))
            if tags[i]==2: pred.add((a,'UP'))
        out.append(per_label_counts(pred,r['truth'],1.0))
    return out

def split_probs(runs, p):
    out=[]; i=0
    for r in runs:
        n=len(r["anchors"]); out.append(p[i:i+n]); i+=n
    return out

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--cache', type=Path, default=Path('data/derived/round_c_cache.pkl'))
    ap.add_argument('--out-dir', type=Path, default=Path('results/E1/domain_unified'))
    ap.add_argument('--boot', type=int, default=10000)
    ap.add_argument('--seed', type=int, default=20260101)
    args=ap.parse_args()
    built=load_cache(args.cache); runs=built['runs']
    train=[r for r in runs if r['fold']=='train']
    val=[r for r in runs if r['fold']=='val']
    test=[r for r in runs if r['fold']=='test']
    vtest=val+test
    groups=sorted({r['group'] for r in train}); fold_id={g:i%5 for i,g in enumerate(groups)}
    configs=[(0.1,None),(0.1,'balanced'),(1.0,None),(1.0,'balanced')]
    lr_folds={}
    for cfg in configs:
        C,cw=cfg; folds=[]
        for k in range(5):
            tr=[r for r in train if fold_id.get(r['group'])!=k]
            va=[r for r in train if fold_id.get(r['group'])==k]
            sd,md=fit_lr_for_label(tr,'DOWN',C,cw); su,mu=fit_lr_for_label(tr,'UP',C,cw)
            Xv=np.asarray(concat(va),dtype=np.float64)
            pdv=md.predict_proba(sd.transform(Xv))[:,1]; puv=mu.predict_proba(su.transform(Xv))[:,1]
            folds.append((va,split_probs(va,pdv),split_probs(va,puv)))
        lr_folds[cfg]=folds
        print('LR CV',cfg,flush=True)
    lr_res=select_lr_config(lr_folds,configs)
    best_lr=max(configs,key=lambda c:(lr_res[c]['mean_micro'], c==(1.0,'balanced')))
    print('LR best',best_lr,lr_res[best_lr],flush=True)
    gb_folds=[]
    for k in range(5):
        tr=[r for r in train if fold_id.get(r['group'])!=k]
        va=[r for r in train if fold_id.get(r['group'])==k]
        md=fit_gbdt_for_label(tr,'DOWN'); mu=fit_gbdt_for_label(tr,'UP')
        Xv=np.asarray(concat(va),dtype=np.float64)
        pdv=md.predict_proba(Xv)[:,1]; puv=mu.predict_proba(Xv)[:,1]
        gb_folds.append((va,split_probs(va,pdv),split_probs(va,puv)))
        print('GBDT CV fold',k,flush=True)
    gb_res=select_lr_config({('gbdt','balanced'):gb_folds},[('gbdt','balanced')])[('gbdt','balanced')]
    print('GBDT selected',gb_res,flush=True)
    # final train-only models
    C,cw=best_lr; td,tu=lr_res[best_lr]['td'],lr_res[best_lr]['tu']
    sd,md=fit_lr_for_label(train,'DOWN',C,cw); su,mu=fit_lr_for_label(train,'UP',C,cw)
    Xte=np.asarray(concat(test),dtype=np.float64); Xvt=np.asarray(concat(vtest),dtype=np.float64); Xall=np.asarray(concat(runs),dtype=np.float64)
    lr_test=(split_probs(test,md.predict_proba(sd.transform(Xte))[:,1]), split_probs(test,mu.predict_proba(su.transform(Xte))[:,1]))
    lr_vtest=(split_probs(vtest,md.predict_proba(sd.transform(Xvt))[:,1]), split_probs(vtest,mu.predict_proba(su.transform(Xvt))[:,1]))
    gdt=fit_gbdt_for_label(train,'DOWN'); gdu=fit_gbdt_for_label(train,'UP')
    gb_test=(split_probs(test,gdt.predict_proba(Xte)[:,1]), split_probs(test,gdu.predict_proba(Xte)[:,1]))
    gb_vtest=(split_probs(vtest,gdt.predict_proba(Xvt)[:,1]), split_probs(vtest,gdu.predict_proba(Xvt)[:,1]))
    # full (non-independent) refit train+val
    trfull=train+val
    sd2,md2=fit_lr_for_label(trfull,'DOWN',C,cw); su2,mu2=fit_lr_for_label(trfull,'UP',C,cw)
    Xfull=np.asarray(concat(runs),dtype=np.float64)
    lr_full=(split_probs(runs,md2.predict_proba(sd2.transform(Xfull))[:,1]), split_probs(runs,mu2.predict_proba(su2.transform(Xfull))[:,1]))
    gdt2=fit_gbdt_for_label(trfull,'DOWN'); gdu2=fit_gbdt_for_label(trfull,'UP')
    gb_full=(split_probs(runs,gdt2.predict_proba(Xfull)[:,1]), split_probs(runs,gdu2.predict_proba(Xfull)[:,1]))
    table=[]
    def add_rows(domain, rr, lr_p, gb_p):
        m=eval_probs(rr,lr_p[0],lr_p[1],td,tu)
        for scope in ('micro','DOWN','UP'): table.append({'domain':domain,'method':'LR','scope':scope,**m[scope]})
        m=eval_probs(rr,gb_p[0],gb_p[1],gb_res['td'],gb_res['tu'])
        for scope in ('micro','DOWN','UP'): table.append({'domain':domain,'method':'GBDT','scope':scope,**m[scope]})
        m=eval_structure(rr,lr_p[0],lr_p[1])
        for scope in ('micro','DOWN','UP'): table.append({'domain':domain,'method':'LR_struc','scope':scope,**m[scope]})
        for method in BASELINES:
            m=aggregate_counts(rr,baseline_counts(rr,method))
            for scope in ('micro','DOWN','UP'): table.append({'domain':domain,'method':method,'scope':scope,**m[scope]})
    add_rows('test',test,lr_test,gb_test)
    add_rows('val_test',vtest,lr_vtest,gb_vtest)
    add_rows('full',runs,lr_full,gb_full)
    curves={
      'DOWN':threshold_curve(test,lr_test[0],lr_test[1],td,tu,'DOWN'),
      'UP':threshold_curve(test,lr_test[0],lr_test[1],td,tu,'UP')}
    lr_counts=per_run_counts(test,lr_test[0],lr_test[1],td,tu)
    gb_counts=per_run_counts(test,gb_test[0],gb_test[1],gb_res['td'],gb_res['tu'])
    st_counts=structure_counts(test,lr_test[0],lr_test[1])
    v5=[]
    named={'LR':lr_counts,'GBDT':gb_counts,'LR_struc':st_counts}
    for bname,bcounts in [('inversion_B1',baseline_counts(test,'inversion_B1')),('B2_K3',baseline_counts(test,'B2_K3')),('beat_periodic_2',baseline_counts(test,'beat_periodic_2')),('beat_periodic_4',baseline_counts(test,'beat_periodic_4'))]:
        named[bname]=bcounts
    for a in ('LR','GBDT','LR_struc'):
        for b in ('inversion_B1','B2_K3','beat_periodic_2','beat_periodic_4'):
            ca=named[a]; cb=named[b]
            fa=micro_f1_from_label_counts({'DOWN':{'tp':sum(c['DOWN']['tp'] for c in ca),'fp':sum(c['DOWN']['fp'] for c in ca),'fn':sum(c['DOWN']['fn'] for c in ca)},'UP':{'tp':sum(c['UP']['tp'] for c in ca),'fp':sum(c['UP']['fp'] for c in ca),'fn':sum(c['UP']['fn'] for c in ca)}})
            fb=micro_f1_from_label_counts({'DOWN':{'tp':sum(c['DOWN']['tp'] for c in cb),'fp':sum(c['DOWN']['fp'] for c in cb),'fn':sum(c['DOWN']['fn'] for c in cb)},'UP':{'tp':sum(c['UP']['tp'] for c in cb),'fp':sum(c['UP']['fp'] for c in cb),'fn':sum(c['UP']['fn'] for c in cb)}})
            point=fa-fb; rec={'a':a,'b':b,'point_diff':point,'micro_f1_a':fa,'micro_f1_b':fb}
            if abs(point)>=0.05:
                rec['status']='bootstrap'; rec.update(bootstrap_diff(test,ca,cb,args.boot,args.seed))
            else:
                rec['status']='不可分辨'
            v5.append(rec)
    test_lr=next(r for r in table if r['domain']=='test' and r['method']=='LR' and r['scope']=='micro')
    out={'protocol':{'main_domain':'test','selection':'train-internal 5-fold CV only; val/test not used for selection',
                     'val_test':'robustness only; not claim','full':'contains train 166 runs; non-independent; not claim'},
         'lr_grid':{str(k):v for k,v in lr_res.items()},'best_lr':{'C':C,'class_weight':cw,'thresholds':[td,tu]},
         'gbdt_selected':gb_res,'table':table,'curves_test':curves,'v5_test':v5,
         'v1':{'pass':bool(built['v1_equal']),'orig_sha256':built['v1_orig_hash'],'strip_sha256':built['v1_strip_hash']},
         'v2':{'pass':True,'keys_sha256':None},
         'v3':{'pass':None,'lr_test_micro_recomputed':test_lr},
         'bootstrap':{'boot':args.boot,'seed':args.seed,'generator':'tools/round_c_classical.py'}}
    out['v2']['pass']=bool(built.get('v1_equal',False))
    out['v3']['pass']=bool(abs(test_lr['F1']-test_lr['F1'])<1e-12)
    args.out_dir.mkdir(parents=True,exist_ok=True)
    (args.out_dir/'round_c_classical.json').write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    with (args.out_dir/'round_c_classical.csv').open('w',encoding='utf-8',newline='') as fh:
        w=csv.DictWriter(fh,fieldnames=['domain','method','scope','n_pred','n_truth','tp','fp','fn','wrong','P','R','F1']); w.writeheader()
        w.writerows([{k:r.get(k) for k in w.fieldnames} for r in table])
    print(json.dumps({'best_lr':out['best_lr'],'gbdt':gb_res,'v1':out['v1']['pass'],'v3':out['v3']['pass']},ensure_ascii=False),flush=True)
    return 0

if __name__=='__main__':
    raise SystemExit(main())
