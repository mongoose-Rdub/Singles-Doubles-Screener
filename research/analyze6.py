import warnings, numpy as np, pandas as pd
warnings.filterwarnings("ignore")
exec(open("analyze3.py").read().split("D = P[")[0])
P = P[P.res_d.notna()].copy()
P["tier"] = np.where(P.atr_pct >= .04, "Double", np.where(P.atr_pct >= .028, "Single", None))
T = P[P.tier.notna()].copy()
T["res"] = np.where(T.tier == "Double", T.res_d, T.res_s); T["pnl"] = np.where(T.tier == "Double", T.pnl_d, T.pnl_s)
T["R"] = T.pnl / T.stop_pct
T["atr_rank"] = T.groupby(["date", "tier"]).atr_pct.rank(pct=True)
T["comp"] = 60 * T.rs + 40 * T.atr_rank
T["period"] = np.where(T.date < "2022-01-01", "2018 to 2021", "2022 to 2026")
def top(df, col, n=25): return df.sort_values(["date", col], ascending=[True, False]).groupby(["tier", "date"]).head(n)
def line(g): return pd.Series(dict(n=len(g), win=(g.res == 1).mean() * 100, stop=(g.res == -1).mean() * 100, pnl=g.pnl.mean() * 100, R=g.R.mean(), stop_pct=g.stop_pct.mean() * 100))
for tier in ("Double", "Single"):
    G = T[T.tier == tier]
    print("\n=====", tier, "tier, tier size per week", round(G.groupby("date").size().mean()))
    rows = []
    for per in ("2018 to 2021", "2022 to 2026", "all"):
        g = G if per == "all" else G[G.period == per]
        rows.append(line(g).rename(f"{per}: whole tier"))
        for lab, col in (("composite", "comp"), ("rs only", "rs"), ("range only", "atr_pct")):
            rows.append(line(top(g, col)).rename(f"{per}: top 25 {lab}"))
    print(pd.DataFrame(rows).round(2).to_string())
    c = top(G, "comp"); g2 = G
    wk = c.groupby("date").pnl.mean() - g2.groupby("date").pnl.mean()
    print("composite minus tier, avg pnl per trade difference: %.2f%% +/- %.2f%% (1 se, weekly)" % (wk.mean() * 100, wk.std() / np.sqrt(len(wk)) * 100))
    wr = (c.groupby("date").res.apply(lambda x: (x == 1).mean()) - g2.groupby("date").res.apply(lambda x: (x == 1).mean()))
    print("win rate difference: %.2f pts +/- %.2f" % (wr.mean() * 100, wr.std() / np.sqrt(len(wr)) * 100))
    # stage tables inside tier
    for by in ("stage", "sec_stage", "spy_up"):
        print("\n  by", by); print(G.groupby(["period", by]).apply(line).round(2).to_string())
