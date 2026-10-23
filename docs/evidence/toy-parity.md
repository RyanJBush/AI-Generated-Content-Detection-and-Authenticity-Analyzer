# Toy parity evidence: v0.3 §3.1 formula vs pinned upstream Binoculars

Run by Claude (separate chat sandbox), 2026-10-23T22:30Z. Environment: python 3.12.3 | torch 2.14.1+cpu, Linux CPU.
Upstream file: raw.githubusercontent.com/ahans30/Binoculars/c8ae2f90d50ee696418bc71d8d9e5020e5f9d7b8/binoculars/metrics.py (SHA-256 863876e772893f03a3d2a6b82c4589123751c7b77f2499c2a8cd92159a2d7061).
Scope: fp32 CPU toy logits only. Does not establish bf16/fp16/GPU parity or Qwen behavior. This is upstream-parity evidence, not independent hand-computed validation.

## Script (toy.py)
```python
import torch, types, sys
sys.path.insert(0, "up"); import metrics as M
torch.manual_seed(0)
B_, T, V = 2, 6, 7
obs = torch.randn(B_, T, V) * 2; perf = torch.randn(B_, T, V) * 2
PAD = 6
ids = torch.tensor([[1,2,3,4,5,0],[2,3,1,4,PAD,PAD]])          # row 2 right-padded
am  = torch.tensor([[1,1,1,1,1,1],[1,1,1,1,0,0]])
enc = types.SimpleNamespace(input_ids=ids, attention_mask=am)

def spec(obs, perf, ids, am, final=True):
    O = obs.float().log_softmax(-1); P = perf.float().log_softmax(-1)
    m = am[:, :-1] * am[:, 1:]
    nll = (-(P[:, :-1].gather(-1, ids[:, 1:, None]).squeeze(-1)) * m).sum(1) / m.sum(1)
    d = am.clone() if final else torch.cat([am[:, 1:] * am[:, :-1], torch.zeros_like(am[:, :1])], 1)
    xe = ((O.exp() * -P).sum(-1) * d).sum(1) / d.sum(1)
    return nll, xe, nll / xe

ppl = torch.tensor(M.perplexity(enc, perf)); xppl = torch.tensor(M.entropy(obs, perf, enc, PAD))
nll, xe, b = spec(obs, perf, ids, am)
print("1 upstream vs spec  max|diff| NLL, XENT:", float((ppl-nll).abs().max()), float((xppl-xe).abs().max()))
print("2 matched-position variant changes B:", spec(obs, perf, ids, am, final=False)[2].tolist(), "vs", b.tolist())
print("3 swapped roles changes B:", spec(perf, obs, ids, am)[2].tolist())
# 4: real token equal to pad id inside text (pad==eos case), no padding
ids2 = torch.tensor([[1,2,PAD,4,5,0]]); am2 = torch.ones(1,6, dtype=torch.long)
enc2 = types.SimpleNamespace(input_ids=ids2, attention_mask=am2)
up_x = float(M.entropy(obs[:1], perf[:1], enc2, PAD)[0]); sp_x = float(spec(obs[:1], perf[:1], ids2, am2)[1][0])
print("4 in-text token == pad id: upstream XENT", round(up_x,6), "spec XENT", round(sp_x,6))
```

## Output
```
1 upstream vs spec  max|diff| NLL, XENT: 0.0 0.0
2 matched-position variant changes B: [0.7248329520225525, 1.0614306926727295] vs [0.7174583673477173, 1.0272923707962036]
3 swapped roles changes B: [0.7381558418273926, 1.066767930984497]
4 in-text token == pad id: upstream XENT 3.307884 spec XENT 3.317548
```

## Threshold-rule and AUROC-tie toy (thr.py)
```python
import numpy as np
def fit(r_h, a):
    H=len(r_h); 
    for c in sorted(set(r_h)):
        if (r_h > c).sum()/H <= a: return c
r_h = np.array([1,2,2,3,3,3,4,5,5,5], float)   # tied human dev scores (machine-positive r)
for a in (0.05, 0.10, 0.30):
    c = fit(r_h, a); print(f"alpha={a}: c={c}, achieved dev FPR={(r_h>c).mean():.2f}")
# length baseline under 512-token truncation: many exact ties
from sklearn.metrics import roc_auc_score
y=[0]*4+[1]*4; s=[511,511,511,300, 511,511,511,511]
print("AUROC with ties (sklearn, ties=0.5):", roc_auc_score(y,s))
```
```
alpha=0.05: c=5.0, achieved dev FPR=0.00
alpha=0.1: c=5.0, achieved dev FPR=0.00
alpha=0.3: c=4.0, achieved dev FPR=0.30
AUROC with ties (sklearn, ties=0.5): 0.625
```
