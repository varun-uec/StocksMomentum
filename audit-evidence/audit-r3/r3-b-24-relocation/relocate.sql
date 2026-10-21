-- Move (never drop) the five snapshot tables and three views to research_archive. One transaction.
begin;
create schema if not exists research_archive;
alter view  public.v_adjfix_diff  set schema research_archive;
alter view  public.v_adjfix_pairs set schema research_archive;
alter view  public.v_live_diff    set schema research_archive;
alter table public.ohlcv_adj_snapshot_20260810               set schema research_archive;
alter table public.screening_results_snapshot_20260810       set schema research_archive;
alter table public.corporate_actions_snapshot_20260810       set schema research_archive;
alter table public.screening_results_snapshot_run12_20260810 set schema research_archive;
alter table public.screening_runs_snapshot_run12_20260810    set schema research_archive;
commit;
