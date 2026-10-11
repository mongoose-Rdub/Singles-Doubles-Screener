import pickle, numpy as np, pandas as pd
P = pickle.load(open("panel.pkl", "rb"))
P = P.dropna(subset=["sma150", "atr_pct", "single_rate", "double_rate", "stage", "sec_stage", "range40", "rsi", "slope50"])
P = P[(P.nwin >= 200) & (P.c >= 10) & (P.dvol20 >= 20e6) & (P.date >= "2018-01-01")].copy()
P["period"] = np.where(P.date < "2022-01-01", "dev", "test")
c = P
# setup tags (vectorized)
near20 = (c.c / c.ema20 - 1).abs()
pull = (c.c > c.sma50) & (c.slope50 > 0) & (near20 < .035) & c.rsi.between(38, 58)
pull_s = np.where(pull, 25 - near20 * 300 - (c.rsi - 48).abs() * .4, 0)
base = (c.dist_high > -.12) & (c.range10 < .075) & (c.range10 < .6 * c.range40)
base_s = np.where(base, 25 - c.range10 * 100 - c.dist_high.abs() * 40, 0)
brk = (c.c > c.hi20) & (c.vol5 > 1.2 * c.vol50) & (c.above50 < .2)
brk_s = np.where(brk, 22 + np.minimum((c.vol5 / c.vol50 - 1.2) * 5, 3), 0)
P["setup_pts"] = np.maximum.reduce([pull_s, base_s, brk_s]).clip(0) * 0.4
P["cap_pts"] = np.minimum(P.single_rate / .65, 1) * 15 + np.minimum(P.double_rate / .35, 1) * 12 + np.minimum(P.atr_pct / .045, 1) * 8
P["rs_pts"] = 18 * P.rs + np.where(P.ret21 > .03, 6, 0) + np.where(P.ret21 > .10, 6, 0)
P["trend_pts"] = np.where((P.c > P.sma50) & (P.sma50 > P.sma150), 11, 0) + np.where(P.slope50 > .02, 6, np.where(P.slope50 > 0, 3, 0)) + np.where(P.c > P.sma20, 3, 0)
P["vol_pts"] = np.where(P.vol5 >= P.vol50, 5, np.where(P.vol5 >= .8 * P.vol50, 2.5, 0))
P["score"] = P.cap_pts + P.rs_pts + P.trend_pts + P.setup_pts + P.vol_pts
elig = (P.c > P.sma150) & (P.above50 < .30)
D = P[(P.atr_pct >= .033) & (P.double_rate >= .15) & P.res_d.notna()].copy()
S = P[(P.atr_pct >= .022) & (P.atr_pct < .033) & (P.single_rate >= .30) & P.res_s.notna()].copy()
D["elig"] = elig[D.index]; S["elig"] = elig[S.index]

def perf(df, r, p, label):
    n = len(df)
    if n == 0: return None
    return dict(label=label, n=n, win=round((df[r] == 1).mean() * 100, 1), stop=round((df[r] == -1).mean() * 100, 1), pnl=round(df[p].mean() * 100, 2))

def topn(df, col, n=25, floor=None):
    d = df
    if floor is not None: d = d[d[col] >= floor]
    return d.sort_values(["date", col], ascending=[True, False]).groupby("date").head(n)

def report(name, pool, r, p):
    rows = []
    for per in ("dev", "test", "all"):
        base = pool if per == "all" else pool[pool.period == per]
        eb = base[base.elig]
        rows.append(perf(base, r, p, f"{per}: pool, all"))
        rows.append(perf(eb, r, p, f"{per}: pool, trend filter"))
        for floor in (None, 60):
            t = topn(eb, "score", 25, floor)
            rows.append(perf(t, r, p, f"{per}: top 25 score" + (f">={floor}" if floor else "")))
    print("\n=====", name); print(pd.DataFrame([x for x in rows if x]).to_string(index=False))
report("DOUBLE pool", D, "res_d", "pnl_d")
report("SINGLE pool", S, "res_s", "pnl_s")

# components alone: top quintile by component, within trend filtered pool
def comp(pool, r, p, name):
    e = pool[pool.elig]
    out = []
    for col in ("cap_pts", "rs_pts", "trend_pts", "setup_pts", "vol_pts", "score"):
        for per in ("dev", "test"):
            g = e[e.period == per]
            thr = g[col].quantile(.8)
            top, rest = g[g[col] >= thr], g[g[col] < thr]
            out.append(dict(component=col, period=per, top_win=round((top[r] == 1).mean() * 100, 1), rest_win=round((rest[r] == 1).mean() * 100, 1),
                            top_pnl=round(top[p].mean() * 100, 2), rest_pnl=round(rest[p].mean() * 100, 2)))
    print("\n== component lift", name); print(pd.DataFrame(out).to_string(index=False))
comp(D, "res_d", "pnl_d", "DOUBLE"); comp(S, "res_s", "pnl_s", "SINGLE")

# by year for the top 25 picks vs trend filtered pool
for name, pool, r, p in (("DOUBLE", D, "res_d", "pnl_d"), ("SINGLE", S, "res_s", "pnl_s")):
    e = pool[pool.elig]; t = topn(e, "score", 25, 60)
    e = e.assign(year=e.date.dt.year); t = t.assign(year=t.date.dt.year)
    y = pd.DataFrame({"pool_win": e.groupby("year")[r].apply(lambda x: (x == 1).mean() * 100), "pick_win": t.groupby("year")[r].apply(lambda x: (x == 1).mean() * 100),
                      "pool_pnl": e.groupby("year")[p].mean() * 100, "pick_pnl": t.groupby("year")[p].mean() * 100, "picks_n": t.groupby("year").size()}).round(2)
    print("\n== by year", name); print(y)
