# Purchase Plan performance

The report still uses `sales_stock_composition_analysis_snapshots`. Its UI,
filters, date rules, formulas, rounding, missing-value rules, and global
composition denominators are unchanged.

## Changes

- Cache options, main data, branches, contributors, location factors, and totals
  for three hours. Cache keys include the latest snapshot `synced_at`; a committed
  snapshot replacement automatically starts a new cache generation. Empty
  snapshots bypass the cache. Failed refreshes retain the previous generation.
- Resolve the snapshot version once per request. Reuse factors by cutoff and
  location filters; reuse totals by cutoff and all selected filters, independently
  of hierarchy, path, and sort. Branch result keys also include path and sort.
- Use a Redis lock per key to coalesce simultaneous rebuilds. Wait at most two
  seconds for another worker, then fall back to calculation. Locks expire after
  120 seconds and are released only by their owner. Database failures are not
  cached. Redis outages fall back to the original database calculation, with
  subsequent cache reads bypassed for the rest of that request.
- Combine the three overall stock aggregate queries into one. Keep sales
  aggregation and location annualisation order unchanged.

## Measurement

The page, main partial, branch, contributors, and options handlers emit an INFO
log through `app.services.purchase_plan_cache`, for example:

```text
Purchase Plan operation=branch elapsed_ms=... sql_queries=3 cache_hits=2 cache_misses=1 cache_fallbacks=0
```

SQL counts cover work inside the handler, after access checks. Compare initial
page time separately from the main AJAX request. Compare cache hits and misses
separately; no production latency improvement has been assumed from unit tests.

To profile the deployed snapshot database, configure `SQLALCHEMY_DATABASE_URI`
and run from `server` using the application's Python environment:

```sh
PYTHONPATH=. python scripts/profile_purchase_plan.py --date 2026-11-24 --filters '{"division":["Gold"]}'
```

Add `--explain` to execute the uncached main report SELECTs again using
`EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)`. This performs real query work; run
against staging or during an appropriate production measurement window. The
profiler uses a read-only PostgreSQL connection and does not clear Redis.
Cached-first runs may already hit existing cache entries.

## Verification

The performance regression fixture fingerprints 224 results generated with the
pre-optimization implementation, across all hierarchy roots, date cutoffs,
sorting, branches, charts, missing values, and location projections. The new
uncached and shared-cache paths match that fingerprint, including repeated JSON
cache reads. Endpoint tests verify identical branch/chart responses on cache
hits, path separation, sync invalidation, and Redis outage fallback.

For an explicit cutoff, the fixture's uncached calculation uses five queries
(previously seven). A new branch with cached factors and totals uses three
queries: snapshot version, child sales aggregation, and child stock aggregation.
An exact result cache hit uses one version query. These counts exclude access
checks and are not production latency benchmarks.
