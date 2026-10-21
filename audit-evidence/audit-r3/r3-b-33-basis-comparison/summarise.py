"""Summarise pairs.csv (output of pairs.sql). Read-only analysis; no database access.

Usage: summarise.py PAIRS_CSV   (the CSV may start with BEGIN and end with ROLLBACK)
"""
import sys

import pandas as pd

lines = [ln for ln in open(sys.argv[1]) if ln.strip() not in ("BEGIN", "ROLLBACK")]
import io
d = pd.read_csv(io.StringIO("".join(lines)))
print(f"pairs {len(d)}; runs {d.new_run.nunique()}; dates {d.run_date.min()}..{d.run_date.max()}")
c = d.dropna(subset=["old_ret", "obc_ret"]).copy()
c["old_new"] = c.old_ret - c.new_ret
c["defect"] = c.old_ret - c.obc_ret
c["basis"] = c.obc_ret - c.new_ret
print("\n== coverage by horizon")
g = d.groupby("h").agg(pairs=("new_ret", "size"), with_old=("old_ret", "count"), with_obc=("obc_ret", "count"))
g["comparable"] = c.groupby("h").size()
print(g.to_string())
print("\n== all comparable pairs (returns are fractions; 0.01 = 1 point)")
r = c.groupby("h").agg(n=("new_ret", "size"), mean_new=("new_ret", "mean"), mean_obc=("obc_ret", "mean"),
                       mean_old=("old_ret", "mean"), mean_old_minus_new=("old_new", "mean"),
                       mean_defect=("defect", "mean"), mean_basis=("basis", "mean"))
r["gap_gt_5pt"] = c[c.old_new.abs() > 0.05].groupby("h").size()
r["gap_gt_50pt"] = c[c.old_new.abs() > 0.5].groupby("h").size()
r["defect_rows"] = c[c.defect.abs() > 0.001].groupby("h").size()
r["basis_rows"] = c[c.basis.abs() > 0.001].groupby("h").size()
print(r.fillna(0).round(4).to_string())
print("\n== old equals the R3-B-33 raw-exit formula, or the corrected own_bars formula")
c["eq_raw"] = (c.old_ret - c.rawexit_ret).abs() < 0.00006
c["eq_corr"] = (c.old_ret - c.obc_ret).abs() < 0.00006
print(c.groupby("h")[["eq_raw", "eq_corr"]].sum().to_string())
print("\n== 120d, qualified set (rank not null) and Top 25 on the engine-2 runs")
x = c[c.h == 120]
for name, sel in (("qualified", x[x["rank"].notna()]), ("top25", x[x["rank"] <= 25])):
    print(f"{name}: n={len(sel)} mean new {sel.new_ret.mean():.4f}, corrected own_bars {sel.obc_ret.mean():.4f}, "
          f"stored own_bars {sel.old_ret.mean():.4f}; median new {sel.new_ret.median():.4f}, stored {sel.old_ret.median():.4f}")
print("\n== 120d rank correlation (Spearman) of rank with each return, per run, qualified set; mean over runs")
q = x[x["rank"].notna()]
for col in ("new_ret", "obc_ret", "old_ret"):
    ics = [(-1) * g["rank"].corr(g[col], method="spearman") for _, g in q.groupby("new_run") if len(g) > 10]
    print(f"{col}: mean Rank IC {sum(ics)/len(ics):.4f} over {len(ics)} runs")
print("\n== stale exits among the new 120d rows")
y = d[d.h == 120]
print(f"n={len(y)} stale_exit={int((y.stale > 0).sum())}")
