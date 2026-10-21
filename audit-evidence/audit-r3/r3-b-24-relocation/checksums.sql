-- usage: psql -At -v sch=public|research_archive -f checksums.sql
-- Row count and an order-independent md5 per table. The view md5 ignores the schema prefix:
-- a view that reads another moved view shows the new schema name in its text.
select 'ohlcv_adj_snapshot_20260810', count(*), md5(string_agg(md5(t::text), '' order by md5(t::text))) from :"sch".ohlcv_adj_snapshot_20260810 t;
select 'screening_results_snapshot_20260810', count(*), md5(string_agg(md5(t::text), '' order by md5(t::text))) from :"sch".screening_results_snapshot_20260810 t;
select 'corporate_actions_snapshot_20260810', count(*), md5(string_agg(md5(t::text), '' order by md5(t::text))) from :"sch".corporate_actions_snapshot_20260810 t;
select 'screening_results_snapshot_run12_20260810', count(*), md5(string_agg(md5(t::text), '' order by md5(t::text))) from :"sch".screening_results_snapshot_run12_20260810 t;
select 'screening_runs_snapshot_run12_20260810', count(*), md5(string_agg(md5(t::text), '' order by md5(t::text))) from :"sch".screening_runs_snapshot_run12_20260810 t;
select 'view:'||c.relname, md5(replace(pg_get_viewdef(c.oid), 'research_archive.', '')) from pg_class c join pg_namespace n on n.oid=c.relnamespace where c.relkind='v' and n.nspname=:'sch' and c.relname in ('v_adjfix_pairs','v_adjfix_diff','v_live_diff') order by 1;
select 'index', count(*) from pg_indexes where schemaname=:'sch' and tablename ~ 'snapshot';
-- live data that the views read must not move
select 'public_core', (select count(*) from public.screening_runs), (select count(*) from public.screening_results), (select count(*) from public.ohlcv_daily), (select count(*) from public.forward_returns);
