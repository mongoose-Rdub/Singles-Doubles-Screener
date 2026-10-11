import numpy as np, pandas as pd
from exits import load_entries, sim
E, O, H, L, C = load_entries()
c0 = E.c.values.astype(np.float64); atr0 = E.atr.values.astype(np.float64); stop0 = E.stop.values.astype(np.float64)
print("buy and hold, no stop, by tier (average return, per day held, early and late)")
for D in (10, 30, 60):
    r = C[:, D - 1] / c0 - 1
    for tier in ("Double", "Single"):
        m = (E.tier == tier).values
        e = m & (E.date < "2022-01-01").values; l = m & (E.date >= "2022-01-01").values
        print(f"  {tier} {D:>2} days: avg {r[m].mean()*100:5.2f}%  per day {r[m].mean()/D*100:.3f}%  early {r[e].mean()*100:5.2f}%  late {r[l].mean()*100:5.2f}%  median {np.median(r[m])*100:5.2f}%")
def show(label, tier, tg, D, **kw):
    m = (E.tier == tier).values
    p, d = sim(O[m], H[m], L[m], C[m], c0[m], stop0[m], atr0[m], tg, D, **kw)
    bh = C[m][:, D - 1] / c0[m] - 1
    g = pd.DataFrame({"p": p, "d": d, "bh": bh, "date": E.date.values[m]})
    top = g.p.sort_values(ascending=False)
    k = int(len(g) * 0.05)
    print(f"  {label:<46} avg {g.p.mean()*100:5.2f}%  median {g.p.median()*100:5.2f}%  win {100*(g.p>0).mean():4.1f}%  days {g.d.mean():4.1f}  perday {g.p.sum()/g.d.sum()*100:.3f}%  "
          f"share of profit from top 5% trades {top.iloc[:k].sum()/g.p.sum()*100:5.0f}%  beats buy and hold same horizon on {100*(g.p>g.bh).mean():4.1f}% of trades  early {g[g.date<'2022-01-01'].p.mean()*100:.2f}% late {g[g.date>='2022-01-01'].p.mean()*100:.2f}%")
print("\nDOUBLE tier")
show("baseline +20% target, stop, 30 days", "Double", 0.20, 30)
show("no target, trail 4 ATR, 60 days", "Double", None, 60, trail=4.0, trail_start=0.0)
show("no target, trail 3 ATR, 60 days", "Double", None, 60, trail=3.0, trail_start=0.0)
show("no target, trail 3 ATR, 30 days", "Double", None, 30, trail=3.0, trail_start=0.0)
print("\nSINGLE tier")
show("baseline +10% target, stop, 30 days", "Single", 0.10, 30)
show("no target, trail 4 ATR, 60 days", "Single", None, 60, trail=4.0, trail_start=0.0)
show("no target, trail 3 ATR, 30 days", "Single", None, 30, trail=3.0, trail_start=0.0)
