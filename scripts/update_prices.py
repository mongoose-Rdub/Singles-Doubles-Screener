"""Updates the price store from Nasdaq's public API.

  python scripts/update_prices.py            incremental: fetch the last ~2 weeks for every symbol, append new days
  python scripts/update_prices.py --full     refetch the full ten years (use weekly, or after many splits)

Splits: Nasdaq returns split adjusted history. The incremental fetch overlaps the stored data by about a week;
if the overlapping closes disagree with what is stored, that symbol's full history is refetched.
"""
import concurrent.futures as cf
import datetime as dt
import json
import os
import sys
import time
import urllib.request

import pandas as pd
import store
from zoneinfo import ZoneInfo

H = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
WINDOW_DAYS = 14
THREADS = 12


def get(url, tries=5):
    for i in range(tries):
        try:
            return json.load(urllib.request.urlopen(urllib.request.Request(url, headers=H), timeout=60))
        except Exception:
            time.sleep(1.5 * (i + 1))
    return None


def num(s):
    try:
        return float(str(s).replace("$", "").replace(",", ""))
    except Exception:
        return None


def fetch(sym, cls, start, end):
    d = get(f"https://api.nasdaq.com/api/quote/{sym}/historical?assetclass={cls}&fromdate={start}&todate={end}&limit=10000")
    try:
        rows = d["data"]["tradesTable"]["rows"]
    except Exception:
        return None
    out = []
    for r in rows or []:
        v = [num(r[k]) for k in ("open", "high", "low", "close", "volume")]
        if None in v:
            continue
        m, dd, y = r["date"].split("/")
        out.append((sym, f"{y}-{m}-{dd}", *v))
    return out


def last_complete_session():
    """Newest date whose bar is final. Before 4:20 pm New York time today's bar is still forming, so it is excluded."""
    now = dt.datetime.now(ZoneInfo("America/New_York"))
    d = now.date() if now.time() >= dt.time(16, 20) else now.date() - dt.timedelta(days=1)
    return d.isoformat()


def main():
    full = "--full" in sys.argv
    today = dt.date.today()
    end = (today + dt.timedelta(days=1)).isoformat()
    uni = json.load(open(store.UNIVERSE))
    jobs = [(r["symbol"], "stocks") for r in uni] + [("SPY", "etf")]
    old = store.load_frame()
    start = "2016-10-01" if full else (pd.Timestamp(store.last_date()) - pd.Timedelta(days=WINDOW_DAYS)).strftime("%Y-%m-%d")
    print("mode", "full" if full else "incremental", "from", start, "symbols", len(jobs), flush=True)

    got, failed = [], []
    with cf.ThreadPoolExecutor(THREADS) as ex:
        futs = {ex.submit(fetch, s, c, start, end): s for s, c in jobs}
        for i, f in enumerate(cf.as_completed(futs)):
            r = f.result()
            (got.extend(r) if r else failed.append(futs[f]))
            if i % 300 == 0:
                print(i, "done", len(failed), "failed", flush=True)
    new = pd.DataFrame(got, columns=store.COLS)
    new = new[new["date"] <= last_complete_session()]

    # split check: overlapping closes must agree with what is stored
    refetch = []
    if not full and len(new):
        cmp = new.merge(old[["sym", "date", "c"]], on=["sym", "date"], suffixes=("", "_old"))
        bad = cmp[(cmp.c / cmp.c_old - 1).abs() > 0.005]
        refetch = sorted(bad.sym.unique())
        print("symbols with changed history (splits or corrections):", len(refetch), refetch[:15], flush=True)
    if refetch:
        full_rows = []
        with cf.ThreadPoolExecutor(THREADS) as ex:
            for s, r in zip(refetch, ex.map(lambda s: fetch(s, "etf" if s == "SPY" else "stocks", "2016-10-01", end), refetch)):
                if r:
                    full_rows.extend(r)
        old = old[~old.sym.isin(refetch)]
        fr = pd.DataFrame(full_rows, columns=store.COLS)
        new = pd.concat([new[~new.sym.isin(refetch)], fr[fr["date"] <= last_complete_session()]])

    merged = pd.concat([old, new]).drop_duplicates(["sym", "date"], keep="last")
    if not full and len(merged) == len(old) and not refetch:
        print("no new rows, price files left untouched")
    elif full:
        merged = merged[merged.sym.isin([s for s, _ in jobs])]
        store.save_months(merged)
    else:
        months = set(new["date"].str[:7]) | {m for m in merged.loc[merged.sym.isin(refetch), "date"].str[:7]}
        store.save_months(merged[merged["date"].str[:7].isin(months)], months)
    print("rows added", len(merged) - len(old), "latest date", merged["date"].max(), "failed symbols", len(failed), failed[:15])
    json.dump({"latest": merged["date"].max(), "failed": failed, "resplit": refetch, "ran": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")},
              open(os.path.join(store.OUT, "update_status.json"), "w"))
    if len(failed) > 0.1 * len(jobs):
        sys.exit("too many failed symbols, not trusting this update")


if __name__ == "__main__":
    main()
