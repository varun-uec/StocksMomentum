"""Independent IS / hold-out boundary reference (no momentum25 import).

Rule (ADR-014 §5): hold-out = latest 36-month block on a grid from 2020-01-01
that the data fully covers and whose last decision has a 120-session forward
window. In-sample = session[277] .. the last decision whose 120-session forward
window ends before the hold-out starts.
"""
import sys
from datetime import date

s = [date.fromisoformat(x) for x in open(sys.argv[1]).read().split()]
def block(k):
    y0 = 2020 + 3 * k
    return date(y0, 1, 1), date(y0 + 3, 1, 1)
hold = None
k = 0
while True:
    a, b = block(k)
    inside = [d for d in s if a <= d < b]
    if not inside or s[0] > a or s[-1] < b:
        break
    after = [d for d in s if d > inside[-1]]
    if len(after) < 120:
        break
    hold = (inside[0], inside[-1]); k += 1
before = [d for d in s if d < hold[0]]
is_end = before[len(before) - 121]
# forward window of the last IS decision: 120 sessions later
idx = s.index(is_end)
print({"sessions": len(s), "first": s[0].isoformat(), "last": s[-1].isoformat(),
       "holdout": [hold[0].isoformat(), hold[1].isoformat()],
       "holdout_exit_of_last_decision": [d for d in s if d > hold[1]][119].isoformat(),
       "in_sample": [s[277].isoformat(), is_end.isoformat()],
       "last_is_forward_exit": s[idx + 120].isoformat(),
       "gap_ok": s[idx + 120] < hold[0]})
