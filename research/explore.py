import json, pandas as pd, numpy as np
import screener as S
bars,uni=S.load()
inds={s:S.indicators(S.frame(r)) for s,r in bars.items() if len(r)>=S.WARMUP+20}
dates=sorted(set().union(*[set(i.index) for i in inds.values()]))
rows=[]
for d in [x for x in dates if x.weekday()==4]:
    for s,ind in inds.items():
        if d not in ind.index: continue
        pos=ind.index.get_loc(d)
        if pos<S.WARMUP or pos+S.HORIZON>=len(ind): continue
        r=ind.loc[d]
        if r[["sma150","atr_pct","range40","rsi","single_rate"]].isna().any(): continue
        if not S.eligible(r): continue
        sc,nm=S.setup_scores(r)
        rows.append(dict(date=d,sym=s,fwd=r.fwd_max,atr=r.atr_pct,dh=r.dist_high,ret63=r.ret63,ret21=r.ret21,
          a50=r.above50,sl=r.slope50,rsi=r.rsi,r10=r.range10,r40=r.range40,vr=r.vol5/r.vol50,ud=r.updown,
          sr=r.single_rate,dr=r.double_rate,setup=nm,sscore=sc,
          tr=int(r.c>r.sma50>r.sma150)))
df=pd.DataFrame(rows)
df["rs"]=df.groupby("date")["ret63"].rank(pct=True)
df["s10"]=df.fwd>=.10; df["d20"]=df.fwd>=.20; df["s8"]=df.fwd>=.08
df.to_pickle("explore.pkl")
print(len(df), df.s10.mean(), df.d20.mean())
for col in ["atr","dh","rs","ret21","a50","rsi","r10","vr","ud","sr","dr","sl"]:
    q=pd.qcut(df[col],5,duplicates="drop")
    g=df.groupby(q,observed=True).agg(n=("fwd","size"),s10=("s10","mean"),d20=("d20","mean"),med=("fwd","median"))
    print("\n",col); print(g.round(3).to_string())
print(df.groupby("setup").agg(n=("fwd","size"),s10=("s10","mean"),d20=("d20","mean"),med=("fwd","median")).round(3))
print(df.groupby("tr").agg(n=("fwd","size"),s10=("s10","mean"),d20=("d20","mean")).round(3))
