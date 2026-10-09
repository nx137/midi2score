#!/usr/bin/env python
"""Round C BiLSTM-CRF (B4) on canonical anchor sequences."""
from __future__ import annotations
import argparse, json, pickle, random, sys, time
from pathlib import Path
import numpy as np
import torch
import torch.nn as nn
sys.path.insert(0, str(Path(__file__).resolve().parent))
from b2_perlabel_bootstrap import per_label_counts
from round_b_lr import bootstrap_diff, micro_f1_from_label_counts

TAGS = 3  # none, DOWN, UP
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
    loss = (logZ - score)
    if class_weight is not None:
        w = class_weight[tags]
        w = w * mask.float()
        loss = (loss * w.sum(dim=1) / mask.float().sum(dim=1).clamp_min(1.0)).mean()
    else:
        loss = loss.mean()
    return loss


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


def train_model(runs, epochs=4, hidden=32, chunk=256, batch_size=32, lr=1e-3, max_train_runs=0, seed=20260101):
    random.seed(seed); np.random.seed(seed); torch.manual_seed(seed)
    mean,std=fit_scaler(runs)
    chunks=make_chunks(runs,mean,std,chunk)
    if max_train_runs:
        keep=set(range(min(max_train_runs,len(runs)))); chunks=[c for c in chunks if c[0] in keep]
    counts=np.bincount(np.concatenate([c[4] for c in chunks]),minlength=TAGS).astype(np.float64)
    cw=torch.tensor((counts.sum()/(TAGS*np.maximum(counts,1))),dtype=torch.float32)
    model=BiLSTMCRF(hidden=hidden)
    opt=torch.optim.AdamW(model.parameters(),lr=lr,weight_decay=1e-4)
    order=list(range(len(chunks)))
    for ep in range(epochs):
        random.shuffle(order); total=0.0; nb=0
        for s in range(0,len(order),batch_size):
            ids=order[s:s+batch_size]; batch=[chunks[i] for i in ids]
            X,Y,M=collate(batch); opt.zero_grad()
            em=model.emissions(X); loss=crf_nll(em,Y,M,model.trans,model.start,model.end,None)
            loss.backward(); torch.nn.utils.clip_grad_norm_(model.parameters(),5.0); opt.step()
            total+=float(loss.detach()); nb+=1
        print(f'epoch {ep+1}/{epochs} loss={total/max(nb,1):.4f}',flush=True)
    return model,mean,std


@torch.no_grad()
def eval_model(model, mean, std, runs):
    parts={'DOWN':{'tp':0,'fp':0,'fn':0,'wrong':0,'n_pred':0,'n_truth':0},'UP':{'tp':0,'fp':0,'fn':0,'wrong':0,'n_pred':0,'n_truth':0}}
    per=[]
    for r in runs:
        x=torch.from_numpy(scale(r,mean,std)); mask=torch.ones(len(r['anchors']),dtype=torch.bool)
        tags=viterbi(model,x,mask); pred=set()
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
    tp=out['DOWN']['tp']+out['UP']['tp']; fp=out['DOWN']['fp']+out['UP']['fp']; fn=out['DOWN']['fn']+out['UP']['fn']
    n_pred=out['DOWN']['n_pred']+out['UP']['n_pred']; n_truth=out['DOWN']['n_truth']+out['UP']['n_truth']
    p=tp/n_pred if n_pred else 0.0; r=tp/n_truth if n_truth else 0.0
    out['micro']={'tp':tp,'fp':fp,'fn':fn,'wrong':out['DOWN']['wrong']+out['UP']['wrong'],'n_pred':n_pred,'n_truth':n_truth,'P':p,'R':r,'F1':2*p*r/(p+r) if p+r else 0.0}
    return out,per

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--cache', type=Path, default=Path('data/derived/round_c_cache.pkl'))
    ap.add_argument('--out-dir', type=Path, default=Path('results/E1/domain_unified'))
    ap.add_argument('--epochs', type=int, default=4)
    ap.add_argument('--hidden', type=int, default=32)
    ap.add_argument('--chunk', type=int, default=256)
    ap.add_argument('--batch-size', type=int, default=32)
    ap.add_argument('--lr', type=float, default=1e-3)
    ap.add_argument('--max-train-runs', type=int, default=0)
    args=ap.parse_args()
    built=load_cache(args.cache); runs=built['runs']
    train=[r for r in runs if r['fold']=='train']; val=[r for r in runs if r['fold']=='val']; test=[r for r in runs if r['fold']=='test']; vtest=val+test
    t0=time.time(); model,mean,std=train_model(train,epochs=args.epochs,hidden=args.hidden,chunk=args.chunk,batch_size=args.batch_size,lr=args.lr,max_train_runs=args.max_train_runs)
    print('trained test model',round(time.time()-t0,1),'s',flush=True)
    test_sum,test_counts=eval_model(model,mean,std,test); vt_sum,vt_counts=eval_model(model,mean,std,vtest)
    model2,mean2,std2=train_model(train+val,epochs=args.epochs,hidden=args.hidden,chunk=args.chunk,batch_size=args.batch_size,lr=args.lr,max_train_runs=args.max_train_runs)
    full_sum,full_counts=eval_model(model2,mean2,std2,runs)
    table=[]
    for dom,summ in (('test',test_sum),('val_test',vt_sum),('full',full_sum)):
        for scope in ('micro','DOWN','UP'):
            table.append({'domain':dom,'method':'BiLSTM_CRF','scope':scope,**summ[scope]})
    out={'config':{'epochs':args.epochs,'hidden':args.hidden,'chunk':args.chunk,'batch_size':args.batch_size,'lr':args.lr,
                   'note':'BiLSTM-CRF sequence architecture fixed; test trained on train only; full retrained train+val and is non-independent'},
         'table':table,'test_counts':test_counts,'vtest_counts':vt_counts,'full_counts':full_counts,
         'v1':{'pass':bool(built['v1_equal']),'orig_sha256':built['v1_orig_hash'],'strip_sha256':built['v1_strip_hash']}}
    args.out_dir.mkdir(parents=True,exist_ok=True)
    (args.out_dir/'round_c_bilstm_crf.json').write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps({'test_micro':test_sum['micro']['F1'],'test_down':test_sum['DOWN']['F1'],'test_up':test_sum['UP']['F1'],'full_micro':full_sum['micro']['F1']},ensure_ascii=False),flush=True)
    return 0

if __name__=='__main__':
    raise SystemExit(main())
