select 'fp', count(*), sum(revision_id), max(revision_id), sum(coalesce(adj_close,0)), md5(string_agg(security_id||date::text||coalesce(adj_close::text,'N')||adj_factor::text||close::text||revision_id::text||coalesce(recorded_at::text,''), ',' order by security_id,date)) from ohlcv_daily;
select 'seq', last_value from data_revision_seq;
select 'hist', count(*) from ohlcv_daily_history;
