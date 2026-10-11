"""Builds universe.json: every US listed stock with a market cap of $2B or more, from Nasdaq's public screener.
Run first. Output is read by fetch_data.py, engine.py and screener.py."""
import json
import urllib.request

H = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
URL = "https://api.nasdaq.com/api/screener/stocks?tableonly=true&limit=10000&offset=0&download=true"
MIN_MCAP = 2e9


def main(out=None):
    import store
    out = out or store.UNIVERSE
    rows = json.load(urllib.request.urlopen(urllib.request.Request(URL, headers=H), timeout=60))["data"]["rows"]

    def mcap(r):
        try:
            return float(r["marketCap"])
        except Exception:
            return 0.0

    big = [r for r in rows if mcap(r) >= MIN_MCAP and "^" not in r["symbol"] and "/" not in r["symbol"]]
    json.dump(big, open(out, "w"))
    print("stocks listed", len(rows), "kept over $2B", len(big))


if __name__ == "__main__":
    main()
