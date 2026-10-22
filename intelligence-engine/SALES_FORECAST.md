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
three rolling three-day holdouts. The lowest MAE method is selected. If Prophet
is unavailable, the validated weekday baseline is used. Negative net turnover is
retained. Forecast dates are the three days immediately after the scope's latest
sales date, which can differ by location.

The range is prediction plus/minus the 90th percentile absolute error from nine
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
  today. Configure `SALES_WEATHER_API_KEY` and `SALES_WEATHER_LOCATIONS_JSON` in
  `.env`. The latter maps exact branch location labels to verified coordinates:
  `{"YOUR LOCATION":{"lat":10.0,"lon":76.0}}` (illustrative, replace coordinates).
  Missing coordinates, historical dates and uncovered forecast days are explicitly
  unavailable. All-location weather is not approximated using one city.
- Gold API: no key required for `/price/XAU`. Returns current USD/troy-ounce spot
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

This information is advisory and does **not** multiply or modify predictions.
Using weather, gold prices or festivals as model inputs requires aligned historical
features and out-of-sample validation first. These integrations use free endpoints
or free-tier keys; no subscriptions are created automatically.

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
