\set ON_ERROR_STOP on
BEGIN;
CREATE TEMP TABLE pre ON COMMIT DROP AS
  SELECT security_id, date, adj_close AS old_adj, round(close*adj_factor,4) AS expected, revision_id AS rev, recorded_at AS rec
  FROM ohlcv_daily WHERE adj_close IS NOT NULL AND adj_close <> round(close*adj_factor,4);
SELECT 'pre_rows', count(*) FROM pre;
DO $$ BEGIN IF (SELECT count(*) FROM pre) <> 56134 THEN RAISE EXCEPTION 'pre-change row count is not 56134'; END IF; END $$;
UPDATE ohlcv_daily o SET adj_close = round(o.close*o.adj_factor,4)
  FROM pre p WHERE o.security_id=p.security_id AND o.date=p.date;
SELECT 'updated_ok', count(*) FROM pre p JOIN ohlcv_daily o USING (security_id,date) WHERE o.adj_close = p.expected AND o.adj_close <> p.old_adj;
SELECT 'revision_moved', count(*) FROM pre p JOIN ohlcv_daily o USING (security_id,date) WHERE o.revision_id<>p.rev OR o.recorded_at IS DISTINCT FROM p.rec;
SELECT 'remaining_mismatch', count(*) FROM ohlcv_daily WHERE adj_close IS NOT NULL AND adj_close <> round(close*adj_factor,4);
SELECT 'max_abs_change', max(abs(o.adj_close-p.old_adj)) FROM pre p JOIN ohlcv_daily o USING (security_id,date);
DO $$ BEGIN
 IF (SELECT count(*) FROM pre p JOIN ohlcv_daily o USING (security_id,date) WHERE o.adj_close=p.expected AND o.adj_close<>p.old_adj) <> 56134 THEN RAISE EXCEPTION 'expected-value check failed'; END IF;
 IF (SELECT count(*) FROM pre p JOIN ohlcv_daily o USING (security_id,date) WHERE o.revision_id<>p.rev OR o.recorded_at IS DISTINCT FROM p.rec) <> 0 THEN RAISE EXCEPTION 'trigger moved revision_id'; END IF;
END $$;
