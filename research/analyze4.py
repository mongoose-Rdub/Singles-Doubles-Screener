import pickle, warnings, numpy as np, pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
warnings.filterwarnings("ignore")
exec(open("analyze3.py").read().split("def walk")[0])   # reuse data prep and feature sets

def walk_pnl(pool, r, p, feats, n=25):
    outs = []
    for Y in range(2020, 2027):
        tr = pool[pool.date < pd.Timestamp(Y, 1, 1) - pd.Timedelta(days=60)]
        te = pool[pool.year == Y]
        m = HistGradientBoostingRegressor(max_iter=120, learning_rate=0.05, max_depth=3, min_samples_leaf=400, l2_regularization=10.0, random_state=0)
        # target: pnl in units of risk (R) so wide stops do not look attractive by construction
        y = tr[p] / tr.stop_pct
        m.fit(tr[feats], y.clip(-1.5, 6))
        outs.append(te.assign(pr=m.predict(te[feats])))
    allp = pd.concat(outs)
    top = allp.sort_values(["date", "pr"], ascending=[True, False]).groupby("date").head(n)
    return allp, top

def se_week(df, p):
    w = df.groupby("date")[p].mean()
    return w.mean() * 100, w.std() / np.sqrt(len(w)) * 100

for name, pool, r, p in (("DOUBLE", D, "res_d", "pnl_d"), ("SINGLE", S, "res_s", "pnl_s")):
    print("\n=====", name, "ranked on expected result in R units, walk forward 2020 to 2026")
    rows = []
    for k, f in SETS.items():
        allp, top = walk_pnl(pool, r, p, f)
        pm, ps = se_week(top, p); bm, bs = se_week(allp, p)
        top = top.assign(R=top[p] / top.stop_pct); allp = allp.assign(R=allp[p] / allp.stop_pct)
        rows.append(dict(model=k, pick_win=round((top[r] == 1).mean() * 100, 1), pick_pnl=round(pm, 2), pick_se=round(ps, 2), pool_win=round((allp[r] == 1).mean() * 100, 1),
                         pool_pnl=round(bm, 2), pool_se=round(bs, 2), pick_R=round(top.R.mean(), 3), pool_R=round(allp.R.mean(), 3),
                         avg_stop=round(top.stop_pct.mean() * 100, 1), pool_stop=round(allp.stop_pct.mean() * 100, 1),
                         h1_pnl=round(top[top.year <= 2022][p].mean() * 100, 2), h2_pnl=round(top[top.year >= 2023][p].mean() * 100, 2)))
    print(pd.DataFrame(rows).to_string(index=False))
