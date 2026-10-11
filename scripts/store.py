"""Price store: ten years of daily bars kept as monthly compressed files (data/prices/YYYY-MM.csv.gz).
A daily update only rewrites the current month, so each commit stays small."""
import glob
import os
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRICES = os.path.join(ROOT, "data", "prices")
UNIVERSE = os.path.join(ROOT, "data", "universe.json")
WORK = os.path.join(ROOT, "work")          # scratch files, never committed
OUT = os.path.join(ROOT, "output")
COLS = ["sym", "date", "o", "h", "l", "c", "v"]


def load_frame():
    parts = [pd.read_csv(f) for f in sorted(glob.glob(os.path.join(PRICES, "*.csv.gz")))]
    df = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(columns=COLS)
    return df.drop_duplicates(["sym", "date"], keep="last")


def load_bars():
    """Returns {symbol: [(date, o, h, l, c, v), ...]} in the shape engine.py expects."""
    df = load_frame().sort_values(["sym", "date"])
    out = {}
    for sym, g in df.groupby("sym", sort=False):
        out[sym] = list(zip(g["date"], g["o"], g["h"], g["l"], g["c"], g["v"]))
    return out


def save_months(df, months=None):
    """Rewrite monthly files from df (all rows for the months being written)."""
    os.makedirs(PRICES, exist_ok=True)
    df = df.copy()
    df["m"] = df["date"].str[:7]
    for m, g in df.groupby("m"):
        if months is not None and m not in months:
            continue
        g = g.sort_values(["sym", "date"])[COLS]
        g.to_csv(os.path.join(PRICES, m + ".csv.gz"), index=False, float_format="%.4f", compression={"method": "gzip", "mtime": 0})


def last_date():
    f = sorted(glob.glob(os.path.join(PRICES, "*.csv.gz")))[-1]
    return pd.read_csv(f)["date"].max()
