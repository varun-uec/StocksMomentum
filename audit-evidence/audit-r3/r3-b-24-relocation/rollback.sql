-- Move everything back to public. The schema is kept (empty) so a rerun of relocate.sql is a no-op create.
begin;
alter table research_archive.ohlcv_adj_snapshot_20260810               set schema public;
alter table research_archive.screening_results_snapshot_20260810       set schema public;
alter table research_archive.corporate_actions_snapshot_20260810       set schema public;
alter table research_archive.screening_results_snapshot_run12_20260810 set schema public;
alter table research_archive.screening_runs_snapshot_run12_20260810    set schema public;
alter view  research_archive.v_adjfix_pairs set schema public;
alter view  research_archive.v_adjfix_diff  set schema public;
alter view  research_archive.v_live_diff    set schema public;
commit;
