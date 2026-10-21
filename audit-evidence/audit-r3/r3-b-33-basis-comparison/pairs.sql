-- R3-B-33 read-only extraction. One SELECT, no temp table, run inside
-- BEGIN READ ONLY. Every bar read is bounded to date <= 2022-12-30: the sealed
-- hold-out (2023-01-02 to 2025-12-31) is never read.
-- Columns: old_ret = stored own_bars row (latest own_bars run for that date; raw
-- exit close against adjusted entry close, R3-B-33). obc_ret = own_bars basis
-- recomputed with the exit adjusted (h-th own bar after the entry bar).
-- new_ret = sessions row of runs 151-170. rawexit_ret = raw exit close over the
-- adjusted entry close, to test the R3-B-33 formula.
-- old_ret is a stored value. summarise.py drops every pair whose own-bar exit is
-- missing (a bar after 2022-12-30 was not read), so no statistic uses a return
-- whose exit lies in the hold-out.
-- Run: BEGIN READ ONLY; COPY (<this query>) TO STDOUT WITH CSV HEADER; ROLLBACK;
--      then: python summarise.py pairs.csv > summary.txt (pairs.csv is not kept: 151,611 rows).
WITH pairs AS (
  SELECT f.run_id AS new_run, r.run_date, f.security_id, f.horizon_days AS h,
         f.forward_return AS new_ret, f.exit_stale_sessions AS stale
  FROM forward_returns f JOIN screening_runs r ON r.id = f.run_id
  WHERE f.horizon_basis = 'sessions' AND f.run_id BETWEEN 151 AND 170
), old_run AS (
  SELECT run_date, max(id) AS old_run FROM screening_runs sr
  WHERE strategy_id = 8 AND id BETWEEN 14 AND 142 AND run_date <= '2022-06-30'
    AND EXISTS (SELECT 1 FROM forward_returns x WHERE x.run_id = sr.id AND x.horizon_basis = 'own_bars')
  GROUP BY run_date
), entry AS (
  SELECT p.*, e.date AS entry_date, e.close * e.adj_factor AS entry_adj
  FROM pairs p
  JOIN LATERAL (SELECT date, close, adj_factor FROM ohlcv_daily o
                WHERE o.security_id = p.security_id AND o.date <= p.run_date
                ORDER BY o.date DESC LIMIT 1) e ON true
)
SELECT p.new_run, p.run_date, p.security_id, p.h, p.new_ret, p.stale, s.rank,
       old.forward_return AS old_ret,
       (x.close * x.adj_factor / p.entry_adj - 1) AS obc_ret,
       (x.close / p.entry_adj - 1) AS rawexit_ret
FROM entry p
JOIN old_run ON old_run.run_date = p.run_date
LEFT JOIN screening_results s ON s.run_id = p.new_run AND s.security_id = p.security_id
LEFT JOIN forward_returns old ON old.run_id = old_run.old_run AND old.security_id = p.security_id
     AND old.horizon_days = p.h AND old.horizon_basis = 'own_bars'
LEFT JOIN LATERAL (SELECT close, adj_factor FROM ohlcv_daily o
                   WHERE o.security_id = p.security_id AND o.date > p.entry_date AND o.date <= '2022-12-30'
                   ORDER BY o.date OFFSET (p.h - 1) LIMIT 1) x ON true
ORDER BY p.new_run, p.security_id, p.h;
