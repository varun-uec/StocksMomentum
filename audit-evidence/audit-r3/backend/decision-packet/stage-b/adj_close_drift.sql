-- R3-B-30: the bars whose stored adj_close is not close x adj_factor (read-only).
\pset footer off
\echo '== By factor and size of the gap =='
select adj_factor = 1 as factor_is_1,
       count(*) as bars, count(distinct security_id) as securities,
       min(date) as first, max(date) as last,
       round(percentile_cont(0.5) within group (order by abs(adj_close / nullif(round(close * adj_factor, 4), 0) - 1))::numeric, 6) as median_rel_gap,
       round(max(abs(adj_close / nullif(round(close * adj_factor, 4), 0) - 1))::numeric, 6) as max_rel_gap
from ohlcv_daily
where adj_close is not null and abs(adj_close - round(close * adj_factor, 4)) > 0.0001
group by 1 order by 1;
\echo '== Is the stored adj_close the close times an older factor? (top 10 securities) =='
select s.symbol, b.security_id, count(*) as bars, min(b.date) as first, max(b.date) as last,
       round(min(b.adj_close / nullif(b.close, 0)), 6) as stored_ratio_min,
       round(max(b.adj_close / nullif(b.close, 0)), 6) as stored_ratio_max,
       min(b.adj_factor) as factor_min, max(b.adj_factor) as factor_max
from ohlcv_daily b join securities s on s.id = b.security_id
where b.adj_close is not null and abs(b.adj_close - round(b.close * b.adj_factor, 4)) > 0.0001
group by s.symbol, b.security_id order by bars desc limit 10;
