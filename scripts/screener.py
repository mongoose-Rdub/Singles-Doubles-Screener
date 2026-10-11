"""
Singles and Doubles Screener, final version (standalone). Run after fetch_data.py and engine.py.

Design, taken from what ten years of data supported:
  * Universe: US stocks over $2B, price $10 or more, $20M or more traded per day (20 day average).
  * Tiers by average daily range (ATR as a share of price):
      Double tier: 4.0% or more        target +20%
      Single tier: 2.8% to under 4.0%  target +10%
    The odds of reaching a target before the stop rise steadily with daily range. That is the main signal.
  * Stage (30 week average and slope) for the stock and its sector, SPY regime, and past move record are
    shown as information only. None of them held up as an edge in both the early and later halves of the data.
  * Priority score (0 to 100) = 60% relative strength rank + 40% daily range rank inside the tier. It is an ordering
    aid. Out of sample it raised win rate but not profit per trade, and the dashboard says so.

Outputs (in dashboard_data/): candidates.json, odds.json, byyear.json, signals.json, summary.json
"""
import json
import pickle
import numpy as np
import pandas as pd

DOUBLE_ATR, SINGLE_ATR = 0.040, 0.028
MIN_PRICE, MIN_DVOL = 10.0, 20e6
START = "2017-09-01"
SPLIT = "2022-01-01"
STAGE_NAME = {1: "1 Base", 2: "2 Advance", 3: "3 Top", 4: "4 Decline"}
ODDS_EDGES = [0.0, 0.020, 0.025, 0.030, 0.035, 0.040, 0.045, 0.050, 0.060, 0.080, 1.0]
ODDS_LABELS = ["under 2.0", "2.0 to 2.5", "2.5 to 3.0", "3.0 to 3.5", "3.5 to 4.0", "4.0 to 4.5", "4.5 to 5.0", "5.0 to 6.0", "6.0 to 8.0", "8.0 and up"]


def clean(s):
    return (s or "").replace("-", " ").replace("–", " ").replace("—", " ").replace("  ", " ").strip()


def main():
    P = pickle.load(open("panel.pkl", "rb"))
    uni = {r["symbol"]: r for r in json.load(open("universe.json"))}
    need = ["sma150", "atr_pct", "slope150", "stage", "sec_stage", "rs", "stop_pct", "dist_high"]
    P = P.dropna(subset=need)
    P = P[(P.c >= MIN_PRICE) & (P.dvol20 >= MIN_DVOL) & (P.date >= START)].copy()
    asof = P["date"].max()
    cur = P[P.date == asof].copy()
    H = P[P.res_d.notna() & P.res_s.notna()].copy()         # rows with a finished 30 day outcome
    H["period"] = np.where(H.date < SPLIT, "early", "late")

    # ---------------- odds by daily range ----------------
    H["bucket"] = pd.cut(H.atr_pct, ODDS_EDGES, labels=ODDS_LABELS, right=False)
    odds = []
    for b, g in H.groupby("bucket", observed=True):
        odds.append({"range": str(b), "n": int(len(g)),
                     "win10": round(float((g.res_s == 1).mean() * 100), 1), "win20": round(float((g.res_d == 1).mean() * 100), 1),
                     "stop10": round(float((g.res_s == -1).mean() * 100), 1), "stop20": round(float((g.res_d == -1).mean() * 100), 1),
                     "pnl10": round(float(g.pnl_s.mean() * 100), 2), "pnl20": round(float(g.pnl_d.mean() * 100), 2),
                     "avg_stop": round(float(g.stop_pct.mean() * 100), 1)})
    odds_lookup = {o["range"]: o for o in odds}

    # ---------------- tiers and their tested results ----------------
    H["tier"] = np.where(H.atr_pct >= DOUBLE_ATR, "Double", np.where(H.atr_pct >= SINGLE_ATR, "Single", None))
    T = H[H.tier.notna()].copy()
    T["res"] = np.where(T.tier == "Double", T.res_d, T.res_s)
    T["pnl"] = np.where(T.tier == "Double", T.pnl_d, T.pnl_s)
    T["atr_rank"] = T.groupby(["date", "tier"]).atr_pct.rank(pct=True)
    T["score"] = 60 * T.rs + 40 * T.atr_rank
    T["year"] = T.date.dt.year

    def top(df, n=25):
        return df.sort_values(["date", "score"], ascending=[True, False]).groupby(["tier", "date"]).head(n)

    byyear = []
    for tier in ("Double", "Single"):
        G = T[T.tier == tier]
        for y, g in G.groupby("year"):
            t = top(g)
            byyear.append({"year": int(y), "tier": tier, "n_tier": int(len(g)),
                           "win_tier": round(float((g.res == 1).mean() * 100), 1), "pnl_tier": round(float(g.pnl.mean() * 100), 2),
                           "win_top": round(float((t.res == 1).mean() * 100), 1), "pnl_top": round(float(t.pnl.mean() * 100), 2),
                           "stop_tier": round(float(g.stop_pct.mean() * 100), 1), "stop_top": round(float(t.stop_pct.mean() * 100), 1)})

    # ---------------- does anything else add edge? early vs late ----------------
    signals = []

    def add(group, value, mask, base):
        row = {"group": group, "value": value}
        diffs = []
        for per in ("early", "late"):
            g = T[(T.period == per) & mask]
            b = base[per]
            row[f"n_{per}"] = int(len(g))
            row[f"win_{per}"] = round(float((g.res == 1).mean() * 100), 1) if len(g) else None
            row[f"pnl_{per}"] = round(float(g.pnl.mean() * 100), 2) if len(g) else None
            if len(g) >= 400:
                diffs.append(((g.res == 1).mean() * 100 - b[0], g.pnl.mean() * 100 - b[1]))
        if len(diffs) == 2:
            (dw1, dp1), (dw2, dp2) = diffs
            if np.sign(dw1) == np.sign(dw2) and np.sign(dp1) == np.sign(dp2) and min(abs(dw1), abs(dw2)) >= 2 and min(abs(dp1), abs(dp2)) >= 0.25:
                row["verdict"] = "Held in both periods"
            elif np.sign(dw1) != np.sign(dw2) or np.sign(dp1) != np.sign(dp2):
                row["verdict"] = "Reversed between periods"
            else:
                row["verdict"] = "Too small to trust"
        else:
            row["verdict"] = "Too few cases"
        signals.append(row)

    base = {per: ((T[T.period == per].res == 1).mean() * 100, T[T.period == per].pnl.mean() * 100) for per in ("early", "late")}
    add("Everything in the tiers", "Baseline", T.index == T.index, base)
    for k in (1, 2, 3, 4):
        add("Stock stage", {1: "Stage 1 base", 2: "Stage 2 advance", 3: "Stage 3 top", 4: "Stage 4 decline"}[k], T.stage == k, base)
    for k in (2, 3, 4):
        add("Sector stage", {2: "Sector in Stage 2", 3: "Sector in Stage 3", 4: "Sector in Stage 4"}[k], T.sec_stage == k, base)
    add("Market regime", "SPY above 200 day average", T.spy_up == 1, base)
    add("Market regime", "SPY below 200 day average", T.spy_up == 0, base)
    add("Relative strength", "Top fifth of the market", T.rs >= 0.8, base)
    add("Relative strength", "Bottom fifth of the market", T.rs < 0.2, base)
    add("Trend filter", "Price above 150 day average", T.c > T.sma150, base)
    add("Trend filter", "Price below 150 day average", T.c <= T.sma150, base)

    # ---------------- headline numbers for the summary ----------------
    summ = {}
    for tier in ("Double", "Single"):
        G = T[T.tier == tier]
        t = top(G)
        wk = (t.groupby("date").pnl.mean() - G.groupby("date").pnl.mean())
        summ[tier] = {"n": int(len(G)), "win": round(float((G.res == 1).mean() * 100), 1), "stop": round(float((G.res == -1).mean() * 100), 1),
                      "pnl": round(float(G.pnl.mean() * 100), 2), "avg_stop": round(float(G.stop_pct.mean() * 100), 1),
                      "top_win": round(float((t.res == 1).mean() * 100), 1), "top_pnl": round(float(t.pnl.mean() * 100), 2),
                      "top_stop": round(float(t.stop_pct.mean() * 100), 1),
                      "pnl_gap": round(float(wk.mean() * 100), 2), "pnl_gap_se": round(float(wk.std() / np.sqrt(len(wk)) * 100), 2)}

    # ---------------- current candidates ----------------
    cur["tier"] = np.where(cur.atr_pct >= DOUBLE_ATR, "Double", np.where(cur.atr_pct >= SINGLE_ATR, "Single", None))
    cur = cur[cur.tier.notna()].copy()
    cur["atr_rank"] = cur.groupby("tier").atr_pct.rank(pct=True)
    cur["score"] = 60 * cur.rs + 40 * cur.atr_rank
    cur["bucket"] = pd.cut(cur.atr_pct, ODDS_EDGES, labels=ODDS_LABELS, right=False).astype(str)
    rows = []
    for _, r in cur.sort_values("score", ascending=False).iterrows():
        u = uni.get(r.sym, {})
        tp = 0.20 if r.tier == "Double" else 0.10
        o = odds_lookup.get(r.bucket, {})
        stg = STAGE_NAME[int(r.stage)] + (" early" if r.fresh2 == 1 else "")
        rows.append({
            "symbol": r.sym,
            "name": clean(u.get("name", "").replace(" Common Stock", "").replace(" Class A", "").replace(" Inc.", "").replace(" Corporation", "")),
            "sector": clean(r.sector), "mcap_b": round(float(u.get("marketCap", 0) or 0) / 1e9, 1),
            "tier": r.tier, "score": round(float(r.score), 1),
            "price": round(float(r.c), 2), "target": round(float(r.c * (1 + tp)), 2), "stop": round(float(r.stop), 2),
            "stop_pct": round(float(r.stop_pct) * 100, 1), "rr": round(float(tp / r.stop_pct), 2),
            "odds": float(o.get("win20" if r.tier == "Double" else "win10", np.nan)),
            "atr_pct": round(float(r.atr_pct) * 100, 2),
            "rs": round(float(r.rs) * 100, 0), "ret63": round(float(r.ret63) * 100, 1), "ret21": round(float(r.ret21) * 100, 1),
            "dist_high": round(float(r.dist_high) * 100, 1),
            "stage": stg, "sector_stage": STAGE_NAME[int(r.sec_stage)],
            "dvol_m": round(float(r.dvol20) / 1e6, 0),
        })

    n_all = int(P[P.date == asof].shape[0])
    summary = [{
        "asof": asof.strftime("%Y-%m-%d"),
        "universe_total": int(P.sym.nunique()),
        "liquid_now": n_all,
        "tier_double": int((cur.tier == "Double").sum()), "tier_single": int((cur.tier == "Single").sum()),
        "pct_above50": round(float((P[P.date == asof].c > P[P.date == asof].sma50).mean() * 100), 1),
        "first": H.date.min().strftime("%Y-%m-%d"), "last": H.date.max().strftime("%Y-%m-%d"),
        "weeks": int(H.date.nunique()), "trades": int(len(T)),
        "d_win": summ["Double"]["win"], "d_stop": summ["Double"]["stop"], "d_pnl": summ["Double"]["pnl"], "d_avg_stop": summ["Double"]["avg_stop"],
        "s_win": summ["Single"]["win"], "s_stop": summ["Single"]["stop"], "s_pnl": summ["Single"]["pnl"], "s_avg_stop": summ["Single"]["avg_stop"],
        "d_top_win": summ["Double"]["top_win"], "d_top_pnl": summ["Double"]["top_pnl"], "d_top_stop": summ["Double"]["top_stop"],
        "s_top_win": summ["Single"]["top_win"], "s_top_pnl": summ["Single"]["top_pnl"], "s_top_stop": summ["Single"]["top_stop"],
        "d_gap": summ["Double"]["pnl_gap"], "d_gap_se": summ["Double"]["pnl_gap_se"],
        "s_gap": summ["Single"]["pnl_gap"], "s_gap_se": summ["Single"]["pnl_gap_se"],
    }]
    out = "dashboard_data/"
    for name, obj in (("candidates", rows), ("odds", odds), ("byyear", byyear), ("signals", signals), ("summary", summary)):
        json.dump(obj, open(out + name + ".json", "w"))
    print(json.dumps(summary[0], indent=1))
    print("odds:"); print(pd.DataFrame(odds).to_string(index=False))
    print("signals:"); print(pd.DataFrame(signals)[["group", "value", "n_early", "win_early", "pnl_early", "n_late", "win_late", "pnl_late", "verdict"]].to_string(index=False))
    print("byyear:"); print(pd.DataFrame(byyear).to_string(index=False))
    print("candidates", len(rows), pd.Series([r["stage"] for r in rows]).value_counts().to_dict())


if __name__ == "__main__":
    main()
