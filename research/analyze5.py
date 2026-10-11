import warnings, numpy as np, pandas as pd
warnings.filterwarnings("ignore")
exec(open("analyze3.py").read().split("D = P[")[0])
A = P[P.res_d.notna() & P.res_s.notna()].copy()
A["R_d"] = A.pnl_d / A.stop_pct; A["R_s"] = A.pnl_s / A.stop_pct
A["bucket"] = pd.cut(A.atr_pct, [0, .018, .022, .028, .033, .040, .050, 1.0])
def line(g, r, p, R):
    return pd.Series(dict(n=len(g), win=(g[r] == 1).mean() * 100, stop=(g[r] == -1).mean() * 100, pnl=g[p].mean() * 100, R=g[R].mean(), stop_pct=g.stop_pct.mean() * 100))
print("DOUBLE target (+20%) by daily range bucket, all liquid stocks 2018 to 2026")
print(A.groupby("bucket", observed=True).apply(lambda g: line(g, "res_d", "pnl_d", "R_d")).round(2))
print("\nSINGLE target (+10%) by daily range bucket")
print(A.groupby("bucket", observed=True).apply(lambda g: line(g, "res_s", "pnl_s", "R_s")).round(2))
A["dr_bucket"] = pd.cut(A.double_rate, [-.01, .02, .08, .15, .25, .4, 1.0])
print("\nDOUBLE target by past 20% window record (daily range 3.3% or more only)")
print(A[A.atr_pct >= .033].groupby("dr_bucket", observed=True).apply(lambda g: line(g, "res_d", "pnl_d", "R_d")).round(2))
A["sr_bucket"] = pd.cut(A.single_rate, [-.01, .15, .30, .45, .6, .75, 1.0])
print("\nSINGLE target by past 10% window record (daily range 2.2 to 3.3% only)")
print(A[(A.atr_pct >= .022) & (A.atr_pct < .033)].groupby("sr_bucket", observed=True).apply(lambda g: line(g, "res_s", "pnl_s", "R_s")).round(2))
print("\nUniverse average, all liquid stocks: double target pnl %.2f, single target pnl %.2f" % (A.pnl_d.mean() * 100, A.pnl_s.mean() * 100))
