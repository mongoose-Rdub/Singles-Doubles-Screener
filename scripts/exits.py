"""
Exit rule study (standalone). Uses the same entries as the screener (tier stocks, weekly, entered at the close)
and replays each trade under many exit rules using the actual daily bars that followed.

Run: python3 exits.py        Output: exit_results.pkl and a printed comparison
"""
import os
import pickle
import store
import numpy as np
import pandas as pd

K = 60                       # longest holding window tested, trading days
START = "2017-09-01"
DOUBLE_ATR, SINGLE_ATR = 0.040, 0.028


def load_entries():
    P = pickle.load(open(os.path.join(store.WORK, "panel.pkl"), "rb"))
    P = P.dropna(subset=["sma150", "atr_pct", "slope150", "stage", "stop", "atr"])
    P = P[(P.c >= 10) & (P.dvol20 >= 20e6) & (P.date >= START) & (P.atr_pct >= SINGLE_ATR)].copy()
    P["tier"] = np.where(P.atr_pct >= DOUBLE_ATR, "Double", "Single")
    bars = store.load_bars()
    O, Hh, L, C, rows = [], [], [], [], []
    for sym, g in P.groupby("sym"):
        b = np.array(bars[sym], dtype=object)
        dates = pd.to_datetime(b[:, 0]).values
        arr = b[:, 1:].astype(float)           # o h l c v
        pos = np.searchsorted(dates, g["date"].values)
        ok = (pos + K < len(dates)) & (dates[np.minimum(pos, len(dates) - 1)] == g["date"].values)
        g, pos = g[ok], pos[ok]
        if len(g) == 0:
            continue
        idx = pos[:, None] + 1 + np.arange(K)[None, :]
        O.append(arr[idx, 0]); Hh.append(arr[idx, 1]); L.append(arr[idx, 2]); C.append(arr[idx, 3])
        rows.append(g[["sym", "date", "tier", "c", "atr", "stop", "stop_pct"]])
    E = pd.concat(rows).reset_index(drop=True)
    return E, np.vstack(O).astype(np.float32), np.vstack(Hh).astype(np.float32), np.vstack(L).astype(np.float32), np.vstack(C).astype(np.float32)


def sim(O, H, L, C, c0, stop0, atr0, tgt_pct, D, be=None, trail=None, trail_start=0.0):
    """Replays each trade. Stop is checked before target on a day (conservative); a gap through the stop fills
    at the open. be: after the high reaches +be, stop moves to entry. trail: after the high reaches +trail_start,
    stop follows the highest close minus trail * ATR. tgt_pct None means no target."""
    N = len(c0)
    stop = stop0.astype(np.float64).copy()
    alive = np.ones(N, bool)
    pnl = np.zeros(N)
    days = np.full(N, float(D))
    tgt = c0 * (1 + tgt_pct) if tgt_pct is not None else np.full(N, np.inf)
    hi_close = c0.astype(np.float64).copy()
    armed_be = np.zeros(N, bool)
    armed_tr = np.zeros(N, bool)
    for k in range(D):
        o, h, l, c = O[:, k], H[:, k], L[:, k], C[:, k]
        hs = alive & (l <= stop)
        pnl = np.where(hs, np.minimum(stop, o) / c0 - 1, pnl)
        days = np.where(hs, k + 1, days)
        alive &= ~hs
        ht = alive & (h >= tgt)
        pnl = np.where(ht, tgt / c0 - 1, pnl)
        days = np.where(ht, k + 1, days)
        alive &= ~ht
        if be is not None:
            armed_be |= alive & (h >= c0 * (1 + be))
            stop = np.where(armed_be, np.maximum(stop, c0), stop)
        if trail is not None:
            armed_tr |= alive & (h >= c0 * (1 + trail_start))
            hi_close = np.where(alive, np.maximum(hi_close, c), hi_close)
            stop = np.where(armed_tr, np.maximum(stop, hi_close - trail * atr0), stop)
    pnl = np.where(alive, C[:, D - 1] / c0 - 1, pnl)
    return pnl, days


def summarize(E, pnl, days, label):
    d = E.assign(pnl=pnl, days=days)
    out = {"variant": label}
    for tier in ("Double", "Single"):
        g = d[d.tier == tier]
        wk = g.groupby("date").pnl.mean()
        early, late = g[g.date < "2022-01-01"], g[g.date >= "2022-01-01"]
        out[tier + "_pnl"] = round(g.pnl.mean() * 100, 2)
        out[tier + "_se"] = round(wk.std() / np.sqrt(len(wk)) * 100, 2)
        out[tier + "_early"] = round(early.pnl.mean() * 100, 2)
        out[tier + "_late"] = round(late.pnl.mean() * 100, 2)
        out[tier + "_win"] = round((g.pnl > 0).mean() * 100, 1)
        out[tier + "_days"] = round(g.days.mean(), 1)
        out[tier + "_perday"] = round(g.pnl.sum() / g.days.sum() * 100, 3)     # profit per trading day held
        out[tier + "_worst"] = round(g.pnl.quantile(0.02) * 100, 1)
    return out


def main():
    E, O, H, L, C = load_entries()
    print("entries", len(E), E.groupby("tier").size().to_dict(), E.date.min().date(), E.date.max().date())
    c0 = E.c.values.astype(np.float64); atr0 = E.atr.values.astype(np.float64); stop0 = E.stop.values.astype(np.float64)
    tp = np.where(E.tier == "Double", 0.20, 0.10)
    tp_half = tp / 2
    res = []
    stop_m = lambda m: np.minimum(c0 - m * atr0, c0 * 0.97)

    def run(label, stop=None, tgt="tier", D=30, **kw):
        s = stop0 if stop is None else stop
        # target differs by tier, so run each tier separately and stitch
        pnl = np.zeros(len(E)); days = np.zeros(len(E))
        for tier, t in (("Double", 0.20), ("Single", 0.10)):
            m = (E.tier == tier).values
            tg = None if tgt is None else (t if tgt == "tier" else tgt(t))
            p, d = sim(O[m], H[m], L[m], C[m], c0[m], s[m], atr0[m], tg, D, **{k: (v(t) if callable(v) else v) for k, v in kw.items()})
            pnl[m], days[m] = p, d
        res.append(summarize(E, pnl, days, label))
        return pnl, days

    # A. time limits with the baseline stop and target
    for D in (10, 15, 20, 30, 45, 60):
        run(f"baseline stop and target, {D} day limit", D=D)
    # B. stop width
    for m in (1.0, 1.5, 2.0, 3.0, 4.0):
        run(f"stop {m} ATR below entry (min 3%), 30 days", stop=stop_m(m))
    # C. breakeven stop after a partial gain
    for frac, name in ((0.25, "quarter"), (0.5, "half")):
        run(f"move stop to breakeven after {name} of the target, 30 days", be=lambda t, f=frac: t * f)
    # D. trailing stop with the target kept
    for m in (2.0, 3.0):
        run(f"keep target, trail {m} ATR after half the target, 30 days", trail=m, trail_start=lambda t: t / 2)
    # E. no target, trailing stop from entry
    for m in (2.0, 3.0, 4.0):
        for D in (30, 60):
            run(f"no target, trail {m} ATR, {D} days", tgt=None, D=D, trail=m, trail_start=0.0)
    # F. no target, trail only after a gain of half the single (5%)
    for m in (2.0, 3.0):
        run(f"no target, trail {m} ATR once up 5%, 60 days", tgt=None, D=60, trail=m, trail_start=0.05)
    # G. sell half at the single and the rest to the double, stop to breakeven after the single
    pnl_a = np.zeros(len(E)); pnl_b = np.zeros(len(E)); days_b = np.zeros(len(E)); days_a = np.zeros(len(E))
    for tier in ("Double", "Single"):
        m = (E.tier == tier).values
        pa, da = sim(O[m], H[m], L[m], C[m], c0[m], stop0[m], atr0[m], 0.10, 45)
        pb, db = sim(O[m], H[m], L[m], C[m], c0[m], stop0[m], atr0[m], 0.20, 45, be=0.10)
        pnl_a[m], pnl_b[m], days_a[m], days_b[m] = pa, pb, da, db
    pnl = 0.5 * pnl_a + 0.5 * pnl_b
    days = 0.5 * days_a + 0.5 * days_b
    res.append(summarize(E, pnl, days, "sell half at +10%, rest to +20% with breakeven stop, 45 days"))
    # H. same but rest runs with a 3 ATR trail instead of a fixed +20% target
    pnl_c = np.zeros(len(E)); days_c = np.zeros(len(E))
    for tier in ("Double", "Single"):
        m = (E.tier == tier).values
        pc, dc = sim(O[m], H[m], L[m], C[m], c0[m], stop0[m], atr0[m], None, 60, be=0.10, trail=3.0, trail_start=0.10)
        pnl_c[m], days_c[m] = pc, dc
    res.append(summarize(E, 0.5 * pnl_a + 0.5 * pnl_c, 0.5 * days_a + 0.5 * days_c, "sell half at +10%, rest trails 3 ATR after +10%, 60 days"))

    R = pd.DataFrame(res)
    pickle.dump(R, open(os.path.join(store.WORK, "exit_results.pkl"), "wb"))
    pd.set_option("display.width", 250)
    for tier in ("Double", "Single"):
        cols = ["variant"] + [tier + s for s in ("_pnl", "_se", "_early", "_late", "_win", "_days", "_perday", "_worst")]
        print("\n=====", tier, "tier. pnl = average profit per trade %, se = margin of error, perday = profit per trading day held (%)")
        print(R[cols].to_string(index=False))


def export_dashboard():
    """Writes dashboard_data/exits.json: a short, honest comparison of exit rules against plain holding."""
    import json
    E, O, H, L, C = load_entries()
    c0 = E.c.values.astype(np.float64); atr0 = E.atr.values.astype(np.float64); stop0 = E.stop.values.astype(np.float64)
    rules = []

    def stitched(tgt, D, **kw):
        pnl = np.zeros(len(E)); days = np.zeros(len(E))
        for tier, t in (("Double", 0.20), ("Single", 0.10)):
            m = (E.tier == tier).values
            p, d = sim(O[m], H[m], L[m], C[m], c0[m], stop0[m], atr0[m], t if tgt == "tier" else None, D, **kw)
            pnl[m], days[m] = p, d
        return pnl, days

    rules.append(("Fixed target and stop, 30 days", *stitched("tier", 30)))
    rules.append(("No target, trailing stop 3 ATR, 30 days", *stitched(None, 30, trail=3.0, trail_start=0.0)))
    rules.append(("No target, trailing stop 4 ATR, 60 days", *stitched(None, 60, trail=4.0, trail_start=0.0)))
    rules.append(("Sell half at +10%, rest trails 3 ATR, 60 days", *(lambda a, b: (0.5 * a[0] + 0.5 * b[0], 0.5 * a[1] + 0.5 * b[1]))(
        stitched_leg(O, H, L, C, E, c0, stop0, atr0, 0.10, 45), stitched_leg(O, H, L, C, E, c0, stop0, atr0, None, 60, be=0.10, trail=3.0, trail_start=0.10))))
    rules.append(("Hold 30 days, no stop, no target", C[:, 29] / c0 - 1, np.full(len(E), 30.0)))
    out = []
    for label, pnl, days in rules:
        r = summarize(E, pnl, days, label)
        for tier in ("Double", "Single"):
            out.append({"tier": tier, "rule": label, "avg": r[tier + "_pnl"], "se": r[tier + "_se"], "early": r[tier + "_early"], "late": r[tier + "_late"],
                        "win": r[tier + "_win"], "days": r[tier + "_days"], "perday": r[tier + "_perday"], "worst": r[tier + "_worst"]})
    json.dump(out, open(os.path.join(store.OUT, "exits.json"), "w"))
    print(pd.DataFrame(out).to_string(index=False))


def stitched_leg(O, H, L, C, E, c0, stop0, atr0, tgt, D, **kw):
    pnl = np.zeros(len(E)); days = np.zeros(len(E))
    for tier, t in (("Double", 0.20), ("Single", 0.10)):
        m = (E.tier == tier).values
        tg = None if tgt is None else tgt
        p, d = sim(O[m], H[m], L[m], C[m], c0[m], stop0[m], atr0[m], tg, D, **kw)
        pnl[m], days[m] = p, d
    return pnl, days


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "dashboard":
        export_dashboard()
    else:
        main()
