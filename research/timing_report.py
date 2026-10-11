import pickle, numpy as np, pandas as pd
D = pickle.load(open("timing.pkl","rb")).reset_index()
D["tier"] = np.where(D.atr_pct>=0.04,"Double","Single")
D["period"] = np.where(D.date<"2022-01-01","early","late")
def stat(g, res, pnl):
    g = g[g[res].notna()]
    return len(g), round((g[res]==1).mean()*100,1), round((g[res]==-1).mean()*100,1), round(g[pnl].mean()*100,2)
names = {0:"Mon",1:"Tue",2:"Wed",3:"Thu",4:"Fri"}
for tier,(res,pnl,reso,pnlo) in {"Double":("res_d","pnl_d","res_do","pnl_do"),"Single":("res_s","pnl_s","res_so","pnl_so")}.items():
    G = D[D.tier==tier]
    print("\n==",tier,"close entry by weekday (signal and entry same day)")
    for d in range(5):
        print(names[d], stat(G[G.dow==d],res,pnl))
    F = G[G.lastofweek]
    print("Friday close (weekly last day):", stat(F,res,pnl))
    print("Monday open after that Friday signal:", stat(F,reso,pnlo))
    for p in ("early","late"):
        print(" ",p,"Fri close",stat(F[F.period==p],res,pnl),"| Mon open",stat(F[F.period==p],reso,pnlo))
