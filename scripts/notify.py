"""Posts to Discord through a webhook. The address is read from the DISCORD_WEBHOOK_URL environment variable
(a GitHub Actions secret). It is never stored in this repo.

  python scripts/notify.py daily     post only when something needs a look
  python scripts/notify.py weekly    post the week's plan (top names per tier)
  python scripts/notify.py failed    post that a scheduled run failed
"""
import json
import os
import sys
import urllib.request

import store

SITE = os.environ.get("SITE_URL", "https://singles-doubles-screener.mongoose-rdub.workers.dev")
NAME = "Singles and Doubles"
MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
RED, AMBER, BLUE, GREEN, ORANGE = 0xC62828, 0xE0A100, 0x2557D6, 0x13804A, 0xD9480F


def nice(iso):
    if not iso:
        return "n/a"
    y, m, d = iso[:10].split("-")
    return f"{MON[int(m) - 1]} {int(d)}, {y}"


def post(embeds, content=None):
    url = os.environ.get("DISCORD_WEBHOOK_URL", "").strip()
    if not url:
        print("no webhook set, skipping")
        return
    body = {"username": NAME, "embeds": embeds}
    if content:
        body["content"] = content
    req = urllib.request.Request(url + "?wait=true", data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json", "User-Agent": "SinglesDoublesBot/1.0"})
    print("discord status", urllib.request.urlopen(req, timeout=30).status)


def jload(name):
    return json.load(open(os.path.join(store.OUT, name)))


def daily():
    a = jload("attention.json")
    flags = a.get("flags", [])
    if not flags:
        print("nothing to report, no post")
        return
    c = a["counts"]
    lines = []
    for level, label in (("act", "Act"), ("watch", "Watch"), ("info", "For information")):
        items = [f for f in flags if f["level"] == level]
        if items:
            lines.append(f"**{label}**")
            lines += [f"`{f['symbol']}` {f['kind']}: {f['text']}" for f in items[:12]]
            lines.append("")
    color = RED if c["act"] else AMBER if c["watch"] else BLUE
    m = a.get("market", {})
    foot = f"Data through {nice(a['asof'])}"
    if m.get("spy"):
        foot += f"  |  SPY {'above' if m['above200'] else 'below'} its 200 day average"
    post([{"title": "Daily check", "url": SITE, "description": "\n".join(lines)[:3900], "color": color, "footer": {"text": foot}}])


def weekly():
    a = jload("attention.json")
    s = jload("summary.json")[0]
    plan = [r for r in a["rows"] if r["source"] == "plan"]
    embeds = [{"title": "Weekly plan", "url": SITE, "color": GREEN,
               "description": f"Data through {nice(s['asof'])}. {s['tier_double']} Doubles and {s['tier_single']} Singles qualify. "
                              f"Tracking the top 25 of each tier below.",
               "fields": []}]
    for tier, col in (("Double", ORANGE), ("Single", BLUE)):
        top = sorted([r for r in plan if r["tier"] == tier], key=lambda r: -r["score"])[:10]
        text = "\n".join(f"`{r['symbol']}` ${r['price']:.2f}  stop ${r['stop']:.2f}  target ${r['target']:.2f}" for r in top)
        embeds.append({"title": f"Top {tier}s (target {'+20%' if tier == 'Double' else '+10%'})", "description": text or "None", "color": col})
    embeds[-1]["footer"] = {"text": "Ordered by priority score. Full list on the dashboard."}
    post(embeds)


def failed():
    run = os.environ.get("RUN_URL", "")
    post([{"title": "Scheduled run failed", "description": f"The {sys.argv[2] if len(sys.argv) > 2 else 'scheduled'} run did not finish. Check the run log: {run}", "color": RED}])


if __name__ == "__main__":
    {"daily": daily, "weekly": weekly, "failed": failed}[sys.argv[1]]()
