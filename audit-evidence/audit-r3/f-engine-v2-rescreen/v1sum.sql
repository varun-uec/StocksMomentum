select 'screening_runs', count(*), md5(string_agg(t::text, '|' order by id)) from screening_runs t where id<=150
union all select 'screening_results', count(*), md5(string_agg(t::text, '|' order by run_id, security_id)) from screening_results t where run_id<=150
union all select 'universe_membership', count(*), md5(string_agg(t::text, '|' order by run_id, security_id)) from universe_membership t where run_id<=150
union all select 'forward_returns', count(*), md5(string_agg(t::text, '|' order by run_id, security_id, horizon_days, horizon_basis)) from forward_returns t where run_id<=150
union all select 'ohlcv_daily', count(*), md5(string_agg(t::text, '|' order by security_id, date)) from ohlcv_daily t;
