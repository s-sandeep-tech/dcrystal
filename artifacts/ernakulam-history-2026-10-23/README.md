# Ernakulam weather backfill

Requested period: 1 April through 22 October 2026. Branch: 20, ERNAKULAM.
Representative city coordinates: 9.98 N, 76.30 E; these are not surveyed shop coordinates.

`ernakulam_weather.sql` inserts source-derived historical daily rainfall and maximum
temperature into `sales_external_features`, with `ON CONFLICT DO NOTHING`. It does
not update existing rows or predictions. No database insert has been performed.

The NASA POWER daily point response is saved in `weather_source.json`. The manifest
records missing dates and rainfall above 500 mm/day, which are quarantined rather
than inserted. Values are not silently rescaled or filled. This plausibility screen
is not independent weather validation; review the source before production use.

The observations use UTC daily intervals and a gridded meteorological dataset.
They differ from WeatherAPI local-day forecasts and must not be represented as
forecasts issued before historical sales dates. Availability is conservatively
the retrieval timestamp. Consequently, importing this SQL alone will NOT remove
the current point-in-time backtest fallback. A matching historical forecast archive
or a model using properly lagged observations is needed for that purpose.

Gold history is now in `ernakulam_gold.sql`, and `ernakulam_history.sql` combines
the weather and gold inserts. Both sources are keyless: GoldPrice.com daily closes
in USD/troy ounce and ECB same-date reference FX. INR per gram is calculated as:

```
gold USD/oz * (ECB INR/EUR / ECB USD/EUR) / 31.1034768
```

This is an international reference value, not an IBJA benchmark or an Ernakulam
retail quote. No duties, taxes, making charges or purity adjustments are added.
Gold features use `global` scope because the same reference rate applies across
branches, including branch 20. Data source differences from live Gold API spot
quotes remain visible in the provider field. The source USD and FX series may
observe different intraday fixing times; this is a daily cross-rate conversion.

`gold_manifest.json` reports exact coverage and unmatched dates. No missing dates
or weekends are filled. `gold_converted.json` preserves the exact USD gold and FX
inputs for each output value. Raw sources are saved as `gold_source.csv`,
`ecb_fx_source.xml` and `ecb_fx_daily_source.xml`. GoldPrice.com's CSV requests
attribution to https://goldprice.com/gold-price-history (CC BY 4.0). ECB reference
rates are for information purposes. Both sources are attributed in the SQL.

Gold availability is also retrieval time; no unsupported historical publication
time is asserted. This SQL completes the accessible historical data export, not
point-in-time training eligibility. Baseline fallback can remain after import.
Consult the manifests for remaining gaps; the files do not claim every calendar
day has an independently observed gold value.

To insert after reviewing, from psql:

```sql
\i /path/to/ernakulam_history.sql

SELECT provider, COUNT(*), MIN(feature_date), MAX(feature_date)
FROM sales_external_features
WHERE scope = 'branch:20' AND feature_group = 'weather'
GROUP BY provider;
```

Source documentation:
https://power.larc.nasa.gov/docs/services/api/temporal/daily/
https://goldprice.com/gold-price-history
https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.en.html
