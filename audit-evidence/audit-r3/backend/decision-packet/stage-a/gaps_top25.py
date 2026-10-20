"""Share of today's Top-25 (option A) names with < 95% bar completeness, and their In-Sample forward returns."""
import json
from statistics import mean
import rs_ref as R  # runs the module once (prints); reuse its helpers
from datetime import date
res = []
for run, as_of in sorted(R.runs.items(), key=lambda x: x[1]):
    pops, comp = R.populations(as_of)
    rk = R.ranked(run, R.rs(pops["A"], as_of))
    top = [s for s, _ in rk[:25]]
    gap = [s for s in top if comp.get(s, 0) < .95]
    f = R.fr[(run, 120)]
    g = [f[s] for s in gap if s in f]; n = [f[s] for s in top if s not in gap and s in f]
    res.append(dict(date=str(as_of), gap_names=len(gap), fwd120_gap=mean(g) if g else None, fwd120_nogap=mean(n) if n else None))
print(json.dumps(res, indent=0))
print("mean gap names in Top-25:", mean(r["gap_names"] for r in res))
gg = [r["fwd120_gap"] for r in res if r["fwd120_gap"] is not None]; nn = [r["fwd120_nogap"] for r in res if r["fwd120_nogap"] is not None]
print("mean fwd120 gap names", mean(gg), "n_runs", len(gg), "| no-gap names", mean(nn), "n_runs", len(nn))
