import json, pandas as pd, numpy as np
import screener as S
bars,uni=S.load()
H=S.HORIZON
def outcomes(df, ind, tgt):
    h=df["h"].values; l=df["l"].values; c=df["c"].values
    n=len(c); res=np.full(n,np.nan); 
    stop_all=np.minimum(np.maximum(ind["low10"].values*0.995, c-2*ind["atr"].values), c*0.97)
    for t in range(n-H):
        st=stop_all[t]; tg=c[t]*(1+tgt)
        if not np.isfinite(st): continue
        out=0.0
        for k in range(1,H+1):
            if l[t+k]<=st: out=-1; break      # stop first (conservative on same day)
            if h[t+k]>=tg: out=1; break
        res[t]=out
    return res
rows=[]
for s,r in bars.items():
    if len(r)<S.WARMUP+20: continue
    df=S.frame(r); ind=S.indicators(df)
    ind["win10"]=outcomes(df,ind,.10); ind["win20"]=outcomes(df,ind,.20)
    ind["win8"]=outcomes(df,ind,.08)
    ind["sym"]=s
    sub=ind[ind.index.weekday==4].copy()
    sub["pos"]=[ind.index.get_loc(d) for d in sub.index]
    sub=sub[(sub.pos>=S.WARMUP)&(sub.pos+H<len(ind))]
    rows.append(sub)
df=pd.concat(rows)
df=df.dropna(subset=["sma150","atr_pct","range40","rsi","single_rate","win10"])
df=df[df.apply(S.eligible,axis=1)]
df["rs"]=df.groupby(level=0)["ret63"].rank(pct=True)
df["vr"]=df.vol5/df.vol50
df.to_pickle("explore2.pkl")
print(len(df))
for t in ("win8","win10","win20"):
    print(t,"target before stop:",(df[t]==1).mean().round(3),"stopped:",(df[t]==-1).mean().round(3))
for col in ["atr_pct","dist_high","rs","ret21","above50","rsi","range10","vr","updown","single_rate","double_rate","slope50"]:
    q=pd.qcut(df[col],5,duplicates="drop")
    g=df.groupby(q,observed=True).agg(n=("c","size"),w8=("win8",lambda x:(x==1).mean()),w10=("win10",lambda x:(x==1).mean()),w20=("win20",lambda x:(x==1).mean()))
    print("\n",col); print(g.round(3).to_string())
