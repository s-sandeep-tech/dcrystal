# Customer Order Performance & Delivery Monitoring

Page: `/customer-order-performance-monitoring`

The report uses `customer_order_analysis_snapshot`, refreshed by the existing
customer-order sync from `ext_view.vw_customer_order`. No new model, migration,
external connection, or sync job is required. The Party Performance Matrix CSS
and chart library provide the design reference; neither existing report is changed.

## Access and endpoints

- Page and `/api/customer-order-performance-monitoring/data` require JWT and a
  restored user session. The existing customer-order visibility helper scopes
  snapshot rows before options or calculations are produced.
- `/api/customer-order-performance-monitoring/export` also requires
  `report.export`. CSV includes all matching rows, not just the current page.
- BUSINESS_HEAD and SHOWROOM_MANAGER supplier names/codes are masked in HTML,
  details and CSV. Customer names/phones and employee codes are not selected.
- The browser reuses CustomMultiSelect and Chart.js. The heatmap is a scrollable,
  keyboard-accessible HTML table, with exact-value tooltips and cell selections.

## Calculations

The report date is today's Asia/Kolkata date. Request delivery risk uses the
earliest dated outstanding SOOC under the same request, before interactive
filters; terminal items never set that date. Missing dates remain a separate
category. A request with some dated items uses the earliest known date.

The approved delivered/cancelled/rejected statuses are terminal even if the
snapshot retains stale positive pending quantities. Other approved statuses are
active. Unknown statuses qualify only with positive pending quantities and produce
a warning. Stage selections additionally require active items.

Orders are distinct nonblank request numbers; items are distinct nonblank SOOCs.
Risk counts use the same request number identity, including across branches.
Rows without request numbers do not contribute to delivery-risk counts. Missing
SOOCs remain visible and contribute quantities but not distinct item counts.

Production pending comes only from `total_pending_*`. Approval and customer
delivery are separate measures. All ten stage quantities remain separate and are
never added together to derive production pending. The table displays all positive
stages. Owners retain explicit labels, without inferred stage responsibility.

Exact duplicate SOOC business rows are collapsed (ignoring snapshot metadata).
Conflicting SOOCs fail with HTTP 409. SQL checks in
`scripts/validate_customer_order_monitoring.sql` should be run against the deployed
snapshot before production sign-off. Do not resolve conflicting rows with MAX.

Urgency cutoffs can be set using Flask configuration:
`CUSTOMER_MONITOR_HIGH_DAYS` (default 2) and `CUSTOMER_MONITOR_MEDIUM_DAYS` (default 7).
Cutoffs must satisfy `0 <= high < medium`; charts adapt their labels accordingly.

## Verification

Run from `server`:

```sh
../venv/bin/python -m unittest tests.test_customer_order_monitoring tests.test_customer_order_monitoring_routes tests.test_customer_order_analysis -q
```

Coverage includes exact/conflicting duplicates, date boundaries, earliest active
delivery dates, terminal statuses, missing dates, separate pending measures,
role visibility, supplier masking, export scoping, escaping and empty states.

This implementation reads authorized snapshot rows into memory for validation
and aggregation. At substantially larger snapshot sizes, benchmark request memory
and latency before rollout; a prevalidated database aggregation layer may be needed.
