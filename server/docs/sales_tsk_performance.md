# Sales & TSK Performance

Route: `/sales-tsk-analyse`. Listed in the Sales & Stock report menu.

This report queries `ext_view.vw_item_wise_tsk_details_data` on the external PostgreSQL connection. It has no snapshot model, sync job, or item-level endpoint. Each page segment and the filter options load independently through `/api/sales-tsk-analyse/<segment>`. The CSV download button has been removed from the report UI; the existing protected export endpoint still contains monthly summaries only.

## Definitions

- Default range: the current April–March financial year to date, using Asia/Kolkata. The current month may be partial. Custom ranges cover at most twelve calendar months.
- Sales date: `COALESCE(trans_date::date, date)`; inclusive start and end dates.
- Included transactions: `INVOICE` and `SR`, optionally narrowed by the transaction-type filter.
- Invoice turnover: sum of invoice `turn_over`.
- Returns: signed return turnover, using the existing `SALES_PREDICTION_RETURN_SIGN` setting (`signed` by default, or `positive` to subtract positive source returns).
- Net turnover: invoice turnover plus signed returns. Missing turnover or inconsistent return signs produce an explicit segment error.
- Net weight: sum of source `net_weight` in grams divided by 1,000, displayed/exported in kg. TSK: sum of `total_tsk` as supplied by the view. Return-sign normalization is applied only to turnover. These are labeled source totals.
- Section breakdown: grouped by `section_id`, labeled with `section`; missing section IDs remain in an Unspecified group. A signed bar chart replaces the donut when contributions contain negatives.
- Branch leaderboard: top ten branches by net turnover, with shares calculated against all matching branches.
- KPI YoY: each statistic compares the full selected period with the same dates last year, using identical filters and `(current - prior) / abs(prior) * 100`. Zero/missing prior bases show an unavailable badge. For signed returns, a less-negative total is a positive change.
- Monthly ledger YoY: matching prior-year dates (February 29 clamps to February 28); unavailable for missing/non-positive prior bases or months with no current rows.
- Ledger Return rate %: absolute signed return turnover ÷ invoice turnover × 100; unavailable for zero/negative invoice turnover.
- Ledger TSK %: `total_tsk` ÷ net turnover × 100; unavailable for zero/negative net turnover. This does not use `total_tsk_plusit_charge`. Footer percentages use period totals, not averaged monthly percentages.
- Ledger cumulative turnover: running net turnover from the first selected month, including partial months and signed returns; missing months carry the previous total forward. The footer shows final period turnover, not the sum of cumulative values. Displayed in Cr with full-value hover; protected CSV endpoint uses full amounts.
- Ledger contribution bars: monthly net turnover divided by selected-period net turnover. Zero/negative period totals have no percentage. Negative contributions have no filled bar; bars cap visually at 100% while labels retain the actual percentage.
- Ledger MoM: `(current - previous) / abs(previous) * 100`, only for consecutive complete selected months with transactions and a nonzero previous total. Partial boundary months are marked and excluded. CSV includes contribution, MoM, and partial-month status.
- Missing months: zero totals. Prior history is never invented. The monthly chart hides the prior-year series when the selection has no prior-year records; card sparklines always represent monthly totals. Partial date ranges compare equivalent partial ranges.

Source weight is converted from grams to kg by dividing by 1,000 across every segment and CSV; YoY percentages are unchanged by unit conversion. Turnover and TSK amounts in KPI cards, chart axes, and all tables display in crores (1 Cr = 10,000,000), with full values on hover. CSV retains full monetary amounts and kg weight for analysis. Currency is not inferred. Margin, average ticket, targets, VIP conversion, and sell-through are not derived from this view.

## Access and operation

Every endpoint, including options and CSV, uses the existing `require_report_access` decorator for this report URL, matching other sales reports. These reports use report-level grants; no additional branch/owner entitlement model is assumed.

Register the database menu on deployment:

```sh
python scripts/add_sales_tsk_performance_menu.py
```

The script migrates the existing `/sales-tsk-performance` menu row in place, preserving its role grants and placement. Old page links redirect to `/sales-tsk-analyse` with their query filters. The script is idempotent and grants the ADMIN role. Administrators can assign other roles through existing RBAC management. Reload application workers after deployment.

Queries are read-only, parameterized, and limited to a 30-second statement timeout. Responses use `Cache-Control: no-store`. Database aggregates, not item rows, are transferred to the application. Each segment has its own fetch time and retry state; separate segment requests do not represent one atomic source snapshot.

## Verification

```sh
python -m unittest discover -s tests -p test_sales_tsk_performance.py -v
# Also execute SQL against connection-local temporary tables:
SALES_TSK_SQL_TEST=1 python -m unittest discover -s tests -p test_sales_tsk_performance.py -v
```

The opt-in tests use `SQLALCHEMY_DATABASE_URI` and create only a connection-local TEMP table. They do not modify application tables.

Live external connectivity was unavailable during implementation, both from the host and the application container. Production source types, row-grain uniqueness, weight/TSK sign conventions, query latency, and actual totals require validation once that connection is available. Fixture SQL and browser checks do not establish those live-data properties.
