select count(*) total, count(*) filter (where o2.adj_factor<>1) exit_factor_not_1,
  count(*) filter (where abs(round(o2.close*o2.adj_factor/(e.close*e.adj_factor)-1,4)-f.forward_return)>0.0001) mismatches,
  count(*) filter (where o2.adj_factor<>1 and abs(round(o2.close*o2.adj_factor/(e.close*e.adj_factor)-1,4)-f.forward_return)>0.0001) mismatches_on_adjusted,
  count(*) filter (where o2.adj_factor<>1 and abs(round(o2.close/(e.close*e.adj_factor)-1,4)-f.forward_return)<=0.0001) would_match_raw_exit_bug
from forward_returns f join screening_runs r on r.id=f.run_id
join ohlcv_daily o2 on o2.security_id=f.security_id and o2.date=f.exit_date
join lateral (select close, adj_factor from ohlcv_daily o where o.security_id=f.security_id and o.date<=r.run_date order by o.date desc limit 1) e on true
where f.run_id>150 and f.horizon_basis='sessions' and f.exit_stale_sessions=0;
