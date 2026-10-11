import pickle, warnings, numpy as np, pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
warnings.filterwarnings("ignore")
P = pickle.load(open("panel.pkl", "rb"))
P = P.dropna(subset=["sma150", "atr_pct", "single_rate", "double_rate", "stage", "sec_stage", "range40", "rsi", "slope50", "slope150", "sec_rs", "sec_slope", "spy_up"])
P = P[(P.nwin >= 200) & (P.c >= 10) & (P.dvol20 >= 20e6) & (P.date >= "2018-01-01")].copy()
P["vol_ratio"] = P.vol5 / P.vol50
P["ldv"] = np.log(P.dvol20)
P["range_ratio"] = P.range10 / P.range40
for k in (1, 2, 3, 4): P[f"st{k}"] = (P.stage == k).astype(int); P[f"sst{k}"] = (P.sec_stage == k).astype(int)
P["pull"] = ((P.c > P.sma50) & (P.slope50 > 0) & ((P.c / P.ema20 - 1).abs() < .035) & P.rsi.between(38, 58)).astype(int)
P["base"] = ((P.dist_high > -.12) & (P.range10 < .075) & (P.range_ratio < .6)).astype(int)
P["brk"] = ((P.c > P.hi20) & (P.vol_ratio > 1.2) & (P.above50 < .2)).astype(int)
P["year"] = P.date.dt.year
CORE = ["atr_pct", "single_rate", "double_rate", "rs", "ret21", "ret63", "above50", "above150", "dist_high", "slope50", "slope150", "range10", "range_ratio", "rsi", "vol_ratio", "stop_pct", "ldv"]
STAGE = ["st1", "st2", "st3", "st4", "fresh2"]
SECT = ["sst2", "sst3", "sst4", "sec_rs", "sec_slope"]
REG = ["spy_up"]
SETUP = ["pull", "base", "brk"]
SETS = {"core": CORE, "core+setup": CORE + SETUP, "core+stage": CORE + STAGE, "core+sector": CORE + SECT, "core+regime": CORE + REG, "everything": CORE + SETUP + STAGE + SECT + REG}
D = P[(P.atr_pct >= .033) & (P.double_rate >= .15) & P.res_d.notna()].copy()
S = P[(P.atr_pct >= .022) & (P.atr_pct < .033) & (P.single_rate >= .30) & P.res_s.notna()].copy()

def walk(pool, r, p, feats, n=25):
    outs = []
    for Y in range(2020, 2027):
        tr = pool[pool.date < pd.Timestamp(Y, 1, 1) - pd.Timedelta(days=60)]
        te = pool[pool.year == Y]
        if len(te) == 0: continue
        m = HistGradientBoostingClassifier(max_iter=120, learning_rate=0.05, max_depth=3, min_samples_leaf=300, l2_regularization=5.0, random_state=0)
        m.fit(tr[feats], (tr[r] == 1).astype(int))
        te = te.assign(pr=m.predict_proba(te[feats])[:, 1])
        outs.append(te)
    allp = pd.concat(outs)
    top = allp.sort_values(["date", "pr"], ascending=[True, False]).groupby("date").head(n)
    return allp, top

def summ(df, r, p):
    return dict(n=len(df), win=round((df[r] == 1).mean() * 100, 1), stop=round((df[r] == -1).mean() * 100, 1), pnl=round(df[p].mean() * 100, 2))

for name, pool, r, p in (("DOUBLE", D, "res_d", "pnl_d"), ("SINGLE", S, "res_s", "pnl_s")):
    print("\n=====", name, "walk forward 2020 to 2026, top 25 per week")
    rows = []
    for k, f in SETS.items():
        allp, top = walk(pool, r, p, f)
        row = dict(model=k, **{("pick_" + a): b for a, b in summ(top, r, p).items()})
        row["pool_win"] = summ(allp, r, p)["win"]; row["pool_pnl"] = summ(allp, r, p)["pnl"]
        # by period halves
        for lab, sub in (("2020 to 2022", top[top.year <= 2022]), ("2023 to 2026", top[top.year >= 2023])):
            row["win " + lab] = summ(sub, r, p)["win"]; row["pnl " + lab] = summ(sub, r, p)["pnl"]
        rows.append(row)
    print(pd.DataFrame(rows).to_string(index=False))

# interpretable view: logistic on standardized features, trained on everything, DOUBLE and SINGLE
for name, pool, r in (("DOUBLE", D, "res_d"), ("SINGLE", S, "res_s")):
    f = CORE + STAGE + SECT + REG + SETUP
    X = StandardScaler().fit_transform(pool[f]); y = (pool[r] == 1).astype(int)
    lr = LogisticRegression(C=0.2, max_iter=500).fit(X, y)
    co = pd.Series(lr.coef_[0], index=f).sort_values(key=abs, ascending=False)
    print("\n== standardized logistic coefficients", name); print(co.round(3).to_string())
