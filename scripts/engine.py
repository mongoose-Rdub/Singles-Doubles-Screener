"""
Singles and Doubles engine (standalone). Builds one weekly panel from ten years of daily bars.

For every stock and every week it computes: trend and momentum features, a Weinstein style
stage (30 week average and its slope), the stage of the stock's sector, the market regime from SPY,
the stock's own historical hit rates, and what happened next if you had entered at that close
with a stop and a +10% or +20% target (30 trading day limit).

Run: python3 engine.py      Output: panel.pkl
"""
import json
import pickle
import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view as swv

H = 30               # trading days in the holding window, about 6 weeks
SINGLE, DOUBLE = 0.10, 0.20
SLOPE_BAND = 0.015   # 30 week average counts as rising or falling beyond +/- 1.5% over 10 weeks


def stage_of(c, sma150, slope150, dist_high):
    """Weinstein style stage from the 30 week (150 day) average and its 10 week slope.
    2 = average rising, 4 = average falling, flat average is 1 (basing, far below high) or 3 (topping)."""
    st = np.where(slope150 > SLOPE_BAND, 2,
         np.where(slope150 < -SLOPE_BAND, 4,
         np.where(dist_high < -0.25, 1, 3)))
    st = np.where(np.isfinite(slope150) & np.isfinite(sma150), st, 0)
    return st.astype(np.int8)


def outcomes(o, h, l, c, stop, tp):
    """Trade result for entering at each bar's close. Stop assumed first if both trade the same bar;
    a gap below the stop fills at the open. Returns pnl (fraction) and res (1 target, -1 stop, 0 timeout)."""
    n = len(c)
    pnl = np.full(n, np.nan, np.float32)
    res = np.full(n, np.nan, np.float32)
    m = n - H
    if m <= 0:
        return pnl, res
    Hw, Lw, Ow = swv(h[1:], H)[:m], swv(l[1:], H)[:m], swv(o[1:], H)[:m]
    st = stop[:m, None]
    tg = (c[:m] * (1 + tp))[:, None]
    sh, th = Lw <= st, Hw >= tg
    fs = np.where(sh.any(1), sh.argmax(1), H + 1)
    ft = np.where(th.any(1), th.argmax(1), H + 1)
    stopped = (fs <= ft) & (fs <= H)
    won = (ft < fs)
    idx = np.arange(m)
    fill = np.minimum(stop[:m], Ow[idx, np.minimum(fs, H - 1)])
    p = np.where(stopped, fill / c[:m] - 1, np.where(won, tp, c[H:H + m] / c[:m] - 1))
    r = np.where(stopped, -1.0, np.where(won, 1.0, 0.0))
    ok = np.isfinite(stop[:m])
    pnl[:m] = np.where(ok, p, np.nan)
    res[:m] = np.where(ok, r, np.nan)
    return pnl, res


def indicators(df):
    o, h, l, c, v = (df[k].values.astype(float) for k in ("o", "h", "l", "c", "v"))
    s = pd.DataFrame(index=df.index)
    cs, hs, ls, vs = df["c"], df["h"], df["l"], df["v"]
    s["c"] = cs
    s["sma20"] = cs.rolling(20).mean()
    s["sma50"] = cs.rolling(50).mean()
    s["sma150"] = cs.rolling(150).mean()
    s["sma200"] = cs.rolling(200).mean()
    s["ema20"] = cs.ewm(span=20, adjust=False).mean()
    pc = cs.shift(1)
    tr = pd.concat([hs - ls, (hs - pc).abs(), (ls - pc).abs()], axis=1).max(axis=1)
    s["atr"] = tr.rolling(14).mean()
    s["atr_pct"] = s["atr"] / cs
    s["hi252"] = hs.rolling(252, min_periods=200).max()
    s["dist_high"] = cs / s["hi252"] - 1
    s["ret63"] = cs / cs.shift(63) - 1
    s["ret21"] = cs / cs.shift(21) - 1
    s["hi20"] = hs.rolling(20).max().shift(1)
    s["range10"] = (hs.rolling(10).max() - ls.rolling(10).min()) / cs
    s["range40"] = (hs.rolling(40).max() - ls.rolling(40).min()) / cs
    s["vol5"] = vs.rolling(5).mean()
    s["vol50"] = vs.rolling(50).mean()
    s["dvol20"] = (cs * vs).rolling(20).mean()
    chg = cs.diff()
    gain, loss = chg.clip(lower=0).rolling(14).mean(), (-chg.clip(upper=0)).rolling(14).mean()
    s["rsi"] = 100 - 100 / (1 + gain / loss.replace(0, np.nan))
    s["low10"] = ls.rolling(10).min()
    s["above50"] = cs / s["sma50"] - 1
    s["above150"] = cs / s["sma150"] - 1
    s["slope50"] = s["sma50"] / s["sma50"].shift(10) - 1
    s["slope150"] = s["sma150"] / s["sma150"].shift(50) - 1
    s["stage"] = stage_of(cs.values, s["sma150"].values, s["slope150"].values, s["dist_high"].values)
    below = (cs / s["sma150"]).rolling(80).min()
    s["fresh2"] = ((s["stage"] == 2) & (below < 1.0)).astype(np.int8)   # Stage 2 that began recently
    # best high in the next H bars (for hit rates) and trade outcomes
    fmax = pd.Series(np.concatenate([np.max(swv(h[1:], H), axis=1) / c[:-H] - 1, np.full(H, np.nan)])
                     if len(c) > H else np.full(len(c), np.nan), index=df.index)
    s["fwd_max"] = fmax
    valid = fmax.notna().astype(float)
    for name, thr in (("single", SINGLE), ("double", DOUBLE)):
        done = (fmax >= thr).astype(float).where(fmax.notna(), 0.0)
        # a window is known only H bars later, so shift by H before accumulating
        s[name + "_rate"] = done.shift(H).fillna(0).cumsum() / valid.shift(H).fillna(0).cumsum().replace(0, np.nan)
    s["nwin"] = valid.shift(H).fillna(0).cumsum()
    stop = np.minimum(np.maximum(s["low10"].values * 0.995, c - 2 * s["atr"].values), c * 0.97)
    s["stop"] = stop
    s["stop_pct"] = 1 - stop / c
    for tag, tp in (("s", SINGLE), ("d", DOUBLE)):
        p, r = outcomes(o, h, l, c, stop, tp)
        s["pnl_" + tag] = p
        s["res_" + tag] = r
    return s


def build():
    bars = pickle.load(open("bars10y.pkl", "rb"))
    uni = {r["symbol"]: r for r in json.load(open("universe.json"))}
    spy = pd.DataFrame(bars.pop("SPY"), columns=["date", "o", "h", "l", "c", "v"])
    spy["date"] = pd.to_datetime(spy["date"]); spy = spy.set_index("date")
    cal = spy.index
    wk = pd.Series(cal, index=cal).groupby(cal.to_period("W")).last().values   # last trading day of each week
    wk = pd.DatetimeIndex(wk)

    frames, rets = [], {}
    for i, (sym, rows) in enumerate(bars.items()):
        df = pd.DataFrame(rows, columns=["date", "o", "h", "l", "c", "v"])
        df["date"] = pd.to_datetime(df["date"])
        df = df.drop_duplicates("date").set_index("date").sort_index()
        if len(df) < 260:
            continue
        s = indicators(df)
        rets[sym] = df["c"].pct_change()
        sub = s.loc[s.index.intersection(wk)].copy()
        sub["sym"] = sym
        sub["sector"] = (uni.get(sym, {}).get("sector") or "Other").strip() or "Other"
        frames.append(sub)
        if i % 300 == 0:
            print("stocks", i, flush=True)
    panel = pd.concat(frames)
    panel.index.name = "date"
    panel = panel.reset_index()

    # ---- sector indexes: equal weighted daily return of members, then the same stage logic ----
    R = pd.DataFrame(rets)
    sect = {s: (uni.get(s, {}).get("sector") or "Other").strip() or "Other" for s in R.columns}
    secrows = []
    for sec in sorted(set(sect.values())):
        cols = [s for s, k in sect.items() if k == sec]
        if len(cols) < 8:
            continue
        r = R[cols].mean(axis=1, skipna=True).fillna(0)
        lvl = (1 + r).cumprod()
        d = pd.DataFrame({"c": lvl})
        d["sma150"] = d["c"].rolling(150).mean()
        d["slope150"] = d["sma150"] / d["sma150"].shift(50) - 1
        d["hi252"] = d["c"].rolling(252, min_periods=200).max()
        d["dist_high"] = d["c"] / d["hi252"] - 1
        d["stage"] = stage_of(d["c"].values, d["sma150"].values, d["slope150"].values, d["dist_high"].values)
        d["ret63"] = d["c"] / d["c"].shift(63) - 1
        d["sector"] = sec
        secrows.append(d.loc[d.index.intersection(wk)].reset_index().rename(columns={"index": "date"}))
    sec = pd.concat(secrows)
    sec["sec_rs"] = sec.groupby("date")["ret63"].rank(pct=True)
    sec = sec.rename(columns={"stage": "sec_stage", "slope150": "sec_slope", "ret63": "sec_ret63"})[["date", "sector", "sec_stage", "sec_slope", "sec_ret63", "sec_rs"]]
    panel = panel.merge(sec, on=["date", "sector"], how="left")

    # ---- market regime from SPY ----
    sp = pd.DataFrame({"c": spy["c"]})
    sp["sma200"] = sp["c"].rolling(200).mean()
    sp["sma150"] = sp["c"].rolling(150).mean()
    sp["slope150"] = sp["sma150"] / sp["sma150"].shift(50) - 1
    sp["hi252"] = sp["c"].rolling(252, min_periods=200).max()
    sp["spy_stage"] = stage_of(sp["c"].values, sp["sma150"].values, sp["slope150"].values, (sp["c"] / sp["hi252"] - 1).values)
    sp["spy_up"] = (sp["c"] > sp["sma200"]).astype(int)
    sp = sp.loc[sp.index.intersection(wk), ["spy_stage", "spy_up"]].reset_index().rename(columns={"index": "date", "date": "date"})
    panel = panel.merge(sp, on="date", how="left")
    panel["rs"] = panel.groupby("date")["ret63"].rank(pct=True)
    panel["mcap_b"] = panel["sym"].map(lambda s: float(uni.get(s, {}).get("marketCap", 0) or 0) / 1e9)
    pickle.dump(panel, open("panel.pkl", "wb"))
    print("panel rows", len(panel), "dates", panel["date"].nunique(), "stocks", panel["sym"].nunique())
    print(panel["date"].min(), panel["date"].max())
    return panel


if __name__ == "__main__":
    build()
