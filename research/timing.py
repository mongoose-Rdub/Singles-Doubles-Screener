"""Entry timing study: which day and price to enter the weekly list. Output: timing.pkl"""
import pickle, json
import numpy as np, pandas as pd
from numpy.lib.stride_tricks import sliding_window_view as swv
from engine import indicators, H
DOUBLE_ATR, SINGLE_ATR, MIN_PRICE, MIN_DVOL = 0.04, 0.028, 10.0, 20e6

def open_entry(o, h, l, c, stop, tp):
    n = len(c); m = n - H - 1
    pnl = np.full(n, np.nan); res = np.full(n, np.nan)
    if m <= 0: return pnl, res
    ent = o[1:m + 1]
    Hw, Lw = swv(h[1:], H)[:m], swv(l[1:], H)[:m]
    st = stop[:m, None]; tg = (ent * (1 + tp))[:, None]
    sh, th = Lw <= st, Hw >= tg
    fs = np.where(sh.any(1), sh.argmax(1), H + 1); ft = np.where(th.any(1), th.argmax(1), H + 1)
    stopped = (fs <= ft) & (fs <= H); won = ft < fs
    Ow = swv(o[1:], H)[:m]; idx = np.arange(m)
    fill = np.minimum(stop[:m], Ow[idx, np.minimum(fs, H - 1)])
    last = c[H:H + m]
    p = np.where(stopped, fill / ent - 1, np.where(won, tp, last / ent - 1))
    r = np.where(stopped, -1.0, np.where(won, 1.0, 0.0))
    ok = np.isfinite(stop[:m]) & (ent > 0)
    pnl[:m] = np.where(ok, p, np.nan); res[:m] = np.where(ok, r, np.nan)
    return pnl, res

bars = pickle.load(open("bars10y.pkl", "rb")); bars.pop("SPY")
out = []
for i, (sym, rows) in enumerate(bars.items()):
    df = pd.DataFrame(rows, columns=["date", "o", "h", "l", "c", "v"])
    df["date"] = pd.to_datetime(df["date"]); df = df.drop_duplicates("date").set_index("date").sort_index()
    if len(df) < 260: continue
    s = indicators(df)
    o, h, l, c = (df[k].values.astype(float) for k in ("o", "h", "l", "c"))
    s["pnl_do"], s["res_do"] = open_entry(o, h, l, c, s["stop"].values, 0.20)
    s["pnl_so"], s["res_so"] = open_entry(o, h, l, c, s["stop"].values, 0.10)
    s["dow"] = s.index.dayofweek
    nxt = pd.Series(s.index, index=s.index).shift(-1)
    s["lastofweek"] = (nxt.dt.to_period("W") != s.index.to_period("W")).values
    s = s[(s.c >= MIN_PRICE) & (s.dvol20 >= MIN_DVOL) & (s.index >= "2017-09-01") & (s.atr_pct >= SINGLE_ATR) & s.stop.notna()]
    keep = s[["dow", "lastofweek", "atr_pct", "rs" if "rs" in s else "ret63", "pnl_s", "res_s", "pnl_d", "res_d", "pnl_so", "res_so", "pnl_do", "res_do", "stop_pct"]].copy()
    keep["sym"] = sym
    out.append(keep)
    if i % 400 == 0: print(i, flush=True)
D = pd.concat(out); D.index.name = "date"
pickle.dump(D, open("timing.pkl", "wb")); print(len(D))
