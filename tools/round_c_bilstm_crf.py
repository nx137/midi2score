#!/usr/bin/env python
"""Round C BiLSTM-CRF (B4) on canonical anchor sequences."""
from __future__ import annotations
import argparse, csv, json, pickle, random, subprocess, sys, time
from pathlib import Path
import numpy as np
import torch
import torch.nn as nn
sys.path.insert(0, str(Path(__file__).resolve().parent))
from b2_perlabel_bootstrap import per_label_counts
from round_b_lr import bootstrap_diff, micro_f1_from_label_counts

TAGS = 3  # none, DOWN, UP
TAG_NAMES = {0: "NONE", 1: "DOWN", 2: "UP"}
NEG = -1e18


def load_cache(path):
    with Path(path).open('rb') as fh:
        return pickle.load(fh)


def tagseq(r):
    y = np.zeros(len(r['anchors']), dtype=np.int64)
    y[r['y_DOWN'].astype(bool)] = 1
    y[r['y_UP'].astype(bool)] = 2
    return y


def fit_scaler(runs):
    X = np.concatenate([r['X'] for r in runs], axis=0).astype(np.float64)
    mean = X.mean(axis=0); std = X.std(axis=0); std[std < 1e-8] = 1.0
    return mean, std


def scale(r, mean, std):
    return ((r['X'].astype(np.float64) - mean) / std).astype(np.float32)


class BiLSTMCRF(nn.Module):
    def __init__(self, input_dim=53, hidden=32):
        super().__init__()
        self.lstm = nn.LSTM(input_dim, hidden, num_layers=1, bidirectional=True, batch_first=True)
        self.emission = nn.Linear(2 * hidden, TAGS)
        self.trans = nn.Parameter(torch.zeros(TAGS, TAGS))
        self.start = nn.Parameter(torch.zeros(TAGS))
        self.end = nn.Parameter(torch.zeros(TAGS))
    def emissions(self, x):
        h, _ = self.lstm(x)
        return self.emission(h)


def logsumexp(x, dim):
    m = torch.max(x, dim=dim, keepdim=True).values
    return m.squeeze(dim) + torch.log(torch.sum(torch.exp(x - m), dim=dim))


def crf_nll(em, tags, mask, trans, start, end, class_weight=None):
    B, T, K = em.shape
    if class_weight is not None:
        em = em + torch.log(class_weight).view(1, 1, -1)
    score = start[tags[:, 0]] + em[:, 0, tags[:, 0]]
    for t in range(1, T):
        m = mask[:, t].float()
        score = score + m * (em[:, t, tags[:, t]] + trans[tags[:, t-1], tags[:, t]])
    lengths = mask.sum(dim=1).long()
    last = tags[torch.arange(B), lengths - 1]
    score = score + end[last]
    alpha = start.unsqueeze(0) + em[:, 0]
    for t in range(1, T):
        nxt = torch.logsumexp(alpha.unsqueeze(2) + trans.unsqueeze(0), dim=1) + em[:, t]
        alpha = torch.where(mask[:, t].unsqueeze(1), nxt, alpha)
    logZ = torch.logsumexp(alpha + end.unsqueeze(0), dim=1)
    return (logZ - score).mean()


@torch.no_grad()
def viterbi(model, x, mask):
    em = model.emissions(x.unsqueeze(0))[0]
    B, T, K = 1, em.shape[0], TAGS
    score = model.start + em[0]
    back = torch.zeros((T, K), dtype=torch.long)
    for t in range(1, T):
        if not bool(mask[t]):
            back[t] = torch.arange(K); continue
        vals = score.unsqueeze(1) + model.trans
        best, idx = vals.max(dim=0)
        score = best + em[t]
        back[t] = idx
    last_len = int(mask.sum().item()) - 1
    s = int(torch.argmax(score + model.end)); tags = [s]
    for t in range(T - 1, 0, -1):
        s = int(back[t, s]); tags.append(s)
    tags.reverse()
    return tags[:last_len + 1]

def make_chunks(runs, mean, std, chunk=256):
    out=[]
    for ri,r in enumerate(runs):
        x=scale(r,mean,std); y=tagseq(r)
        if chunk <= 0:
            out.append((ri,0,len(y),x,y)); continue
        for s in range(0,len(y),chunk):
            e=min(len(y),s+chunk)
            out.append((ri,s,e,x[s:e],y[s:e]))
    return out


def collate(batch):
    maxlen=max(x.shape[0] for _,_,_,x,_ in batch)
    B=len(batch); X=torch.zeros((B,maxlen,53),dtype=torch.float32); Y=torch.zeros((B,maxlen),dtype=torch.long); M=torch.zeros((B,maxlen),dtype=torch.bool)
    for i,(_,_,_,x,y) in enumerate(batch):
        n=x.shape[0]; X[i,:n]=torch.from_numpy(x); Y[i,:n]=torch.from_numpy(y); M[i,:n]=True
    return X,Y,M


def train_model(runs, epochs=4, hidden=32, chunk=256, batch_size=32, lr=1e-3, max_train_runs=0, seed=20260101, val_runs=None, patience=10, report_runs=None, use_class_weight=True):
    random.seed(seed); np.random.seed(seed); torch.manual_seed(seed)
    mean,std=fit_scaler(runs)
    chunks=make_chunks(runs,mean,std,chunk)
    if max_train_runs:
        keep=set(range(min(max_train_runs,len(runs)))); chunks=[c for c in chunks if c[0] in keep]
    counts=np.bincount(np.concatenate([c[4] for c in chunks]),minlength=TAGS).astype(np.float64)
    cw=None if not use_class_weight else torch.tensor(np.clip(counts.sum()/(TAGS*np.maximum(counts,1)),1.0,5.0),dtype=torch.float32)
    model=BiLSTMCRF(hidden=hidden)
    opt=torch.optim.AdamW(model.parameters(),lr=lr,weight_decay=1e-4)
    order=list(range(len(chunks)))
    best=-1.0; best_state=None; best_epoch=0; bad=0; history=[]
    for ep in range(epochs):
        model.train(); random.shuffle(order); total=0.0; nb=0
        for s in range(0,len(order),batch_size):
            ids=order[s:s+batch_size]; batch=[chunks[i] for i in ids]
            X,Y,M=collate(batch); opt.zero_grad()
            em=model.emissions(X); loss=crf_nll(em,Y,M,model.trans,model.start,model.end,None if cw is None else torch.log(cw))
            loss.backward(); torch.nn.utils.clip_grad_norm_(model.parameters(),5.0); opt.step()
            total+=float(loss.detach()); nb+=1
        print(f'epoch {ep+1}/{epochs} loss={total/max(nb,1):.4f}',flush=True)
        if val_runs is not None:
            vm,_=eval_model(model,mean,std,val_runs)
            vmetric=vm['micro']['F1']
            record={'epoch':ep+1,'inner_val_micro':vmetric,'inner_val_macro':vm['macro']['F1']}
            if report_runs is not None:
                rm,_=eval_model(model,mean,std,report_runs)
                record['val_micro']=rm['micro']['F1']; record['val_macro']=rm['macro']['F1']
            history.append(record)
            print(f'  inner_val_micro={vmetric:.4f} inner_val_macro={vm["macro"]["F1"]:.4f}' + (f' val_micro={record["val_micro"]:.4f} val_macro={record["val_macro"]:.4f}' if report_runs is not None else ''),flush=True)
            if vmetric > best+1e-6:
                best=vmetric; best_epoch=ep+1; best_state={k:v.detach().clone() for k,v in model.state_dict().items()}; bad=0
            else:
                bad+=1
                if bad>=patience: break
    if best_state is not None:
        model.load_state_dict(best_state)
    return model,mean,std,history,best_epoch


@torch.no_grad()
def eval_model(model, mean, std, runs):
    parts={'DOWN':{'tp':0,'fp':0,'fn':0,'wrong':0,'n_pred':0,'n_truth':0},'UP':{'tp':0,'fp':0,'fn':0,'wrong':0,'n_pred':0,'n_truth':0}}
    none_tp=none_fp=none_fn=0
    per=[]
    for r in runs:
        x=torch.from_numpy(scale(r,mean,std)); mask=torch.ones(len(r['anchors']),dtype=torch.bool)
        tags=np.asarray(viterbi(model,x,mask),dtype=np.int64)
        true_tags=tagseq(r)
        none_tp += int(np.sum((tags==0) & (true_tags==0)))
        none_fp += int(np.sum((tags==0) & (true_tags!=0)))
        none_fn += int(np.sum((tags!=0) & (true_tags==0)))
        pred=set()
        for i,a in enumerate(r['anchors']):
            if tags[i]==1: pred.add((a,'DOWN'))
            if tags[i]==2: pred.add((a,'UP'))
        c=per_label_counts(pred,r['truth'],1.0); per.append(c)
        for lab in ('DOWN','UP'):
            for k in parts[lab]: parts[lab][k]+=c[lab][k]
    out={}
    for lab in ('DOWN','UP'):
        c=parts[lab]; p=c['tp']/c['n_pred'] if c['n_pred'] else 0.0; r=c['tp']/c['n_truth'] if c['n_truth'] else 0.0
        out[lab]={**c,'P':p,'R':r,'F1':2*p*r/(p+r) if p+r else 0.0}
    pn=none_tp/(none_tp+none_fp) if (none_tp+none_fp) else 0.0
    rn=none_tp/(none_tp+none_fn) if (none_tp+none_fn) else 0.0
    out['NONE']={'tp':none_tp,'fp':none_fp,'fn':none_fn,'n_pred':none_tp+none_fp,'n_truth':none_tp+none_fn,
                 'P':pn,'R':rn,'F1':2*pn*rn/(pn+rn) if (pn+rn) else 0.0}
    tp=out['DOWN']['tp']+out['UP']['tp']; fp=out['DOWN']['fp']+out['UP']['fp']; fn=out['DOWN']['fn']+out['UP']['fn']
    n_pred=out['DOWN']['n_pred']+out['UP']['n_pred']; n_truth=out['DOWN']['n_truth']+out['UP']['n_truth']
    p=tp/n_pred if n_pred else 0.0; r=tp/n_truth if n_truth else 0.0
    out['micro']={'tp':tp,'fp':fp,'fn':fn,'wrong':out['DOWN']['wrong']+out['UP']['wrong'],'n_pred':n_pred,'n_truth':n_truth,'P':p,'R':r,'F1':2*p*r/(p+r) if p+r else 0.0}
    out['macro']={'F1':float(np.mean([out['NONE']['F1'],out['DOWN']['F1'],out['UP']['F1']]))}
    return out,per


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--cache', type=Path, default=Path('data/derived/round_c_cache.pkl'))
    ap.add_argument('--out-dir', type=Path, default=Path('results/E1/domain_unified'))
    ap.add_argument('--epochs', type=int, default=200)
    ap.add_argument('--hidden', type=int, default=32)
    ap.add_argument('--chunk', type=int, default=256)
    ap.add_argument('--batch-size', type=int, default=32)
    ap.add_argument('--lr', type=float, default=1e-3)
    ap.add_argument('--seed', type=int, default=20260101)
    ap.add_argument('--disable-class-weight', action='store_true')
    ap.add_argument('--max-train-runs', type=int, default=0)
    args=ap.parse_args()
    built=load_cache(args.cache); runs=built['runs']
    train=[r for r in runs if r['fold']=='train']; val=[r for r in runs if r['fold']=='val']; test=[r for r in runs if r['fold']=='test']; vtest=val+test
    inner_groups=sorted({r['group'] for r in train})[::5]
    inner_val=[r for r in train if r['group'] in inner_groups]
    inner_train=[r for r in train if r['group'] not in inner_groups]
    t0=time.time()
    model,mean,std,history,best_epoch=train_model(inner_train,epochs=args.epochs,hidden=args.hidden,chunk=args.chunk,batch_size=args.batch_size,lr=args.lr,max_train_runs=args.max_train_runs,seed=args.seed,val_runs=inner_val,report_runs=val,use_class_weight=not args.disable_class_weight)
    wall=time.time()-t0
    val_sum,val_counts=eval_model(model,mean,std,val)
    test_sum,test_counts=eval_model(model,mean,std,test)
    vt_sum,vt_counts=eval_model(model,mean,std,vtest)
    full_sum,full_counts=eval_model(model,mean,std,runs)
    def per_score_micro(rs, per):
        agg={}
        for r,c in zip(rs,per):
            a=agg.setdefault(r['score'],{'tp':0,'fp':0,'fn':0})
            for lab in ('DOWN','UP'):
                a['tp']+=c[lab]['tp']; a['fp']+=c[lab]['fp']; a['fn']+=c[lab]['fn']
        out={}
        for sc,a in agg.items():
            p=a['tp']/(a['tp']+a['fp']) if (a['tp']+a['fp']) else 0.0
            rr=a['tp']/(a['tp']+a['fn']) if (a['tp']+a['fn']) else 0.0
            out[sc]=2*p*rr/(p+rr) if (p+rr) else 0.0
        return out
    commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
    config={'hidden':args.hidden,'layers':1,'dropout':0.0,'lr':args.lr,'batch':args.batch_size,'epochs':args.epochs,
            'seed':args.seed,'optimizer':'AdamW','weight_decay':1e-4,'class_weight':('none' if args.disable_class_weight else 'balanced_clipped'),
            'early_stop':'inner_val_micro_f1 patience=10','chunk':args.chunk,'clip_grad_norm':5.0,'git_commit':commit}
    model_dir=args.out_dir/'model1'; model_dir.mkdir(parents=True,exist_ok=True)
    torch.save({'state_dict':model.state_dict(),'mean':mean,'std':std,'config':config},model_dir/'best_model.pt')
    (model_dir/'config.json').write_text(json.dumps(config,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    table=[]
    for dom,summ in (('val',val_sum),('test',test_sum),('val_test',vt_sum),('full',full_sum)):
        for scope in ('NONE','DOWN','UP','micro','macro'):
            table.append({'domain':dom,'method':'BiLSTM_CRF','scope':scope,**summ[scope]})
    out={'config':config,'history':history,'best_epoch':best_epoch,'epochs_run':len(history),'wall_clock_sec':wall,
         'table':table,'per_score_micro_val':per_score_micro(val,val_counts),'per_score_micro_test':per_score_micro(test,test_counts),
         'val':val_sum,'test':test_sum,'val_test':vt_sum,'full':full_sum,
         'v1':{'pass':bool(built['v1_equal']),'orig_sha256':built['v1_orig_hash'],'strip_sha256':built['v1_strip_hash']}}
    (args.out_dir/'round_c_bilstm_crf.json').write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    sweep=args.out_dir/'round_d_sweep.csv'
    fields=['stage','hidden','layers','dropout','lr','batch','seed','epochs_run','best_epoch','val_macro_f1','val_change_f1','f1_NONE','f1_DOWN','f1_UP','f1_CHANGE','wall_clock_sec','git_commit']
    exists=sweep.exists()
    with sweep.open('w' if not exists else 'a',encoding='utf-8',newline='') as fh:
        w=csv.DictWriter(fh,fieldnames=fields)
        if not exists: w.writeheader()
        w.writerow({'stage':'model1','hidden':args.hidden,'layers':1,'dropout':0.0,'lr':args.lr,'batch':args.batch_size,'seed':args.seed,
                    'epochs_run':len(history),'best_epoch':best_epoch,'val_macro_f1':val_sum['macro']['F1'],'val_change_f1':'NA',
                    'f1_NONE':val_sum['NONE']['F1'],'f1_DOWN':val_sum['DOWN']['F1'],'f1_UP':val_sum['UP']['F1'],'f1_CHANGE':'NA',
                    'wall_clock_sec':wall,'git_commit':commit})
    print(json.dumps({'test_micro':test_sum['micro']['F1'],'test_macro':test_sum['macro']['F1'],'val_micro':val_sum['micro']['F1'],'val_macro':val_sum['macro']['F1'],'epochs_run':len(history),'best_epoch':best_epoch,'wall_clock_sec':wall},ensure_ascii=False),flush=True)
    return 0

if __name__=='__main__':
    raise SystemExit(main())
