"""Daily attention note and weekly plan tracking.

  python scripts/attention.py --set-plan   weekly: freeze the current top 25 per tier as this week's plan
  python scripts/attention.py              daily: check the plan and any positions you listed, flag what needs a look

Reads output/candidates.json (from screener.py), output/plan.json, data/positions.json (optional, yours).
Writes output/attention.json and output/prev_symbols.json.
"""
import datetime as dt
import json
import os
import sys

import numpy as np
import pandas as pd
import store

TOP_N = 25
HOLD_DAYS = 30
NEAR_STOP = 0.25      # flag when price has used 75% of the room to the stop
BIG_MOVE = 5.0        # minimum one day move in percent
ATR_MULT = 2.5        # and at least this many typical daily ranges
NEW_SCORE = 90        # new entrants must score at least this to be listed


def jload(path, default):
    try:
        return json.load(open(path))
    except Exception:
        return default


def main():
    cands = jload(os.path.join(store.OUT, "candidates.json"), [])
    summ = jload(os.path.join(store.OUT, "summary.json"), [{}])[0]
    asof = summ.get("asof")
    plan_path = os.path.join(store.OUT, "plan.json")

    if "--set-plan" in sys.argv:
        entries = []
        for tier in ("Double", "Single"):
            top = sorted([c for c in cands if c["tier"] == tier], key=lambda c: -c["score"])[:TOP_N]
            for c in top:
                entries.append({k: c[k] for k in ("symbol", "name", "sector", "tier", "score", "price", "stop", "target", "stop_pct", "odds", "atr_pct")})
        json.dump({"date": asof, "entries": entries}, open(plan_path, "w"))
        print("plan set", asof, len(entries))

    plan = jload(plan_path, {"date": asof, "entries": []})
    positions = jload(os.path.join(store.ROOT, "data", "positions.json"), [])
    df = store.load_frame()
    df = df[df.sym.isin({e["symbol"] for e in plan["entries"]} | {p["symbol"] for p in positions} | {"SPY"})]
    dates = sorted(df.date.unique())

    def track(sym, start, stop, target, entry):
        g = df[(df.sym == sym) & (df.date > start)].sort_values("date")
        res = {"last": None, "chg1d": None, "status": "open", "event_date": None, "days": int(len(g))}
        gl = df[df.sym == sym].sort_values("date")
        if len(gl):
            res["last"] = float(gl.c.iloc[-1])
            if len(gl) > 1:
                res["chg1d"] = round(float((gl.c.iloc[-1] / gl.c.iloc[-2] - 1) * 100), 1)
        for _, r in g.iterrows():
            if r.l <= stop:
                res.update(status="stopped", event_date=r.date)
                break
            if r.h >= target:
                res.update(status="target", event_date=r.date)
                break
        if res["status"] == "open" and res["days"] > HOLD_DAYS:
            res["status"] = "expired"
        if res["last"]:
            res["pnl_pct"] = round((res["last"] / entry - 1) * 100, 1)
            room = entry - stop
            res["room_left"] = round(float((res["last"] - stop) / room), 2) if room > 0 else None
            res["to_target_pct"] = round((target / res["last"] - 1) * 100, 1)
        return res

    flags, rows = [], []
    for e in plan["entries"]:
        t = track(e["symbol"], plan["date"], e["stop"], e["target"], e["price"])
        rows.append({**e, **t, "source": "plan"})
    for p in positions:
        t = track(p["symbol"], p.get("date", plan["date"]), p["stop"], p["target"], p["entry"])
        rows.append({"symbol": p["symbol"], "name": p.get("name", ""), "tier": p.get("tier", ""), "price": p["entry"], "stop": p["stop"],
                     "target": p["target"], **t, "source": "position"})

    for r in rows:
        who = "Your position" if r["source"] == "position" else "Plan name"
        if r["status"] == "stopped":
            fresh = r["event_date"] == asof
            flags.append({"level": "act" if fresh else "info", "symbol": r["symbol"], "kind": "Stop hit",
                          "text": f"{who} traded through its stop of ${r['stop']:.2f} on {r['event_date']}."})
        elif r["status"] == "target":
            fresh = r["event_date"] == asof
            flags.append({"level": "act" if fresh else "info", "symbol": r["symbol"], "kind": "Target reached",
                          "text": f"{who} reached its target of ${r['target']:.2f} on {r['event_date']}."})
        elif r["status"] == "open":
            if r.get("room_left") is not None and r["room_left"] < NEAR_STOP:
                flags.append({"level": "watch", "symbol": r["symbol"], "kind": "Near stop",
                              "text": f"{who} is within {r['room_left'] * 100:.0f}% of the room above its stop (last ${r['last']:.2f}, stop ${r['stop']:.2f})."})
            lim = max(BIG_MOVE, ATR_MULT * (r.get("atr_pct") or 0))
            if r["chg1d"] is not None and r["days"] > 0 and abs(r["chg1d"]) >= lim:
                up = r["chg1d"] > 0
                flags.append({"level": "info" if up else "watch", "symbol": r["symbol"], "kind": "Big move up" if up else "Big move down",
                              "text": f"{who} moved {'up' if up else 'down'} {abs(r['chg1d']):.1f}% on the day, well beyond its typical daily range."})

    # new entrants: in a tier now, not in the previous run
    prev = set(jload(os.path.join(store.OUT, "prev_symbols.json"), []))
    now_syms = {c["symbol"] for c in cands}
    in_plan = {e["symbol"] for e in plan["entries"]}
    new = sorted([c for c in cands if c["symbol"] not in prev and c["symbol"] not in in_plan and c["score"] >= NEW_SCORE], key=lambda c: -c["score"])[:10] if prev else []
    for c in new:
        flags.append({"level": "info", "symbol": c["symbol"], "kind": "New entrant",
                      "text": f"Newly in the {c['tier']} tier with priority score {c['score']:.0f} (range {c['atr_pct']:.1f}%, stop {c['stop_pct']:.0f}% below)."})

    # market backdrop
    spy = df[df.sym == "SPY"].sort_values("date")
    market = {}
    if len(spy) > 200:
        c = spy.c.reset_index(drop=True)
        sma200, sma50 = c.rolling(200).mean().iloc[-1], c.rolling(50).mean().iloc[-1]
        above_prev = c.iloc[-2] > c.rolling(200).mean().iloc[-2]
        market = {"spy": round(float(c.iloc[-1]), 2), "vs200": round(float((c.iloc[-1] / sma200 - 1) * 100), 1),
                  "vs50": round(float((c.iloc[-1] / sma50 - 1) * 100), 1), "chg5d": round(float((c.iloc[-1] / c.iloc[-6] - 1) * 100), 1),
                  "above200": bool(c.iloc[-1] > sma200), "pct_above50": summ.get("pct_above50")}
        if bool(above_prev) != market["above200"]:
            flags.append({"level": "act", "symbol": "SPY", "kind": "Regime change",
                          "text": "SPY crossed " + ("above" if market["above200"] else "below") + " its 200 day average."})

    order = {"act": 0, "watch": 1, "info": 2}
    flags.sort(key=lambda f: order[f["level"]])
    out = {"asof": asof, "generated": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), "plan_date": plan["date"],
           "market": market, "flags": flags, "rows": rows,
           "counts": {"act": sum(f["level"] == "act" for f in flags), "watch": sum(f["level"] == "watch" for f in flags),
                      "info": sum(f["level"] == "info" for f in flags), "plan": len(plan["entries"]), "positions": len(positions)}}
    json.dump(out, open(os.path.join(store.OUT, "attention.json"), "w"))
    json.dump(sorted(now_syms), open(os.path.join(store.OUT, "prev_symbols.json"), "w"))
    print(json.dumps(out["counts"]), "flags", len(flags))
    for f in flags[:12]:
        print(f["level"], f["symbol"], f["kind"], f["text"])


if __name__ == "__main__":
    main()
