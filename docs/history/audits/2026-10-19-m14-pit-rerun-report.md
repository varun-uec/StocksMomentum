# M14.7 Report — Past Research Re-run Through the Point-in-Time Path

> **Date:** 2026-10-19 · **Branch:** `wickstreet/m10-m11` · **Requirement:** ADR-014 Consequences ("M14 re-runs a sample and reports the differences before the Studio ships") · **Script:** `backend/scripts/m14_pit_rerun.py` · **Data:** E2E copy `momentum25_e2e`, read only, data revision 0

## Verdict

- The point-in-time path changes past selections moderately. Across 8 sampled runs, the qualified set keeps 84–98% of its names (Jaccard), and 22–25 of the Top-25 stay the same.
- The changes come from three causes. Two of them were known gaps that the point-in-time path fixes. The third was a defect on every path, live production included. It is now fixed (`18cab43`).
- Code drift since the runs were stored is often larger than the point-in-time effect. On 2023-02-28 only 8 of the stored Top-25 survive today's code. So no past result should be quoted without re-running it.

## Method

The sample is 8 of the 65 runs in the `adjfix-recheck` series of `minervini_trend_template` (strategy 8 in the copy), the series the 2026-08-10 ranking report used. They are spread evenly from 2020-11-27 to 2026-02-27. Each run date gets three selections:

1. **stored**: the run as saved;
2. **live**: today's historical path, with the stored cumulative `adj_factor` and today's universe;
3. **pit**: the point-in-time path, with factors from corporate actions whose ex-date falls on or before the date, and the universe listed and not delisted by then.

stored → live measures code drift. live → pit measures the point-in-time effect alone. The audit ran before the RS fix below. That fix changes the live and pit paths equally, so it does not change the live → pit comparison.

## Results

| Run date | Qualified: stored / live / pit | Jaccard stored–live | Jaccard live–pit | Top-25 kept, stored→live | Top-25 kept, live→pit |
|---|---|---|---|---|---|
| 2020-11-27 | 191 / 200 / 190 | 0.889 | 0.950 | 25 | 24 |
| 2021-08-31 | 171 / 169 / 152 | 0.988 | 0.899 | 24 | 22 |
| 2022-05-31 | 121 / 119 / 109 | 0.983 | 0.869 | 25 | 24 |
| 2023-02-28 | 148 / 161 / 141 | 0.850 | 0.841 | **8** | 25 |
| 2023-11-30 | 385 / 366 / 362 | 0.951 | 0.978 | 24 | 23 |
| 2024-08-30 | 364 / 335 / 321 | 0.920 | 0.958 | 25 | 23 |
| 2025-05-30 | 119 / 119 / 123 | 0.763 | 0.936 | 24 | 24 |
| 2026-02-27 | 165 / 135 / 130 | 0.818 | 0.963 | 22 | 24 |

The point-in-time path qualifies fewer names in 7 of 8 runs (by up to 17).

Gate verdicts that changed between live and pit, over every name that entered or left the qualified set:

| Gate | Changes |
|---|---|
| `tt_close_above_sma50` | 53 |
| `tt_rs_rating_min` | 30 |
| `vol_liquidity_min` | 24 |
| `tt_close_above_sma150_200` | 3 |
| Screened by one path only (universe) | 3 |

## Causes

1. **Raw close against adjusted averages (fixed by the point-in-time path).** The trend-template rules compare the raw latest close with adjusted SMAs and 52-week levels.
   - On the live daily run the latest bar's factor is 1, so this is correct.
   - On today's historical path, any split after the decision scales every earlier bar, so the SMAs shrink while the close stays raw. JASH on 2021-08-31: SMA50 107.8 on the historical path, 539.2 point in time, raw close about 539. `close > SMA50` passes trivially, and names qualify that never did at the time. This is the ADR-014 Context §5 gap. The point-in-time path computes factors as of the decision, so the latest factor is 1 and the comparison is honest.
2. **The universe at the date.** The point-in-time universe drops names delisted by the decision. Because RS rating is a percentile across the universe, a different universe moves ratings near the 70 floor. Names with identical indicators on both paths (FORTIS, ALPHAGEO, 2021-08-31) still flip on `tt_rs_rating_min` for this reason.
3. **RS ratings on raw closes: a defect on every path (fixed, `18cab43`).** `compute_universe_rs_ratings` measured returns on raw closes, so a split inside the 252-session lookback read as a crash. MCX (1:5 split on 2026-01-02) showed a 12-month return of −76% instead of +20%.
   - It affected the live daily run as well as research and the Studio.
   - On the latest session in the copy (2026-08-07), 107 of 2,432 names had a split or bonus in the past year. With the fix, 71 of 2,882 rated names move by 10 or more points.
   - 28 names that failed the RS ≥ 70 gate now pass (MBAPL 2 → 92, SILVERTUC 4 → 93, KRISHANA 2 → 90). No name loses the gate.

The liquidity gate moves for a related reason. The historical path scales volume by the later factor, the point-in-time path does not, and averaged turnover then differs near the ₹1 crore floor.

## What this means

- **Past research that used today's historical path is biased toward names with later splits and bonuses.** Those names passed price gates they would have failed at the time. RP-000 to RP-007 and the 2026-08-10 report were run on that path. Their headline findings, that the ranking IC is negative and every recomposition failed on hold-out, rest on the qualified set, which keeps 84–98% of its names. These findings are probably robust, but they are not re-measured here.
- **The Studio uses only the point-in-time path**, with the RS fix. Its results do not carry causes 1 or 3.
- **Production.** The RS fix changes which names qualify on the live daily run. The owner's running instance (image `cb0da94`) keeps the old behaviour until it is rebuilt.

## Open items for the owner

1. **Deploy the RS fix?** It corrects a defect, and 28 names move across the gate on the latest session. It changes the production Top-25 once rebuilt. Default taken: fixed on the branch, not deployed.
2. **Re-route the existing historical research tools to the point-in-time path?** ADR-014 says the port also fixes existing research. Re-routing changes numbers that earlier reports quote. Default taken: not re-routed. The Studio uses the point-in-time path; the older tools still use today's historical path.
3. **Latent risk, not seen in the data.** If a corporate action with a future ex-date were stored, the stored factors would scale today's bars on the live run, and cause 1 would reach production. The copy holds no such action today.
