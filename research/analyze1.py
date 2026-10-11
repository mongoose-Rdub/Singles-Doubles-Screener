import pickle, numpy as np, pandas as pd
P = pickle.load(open("panel.pkl", "rb"))
P = P.dropna(subset=["sma150", "atr_pct", "single_rate", "double_rate", "stage", "sec_stage"])
P = P[(P.nwin >= 200) & (P.c >= 10) & (P.dvol20 >= 20e6)]
P["year"] = P.date.dt.year
P["period"] = np.where(P.date < "2022-01-01", "dev 2018 to 2021", "test 2022 to 2026")
P = P[P.date >= "2018-01-01"]
print("rows", len(P), P.date.min().date(), P.date.max().date())
print("stage mix", P.stage.value_counts(normalize=True).round(3).to_dict())
print("sec stage mix", P.sec_stage.value_counts(normalize=True).round(3).to_dict())
print("spy up share", P.drop_duplicates("date").spy_up.mean().round(3))
dbl = P[(P.atr_pct >= 0.033) & (P.double_rate >= 0.15) & P.res_d.notna()].copy()
sgl = P[(P.atr_pct >= 0.022) & (P.atr_pct < 0.033) & (P.single_rate >= 0.30) & P.res_s.notna()].copy()
print("pool sizes", len(dbl), len(sgl))
def tab(df, by, r, p):
    g = df.groupby(by, observed=True).agg(n=(r, "size"), win=(r, lambda x: (x == 1).mean() * 100), stop=(r, lambda x: (x == -1).mean() * 100), pnl=(p, lambda x: x.mean() * 100))
    return g.round(2)
for name, df, r, p in (("DOUBLE pool, target 20%", dbl, "res_d", "pnl_d"), ("SINGLE pool, target 10%", sgl, "res_s", "pnl_s")):
    print("\n=====", name)
    print(tab(df, "period", r, p))
    for by in ("stage", "sec_stage", "spy_up", "fresh2"):
        print("\nby", by); print(tab(df, ["period", by], r, p))
    df["rsq"] = pd.cut(df.rs, [0, .2, .4, .6, .8, 1.0], include_lowest=True)
    print("\nby rs quintile"); print(tab(df, ["period", "rsq"], r, p))
    df["secrs"] = pd.cut(df.sec_rs, [0, .33, .66, 1.0], include_lowest=True)
    print("\nby sector rs tercile"); print(tab(df, ["period", "secrs"], r, p))
