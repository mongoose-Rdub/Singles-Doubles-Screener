"""Pulls the full 10 years of daily bars (the most Nasdaq's public API provides) for every
US stock with market cap >= $2B, plus SPY as a market reference. Saves bars10y.pkl."""
import json, time, pickle, concurrent.futures as cf, urllib.request
H = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
FROM, TO = "2016-10-01", "2026-10-11"

def get(url, tries=5):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=H)
            return json.load(urllib.request.urlopen(req, timeout=60))
        except Exception:
            time.sleep(1.5 * (i + 1))
    return None

def num(s):
    try: return float(str(s).replace('$', '').replace(',', ''))
    except Exception: return None

def bars(arg):
    sym, cls = arg
    d = get(f"https://api.nasdaq.com/api/quote/{sym}/historical?assetclass={cls}&fromdate={FROM}&todate={TO}&limit=10000")
    try: rows = d['data']['tradesTable']['rows']
    except Exception: return sym, None
    out = []
    for r in rows:
        v = [num(r[k]) for k in ('open', 'high', 'low', 'close', 'volume')]
        if None in v: continue
        m, dd, y = r['date'].split('/')
        out.append((f"{y}-{m}-{dd}", *v))
    out.sort()
    return sym, out

if __name__ == "__main__":
    uni = json.load(open('universe.json'))
    jobs = [(r['symbol'], 'stocks') for r in uni] + [('SPY', 'etf')]
    data, missing = {}, []
    with cf.ThreadPoolExecutor(10) as ex:
        for i, (s, b) in enumerate(ex.map(bars, jobs)):
            if b: data[s] = b
            else: missing.append(s)
            if i % 200 == 0: print(i, len(data), flush=True)
    pickle.dump(data, open('bars10y.pkl', 'wb'))
    print("done", len(data), "missing", len(missing), missing[:20])
