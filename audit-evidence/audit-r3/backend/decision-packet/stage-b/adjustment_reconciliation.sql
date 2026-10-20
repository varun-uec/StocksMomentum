-- R3-B-30 reconciliation of stored adjustment values and dates (read-only).
-- Run with default_transaction_read_only=on (adjustment_reconciliation.sh).
-- Expected factor of a bar on d (IMPLEMENTATION_SPEC §8, compute_adjustment_factors):
-- the product of every priced action's ratio with ex_date > d; 1 without one.
\pset footer off
\echo '== Bars and adjusted closes =='
select count(*) as bars,
       count(*) filter (where adj_close is null) as adj_close_null,
       count(*) filter (where adj_close is null and adj_factor <> 1) as adj_close_null_factor_not_1,
       count(*) filter (where adj_close is not null
                          and abs(adj_close - round(close * adj_factor, 4)) > 0.0001) as adj_close_not_close_x_factor
from ohlcv_daily;

\echo '== Actions =='
select type, count(*) as actions, count(*) filter (where ratio is null) as unpriced,
       count(distinct security_id) as securities
from corporate_actions group by type order by type;

\echo '== Stored adj_factor against the factor the actions imply =='
with expected as (
  select b.security_id, b.date, b.adj_factor,
         coalesce((select exp(sum(ln(a.ratio)))
                   from corporate_actions a
                   where a.security_id = b.security_id and a.ratio is not null
                     and a.ex_date > b.date), 1)::numeric as want
  from ohlcv_daily b)
select count(*) as bars_compared,
       count(*) filter (where abs(adj_factor - want) > 1e-6 * greatest(want, 1)) as factor_mismatch,
       count(distinct security_id) filter (where abs(adj_factor - want) > 1e-6 * greatest(want, 1))
         as securities_with_mismatch
from expected;

\echo '== Largest mismatches (up to 15 securities) =='
with expected as (
  select b.security_id, b.date, b.adj_factor,
         coalesce((select exp(sum(ln(a.ratio)))
                   from corporate_actions a
                   where a.security_id = b.security_id and a.ratio is not null
                     and a.ex_date > b.date), 1)::numeric as want
  from ohlcv_daily b)
select s.symbol, e.security_id, count(*) as bars, min(e.date) as first, max(e.date) as last,
       min(e.adj_factor) as stored_min, max(e.adj_factor) as stored_max,
       round(min(e.want), 6) as want_min, round(max(e.want), 6) as want_max
from expected e join securities s on s.id = e.security_id
where abs(e.adj_factor - e.want) > 1e-6 * greatest(e.want, 1)
group by s.symbol, e.security_id order by bars desc limit 15;

\echo '== Adjustment dates: stored factor steps against action ex-dates =='
-- A step is a bar whose factor differs from the next bar's. It is aligned when
-- a priced action has its ex-date after the bar and on or before the next bar.
with steps as (
  select security_id, date, next_date
  from (select security_id, date, adj_factor,
               lead(date) over w as next_date, lead(adj_factor) over w as next_factor
        from ohlcv_daily window w as (partition by security_id order by date)) t
  where next_factor is not null and next_factor <> adj_factor
)
select count(*) as factor_steps,
       count(*) filter (where not exists (
         select 1 from corporate_actions a
         where a.security_id = steps.security_id and a.ratio is not null
           and a.ex_date > steps.date and a.ex_date <= steps.next_date)) as steps_without_action
from steps;

\echo '== Priced actions inside the bar history with no factor step at their ex-date =='
with spans as (select security_id, min(date) as lo, max(date) as hi from ohlcv_daily group by security_id)
select count(*) as priced_actions_in_history,
       count(*) filter (where not exists (
         select 1 from ohlcv_daily b1 join ohlcv_daily b2
           on b2.security_id = b1.security_id
          and b2.date = (select min(date) from ohlcv_daily x
                         where x.security_id = b1.security_id and x.date >= a.ex_date)
         where b1.security_id = a.security_id
           and b1.date = (select max(date) from ohlcv_daily y
                          where y.security_id = a.security_id and y.date < a.ex_date)
           and b1.adj_factor <> b2.adj_factor)) as actions_without_step
from corporate_actions a join spans s on s.security_id = a.security_id
where a.ratio is not null and a.ex_date > s.lo and a.ex_date <= s.hi;
