"""Builds site/index.html (the standalone dashboard for Cloudflare) from output/*.json and site/template.html."""
import json
import os
import store

NAMES = ["summary", "candidates", "odds", "byyear", "signals", "exits", "attention"]


def main():
    data = {}
    for n in NAMES:
        p = os.path.join(store.OUT, n + ".json")
        data[n] = json.load(open(p)) if os.path.exists(p) else None
    blob = json.dumps(data, separators=(",", ":")).replace("</", "<\\/")
    tpl = open(os.path.join(store.ROOT, "site", "template.html"), encoding="utf-8").read()
    html = tpl.replace("/*__DATA__*/null", blob)
    out = os.path.join(store.ROOT, "site", "index.html")
    open(out, "w", encoding="utf-8").write(html)
    print("wrote", out, round(len(html) / 1024), "KB")


if __name__ == "__main__":
    main()
