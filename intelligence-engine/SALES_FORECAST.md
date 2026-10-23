# Sales Turnover Forecast

## Deployment

From the repository root:

```sh
docker compose build server sync-consumer intelligence-engine
docker compose run --rm --no-deps server python scripts/setup_sales_prediction.py
docker compose up -d --no-deps server sync-consumer intelligence-engine
```

The setup script creates the prediction tables and report menu permission without
changing the existing Sales & Stock Composition report. It grants the new menu to
existing ADMIN, SUPER_ADMIN and DATA_SYNC_USER roles. Other viewers need the
`/sales-turnover-forecast` menu assigned through role management. Running syncs or
forecasts requires ADMIN or DATA_SYNC_USER under the existing access policy.

In Settings, use **Sales Prediction Data Sync**, optionally select **Forecast
after sync**, then open **Sales Turnover Forecast**. The report supports all
locations or one location, 30/90-day or full history, and a three-day forecast.
Actual turnover is solid blue, forecast turnover dotted amber, and the shaded
band is an indicative error range. Display amounts are INR lakhs; storage is INR.

## Data Contract

- Source: `ext_view.vw_item_wise_tsk_details_data`, not the cumulative summary view.
- Fields read: `id`, `trans_date`, `date`, `branch_id`, `location_name`,
  `trans_type`, `turn_over`, `last_updated_at`.
- Only `INVOICE` and `SR` records through yesterday in Asia/Kolkata are included.
  Business date is `COALESCE(trans_date::date, date)`. Conflicting non-null dates,
  missing required fields and duplicate IDs fail validation.
- Default `SALES_PREDICTION_RETURN_SIGN=signed` expects non-positive SR turnover.
  For a verified positive-return source, set this variable to `positive` on the
  sync consumer. Mixed signs are rejected; amounts are never silently made ABS.
- Daily net turnover is invoice turnover plus signed return turnover, grouped by
  branch and date. All available source history is refreshed in a consistent
  read-only transaction, fetched in batches of 20,000 aggregated rows.
- A new version is published only after source counts and local sums reconcile.
  Failed refreshes leave the previous version available. Old versions are retained
  because queued forecasts refer to their exact input version.
- Missing dates inside observed history are assumed zero after the full-source
  refresh. There is no upstream completeness watermark: this assumption must be
  checked against source loading practices. Stale histories are flagged, not
  extrapolated silently to today's date.

## Forecast Method

At least 65 calendar days and 28 observed sales dates are required. A recent
same-weekday average and Prophet weekly-seasonality model are compared using
three rolling three-day holdouts (six with at least 90 days). The lowest MAE baseline is selected. If Prophet
is unavailable, the validated weekday baseline is used. Negative net turnover is
retained. Forecast dates are the three days immediately after the scope's latest
sales date, which can differ by location.

The range is prediction plus/minus the 90th percentile absolute error from nine or eighteen
backtest observations. It is indicative, not a calibrated 90% confidence interval.
Each task fits its input history; this feature does not depend on an in-memory
model surviving a restart. Results are persisted in `sales_turnover_forecast_runs`
and `intelligence_forecasts` with metric `sales_net_turnover`.

Requests use the existing Redis Streams retries, heartbeats and crash recovery.
An unqueued durable request is recovered by the worker's database outbox. Duplicate
deliveries retain the same task ID and existing durable task receipts prevent
repeated output writes. The sync itself uses the existing application sync queue.

## Optional External Context

Select External API data in Settings or External data in the report. This path
uses free APIs first. It returns structured `parameters.weather`,
`parameters.gold` and `parameters.festivals` with provider attribution.

- WeatherAPI.com: free plan, API key required, three-day weather window including
  today. Configure `SALES_WEATHER_API_KEY` and city/state mappings in
  `SALES_REGION_LOCATIONS_JSON` for automatic coordinate lookup. Optional explicit
  `SALES_WEATHER_LOCATIONS_JSON` overrides map exact branch labels to coordinates:
  `{"YOUR LOCATION":{"lat":10.0,"lon":76.0}}` (illustrative, replace coordinates).
  Unresolved locations, historical dates and uncovered forecast days are explicitly
  unavailable. All-location weather is not approximated using one city.
- Gold API: no key required for `/price/XAU/INR`. Source quotes are INR/troy-ounce spot
  observations with provider timestamps, NOT an Indian retail rate or gold-price
  forecast. Current quotes are never substituted for historical forecast periods.
- Calendarific: configure `SALES_CALENDARIFIC_API_KEY` from a free account
  (500 calls/month). Fetches Indian holidays by year. Dhanteras/Akshaya Tritiya
  coverage depends on the provider; absent events are marked missing, never inferred.
  Provider source links remain visible for attribution.

The context cache includes the exact location, start/end dates, retrieval day and
coordinate configuration. Old Gemini caches and cross-period stale fallbacks are
not used. Context/gold caches last five minutes, weather 30 minutes, and calendars
seven days. Provider failures remain isolated and do not stop the forecast.
Gemini fallback is a separate, default-off checkbox requiring External data to be
enabled. It runs only when at least one API parameter is unavailable or partial.
It requests only those gaps, preserves API values and missing-data flags, and adds
sourced commentary separately under `gemini_fallback`. No unsourced answer is
accepted. Gemini failure does not stop the forecast. Use the existing
`INTELLIGENCE_GEMINI_API_KEY` (or `GEMINI_API_KEY`) and a search-capable `GEMINI_MODEL`.
Gemini API charges may apply when this option is enabled. Cache identity includes
the fallback option and model, so free-only requests never reuse Gemini results.

Run this migration manually before deploying the updated server:

```sql
ALTER TABLE sales_turnover_forecast_runs
ADD COLUMN IF NOT EXISTS allow_gemini_fallback boolean NOT NULL DEFAULT false;
```

No API keys or credential-bearing URLs are logged. Recreate the intelligence-engine
container after changing environment variables. Existing saved forecasts retain
their old context; run a new forecast to fetch API data.

Provider documentation and free-tier limits:
https://www.weatherapi.com/pricing
https://gold-api.com/docs
https://calendarific.com/pricing

## External Feature Models

### Historical Observations and Leakage Protection

`weather_observations` now has the weather schema (`rain_mm`, `max_temp_c`) but is
separate from advance `weather` forecasts. Legacy NASA POWER historical observation
rows are classified as observations on read; existing data need not be rewritten.
Lagged weather, lagged gold, and combined observation candidates are evaluated.

Each candidate now trains a separate model for leads 1, 2 and 3. A training target's
inputs are selected at that target's historical prediction origin for that lead,
not using a later day's gold quote or realised future weather. Weather forecasts
must have been issued by that origin; observations must both describe earlier
dates and have `available_at <= origin`. Only observations within seven days are
carried, and the final three-day observation inputs are frozen at the actual origin.
Scaling and regression fit only on the training slice. The existing 5% improvement
gate and coverage requirement remain; external factors are not forced into a model.

**The current Ernakulam download is not proof of historical publication times.**
Those rows record availability on retrieval in October. Moving their availability
to April would invent evidence and invalidate the backtest. These files can be
stored now and become known inputs for subsequent origins, but strict historical
backtests still require original release timestamps or archived forecast vintages.
The read-only `sql/audit_sales_history_availability.sql` identifies this condition.
Metrics include `feature_availability`, `feature_timing_policy`, and an observation
model flag. Saved observation inputs include source feature IDs for reproduction.

To make a historical dataset eligible, import verified source records through
`scripts/import_sales_features.py` with their actual published/issued `available_at`
and actual download `retrieved_at`, preserving source attribution. Weather actuals
released after a day may only serve lagged observation features. Do not use a
blanket UPDATE to backdate availability or treat a dataset's date as its release
time. Publication evidence is currently missing for the previously generated SQL;
the code deliberately retains baseline fallback rather than asserting an unavailable
historical accuracy improvement. No new table migration is required.

### Regional Festivals and Weddings

### Automatic Weather Coordinates

Branch metadata now comes from the sales snapshot for every branch:
`location_name` is the lookup label, `state_name` validates the state, and country
is India. No per-location environment mapping is required. Known trailing branch
suffixes (ROUND, FRCH/FRCHS, SHOP, BRANCH, RO/HO, VL, numeric suffixes) are removed
for city search. Returned city/state/country must still match; ambiguous or
unresolved labels remain unavailable. The same synced state feeds regional festivals
and wedding calendars where a state catalog is supported.

Before deploying, run `intelligence-engine/sql/sales_branch_state.sql`, restart the
server/sync-consumer/intelligence-engine, run Sales Prediction Data Sync, then run
a new forecast. Existing snapshots have no state until resynced. Predictions remain
retained. Missing or conflicting state data is logged and cannot validate a lookup.
The configuration below remains an optional legacy fallback for calls without
database branch metadata; it is no longer necessary for synced branches.

Weather uses explicit `SALES_WEATHER_LOCATIONS_JSON` coordinates first. When absent,
it calls WeatherAPI.com's free-tier `/v1/search.json` endpoint with the existing
`SALES_WEATHER_API_KEY`. The expected city and state come from
`SALES_REGION_LOCATIONS_JSON`; no latitude/longitude entry is required:

```dotenv
SALES_REGION_LOCATIONS_JSON={"GUWAHATI":{"city":"Guwahati","state_code":"IN-AS"},"THRISSUR ROUND":{"city":"Thrissur","state_code":"IN-KL"}}
```

Returned city names must match the configured city (case/spacing insensitive), the
state must match its configured Indian state code, and country must be India.
Multiple distinct matching coordinates are rejected. To support a verified alternate
city spelling, add `city_aliases`, e.g. `["Trichur"]`, to that branch configuration.
Successful coordinates are cached in Redis for 30 days; no-match/ambiguous results
for five minutes. Changing city/state/aliases changes the cache identity. Redis
failure still permits direct lookup. Requests, HTTP timing, cache events, rejected
matches and resolution decisions appear in existing `external_fetch` logs without
API keys. No search is made for All locations or out-of-window historical weather.
Recreate the engine container after environment changes and run a new forecast.
There is no new SQL migration. Documentation: https://www.weatherapi.com/docs/search-api/

### Regional Calendar Configuration

Configure exact branch labels in `.env`, then recreate the engine container:

```dotenv
SALES_REGION_LOCATIONS_JSON={"GUWAHATI":{"state_code":"IN-AS","city":"Guwahati"},"THRISSUR ROUND":{"state_code":"IN-KL","city":"Thrissur"}}
```

Supported state catalogs: KL (Onam/Vishu), TN (Pongal/Tamil New Year), AS (Bihu),
WB (Durga Puja), KA (Ugadi/Dasara), AP (Ugadi/Sankranti), TS (Ugadi/Bathukamma),
MH (Gudi Padwa/Ganesh Chaturthi), GJ (Navratri/Uttarayan), PB (Baisakhi), prefixed
with `IN-`. Unsupported or unmapped branches retain baseline fallback for these
groups. National aggregate models do not receive one branch's regional features.
Calendarific is queried first using its state filter and the existing free-tier
key. A holiday list does not constitute a wedding calendar; absent wedding dates
are explicitly marked unavailable.

With the existing Gemini fallback checkbox enabled, missing regional calendar
groups trigger a separate Google Search grounded JSON request. Dates and seasons
must match the requested region/year, have a valid bounded date interval, and cite
a URL present in grounding metadata. Only catalogued festival names are accepted.
Calendar coverage must explicitly identify a complete year before daily zero/nonzero
features are generated; partial facts are displayed but are not treated as complete
training calendars. Grounding and schema checks establish provenance, not independent
proof of a source's calendar accuracy. Provider omissions can still require verified
manual calendar backfill. Successful API events are retained alongside supplements.

The new groups reuse existing feature/audit tables; no additional SQL migration is
needed beyond the prior external-feature migration. They preserve retrieval-time
availability and cannot be used retroactively to improve old backtests.

New feature schemas for branch-scoped historical imports:

- `regional_festivals`: `festival_day` (0/1), `festival_lead_7` and `festival_after_7`
  (0..1 proximity to regional events).
- `weddings`: `wedding_season` (0/1), `days_to_wedding` (0..30; 31 means no verified
  wedding date in the next 30 days), `wedding_dates_next_7` (0..7, including today).

Regional-calendar and wedding-only candidates, their combination and an all-feature
candidate compete with existing models under the same 42-day/80%-coverage and 5%
backtest improvement rules. Missing future inputs retain the baseline. Fetch logs
include state, requested years, coverage gaps, accepted/rejected Gemini facts and
fallback requests. No new paid service is activated automatically.

Structured API features can now affect predictions. Gemini narrative remains
commentary and is never parsed into numerical model inputs. A baseline is retained
until historical coverage and backtests justify an external model.

- Weather: rainfall and maximum temperature for a specific branch.
- Gold: last known INR/gram quote, carried at most seven days. Source INR/troy-ounce
  prices are divided by 31.1034768 without rounding model inputs. Source price/unit
  are preserved. Legacy INR/ounce features are converted on read; USD features remain
  excluded. Saved INR/ounce report values are displayed per gram without rewriting
  the stored forecast. No future
  gold price is invented. Forecasts use the price actually available at their origin.
  Legacy USD feature rows remain stored for audit but are excluded from INR models.
  New INR history must accumulate or be imported; no historical FX conversion is
  guessed. Existing saved forecasts retain their original currency. Generate a new
  forecast after restarting the engine to fetch INR quotes. No SQL migration is needed.
- Festivals: separate Dhanteras and Akshaya Tritiya proximity values within seven
  days before/after each verified event. Missing calendars are not zero-filled.
- Candidate models: standardized ridge regression with weekday/trend controls and
  weather, gold, festival, or combined features. At least 42 complete training days
  and 80% point-in-time coverage are required. Constant external data is rejected.
- Each candidate uses the same rolling three-day holdouts as the baseline: six
  windows with >=90 history days, otherwise three. Selection requires at least 5%
  lower MAE than the best baseline. Missing final-horizon inputs fall back to baseline.
  These small holdouts are model-selection diagnostics, not a guarantee of accuracy.
- All-location runs can use global gold/festival features; branch weather is never
  applied to national turnover. Weather-enhanced models require a selected branch.

### Storage and Logs

Run `intelligence-engine/sql/sales_external_features.sql` manually before rollout
(the engine's existing startup table creation also includes these tables).
`sales_external_features` stores immutable provider vintages, including availability
and retrieval timestamps. `sales_forecast_feature_inputs` records each forecast's
input pool and model-selection metrics. `sales_external_fetch_logs` records requests,
HTTP outcomes/timing, cache hits/misses, provider coverage and Gemini fallback events.
Logs commit independently so failed forecast transactions do not erase fetch audits.
Console records start with `external_fetch`. Credentials and query strings are omitted.

```sql
SELECT created_at, task_id, event_json
FROM sales_external_fetch_logs ORDER BY id DESC LIMIT 50;
SELECT scope, feature_group, COUNT(*), MIN(feature_date), MAX(feature_date)
FROM sales_external_features GROUP BY scope, feature_group;
```

### Historical Feature Backfill

Free current APIs cannot recreate historical forecast vintages. Features accumulate
when external-enabled forecasts run; there is no automatic daily collection schedule.
To activate enhanced models sooner, import a JSON array of verified historical
features using `python scripts/import_sales_features.py /path/features.json` inside
the engine container. Each row follows this shape:

```json
{
  "scope": "branch:2",
  "feature_group": "weather",
  "feature_date": "2026-10-23",
  "available_at": "2026-10-22T06:00:00+00:00",
  "retrieved_at": "2026-10-22T08:00:00+00:00",
  "provider": "verified-weather-provider",
  "source": "https://provider.example/archive",
  "values_json": {"rain_mm": 3.2, "max_temp_c": 30}
}
```

Use `global` scope for `gold` (`price_inr_g`) and `festivals`
(`dhanteras_proximity`, `akshaya_proximity`, both 0..1). Do not assign historical
availability timestamps unless the source proves that date. A calendar retrieved
today is not automatically treated as available during past backtests. Weather
actuals observed after a sales date are not substitutes for forecasts issued before
that date. Imports are validated and idempotent; no date is inferred.

### Prediction Retention

Sales syncs do not delete predictions. The report uses newly synced actual sales
alongside saved predictions. The latest completed forecast remains displayed while
a newer task is pending or failed, even if it refers to an older snapshot. The
report labels older-snapshot forecasts; historical predictions remain in the
comparison table and the chart's selected history window.

## Verification

```sql
SELECT id, cutoff_date, row_count, source_count, net_turnover, created_at
FROM sales_prediction_sync_runs ORDER BY created_at DESC LIMIT 5;

SELECT sales_date, SUM(net_turnover) AS net_turnover
FROM sales_turnover_daily_snapshots
WHERE run_id = (SELECT id FROM sales_prediction_sync_runs
                ORDER BY created_at DESC LIMIT 1)
GROUP BY sales_date ORDER BY sales_date DESC LIMIT 10;

SELECT task_id, branch_id, queued_at, result_json IS NOT NULL AS has_result
FROM sales_turnover_forecast_runs ORDER BY created_at DESC LIMIT 10;
```

Focused tests:

```sh
docker compose exec server python -m unittest discover -s tests -p test_sales_prediction.py -v
docker compose exec intelligence-engine python -m unittest discover -s tests -p test_sales_turnover.py -v
```

`server/tests/test_sales_prediction_integration.py` is opt-in and must run only
against a disposable database named `sales_test`. It creates a simulated external
source and exercises reconciliation, failure rollback and forecast publishing.
