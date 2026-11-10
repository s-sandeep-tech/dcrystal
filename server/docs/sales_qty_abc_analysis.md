# Sales Quantity ABC Analysis

Page: `/sales-qty-abc-analysis`. Protected APIs: `/api/sales-qty-abc-analysis/options` and `/api/sales-qty-abc-analysis/hierarchy`.

The report has independent routes, service, template, JavaScript, CSS, tests and menu registration. It extends the shared application shell and uses the shared external connection and access decorator. It does not import or serve any existing report service, template, JavaScript, or CSS. The only existing source file changed is the dashboard route registration.

## Source and quantity contract

Reads `ext_view.vw_item_wise_tsk_details_data` directly using a read-only transaction, a 30-second query timeout and parameterized filters. No snapshots, models or migrations are created. The date expression is `COALESCE(trans_date::date, date)`, inclusive of both selected dates. Defaults are financial-year-to-date in Asia/Kolkata, with at most twelve calendar months.

Hierarchy: Make → Purity → Collection → Subsection → Section → Type → Weight Range. IDs identify groups within their full ancestor path; null IDs are retained as Unspecified. Weight Range maps to `wide_range_id` / `wide_range`; Subsection maps to `sub_section_id` / `sub_section`. Source schema is checked before both API queries, and missing columns produce a descriptive 422 error.

Sold Qty counts distinct non-null **invoice** barcodes per complete seven-level hierarchy path across the selected period, plus one per null-barcode invoice row. Parents sum leaf quantities, so each parent reconciles to its children. Repeated invoice appearances of a barcode within the same path count once; appearances in different paths count in each. This intentionally measures barcode-based sold quantity, not signed net units or the count of sales events. It differs from summing the reference report's monthly barcode counts. Returns do not subtract from Sold Qty.

Sold Weight sums invoice `net_weight` / 1000 in kg. Net Turnover combines invoice turnover and returns according to `SALES_PREDICTION_RETURN_SIGN` (`signed` by default, or `positive`). Missing turnover and incompatible return signs produce a source error. MC Profit sums `mcprofit` with source signs across included transactions. Transaction filters apply to every metric; a returns-only selection produces zero Sold Qty and Unclassified rows.

## ABC and display

All ten columns display by default: Hierarchy, Rank, Sold Qty, Contribution %, Cumulative %, Category, Overall Contribution %, Sold Weight (kg), Net Turnover, MC Profit. The last four columns can be hidden using the Columns menu. Table rows use compact vertical spacing. Monetary columns display Cr and provide full-value tooltips.

Siblings sort by quantity descending, then label, then ID; Rank is a sequential position. Contribution divides by parent quantity (report total at Make level). Cumulative contribution restarts within each parent. Overall Contribution divides by report quantity. Full-precision calculations precede display rounding.

The category uses cumulative contribution **before** the current row: below 80% is A; below 95% is B; otherwise C. Thus the row crossing a threshold remains in the category it completes. Exact 80% and 95% boundaries start the next category. A single dominant row is A. Ties are deterministically ordered and can span categories. Zero quantities are Unclassified; non-positive denominators show unavailable percentages.

Only Make rows initially display. Expansion, Collapse all, the compact Show through hierarchy menu, search, zoom and optional columns are client-side. Search reveals matching paths without changing the server calculations; clear search to resume manual expansion. Footer totals count each leaf once regardless of expansion. Applied filters are persisted in the URL. Date-scoped options retain selected values and do not overwrite edits made while a request is loading. Refresh uses applied filters. Reset restores default dates and clears selections/search/expansion.

The server aggregates complete paths, not raw item rows. Results above 20,000 leaf groups are rejected with a request to narrow filters; no truncated totals are displayed. Live query latency and production-scale rendering require validation against the actual source.

## Registration and deployment

From `server/`, using the deployment Python environment:

```sh
python scripts/add_sales_qty_abc_analysis_menu.py
```

This idempotently adds the new menu and ADMIN grant, preserving existing menus and grants. Assign other roles through existing RBAC management. Restart application workers after deployment. Menu registration has not been run against a live application database in this implementation session.

## Validation

From repository root:

```sh
PYTHONPATH=server venv/bin/python -m unittest discover -s server/tests -p 'test_sales_qty_abc_analysis.py' -v
PYTHONPATH=server venv/bin/python -m unittest discover -s server/tests -p 'test_sales*tsk*py' -q
```

Unit coverage includes ABC boundaries/crossing rows, tie ordering, zero/null groups, all-level reconciliation, parent versus overall contribution, date validation, parameterized SQL, invoice/null barcode query semantics, schema errors, result limits, read-only connection cleanup, independent report authorization, API errors and menu idempotence.

Fixture Chromium checks passed for initial columns, expansion through all seven levels, search retaining calculations, optional columns, zoom, information dialog, Apply/Reset, mobile filters, error/retry and desktop/dark/mobile screenshots. No browser JavaScript errors were observed. These tests do not validate live PostgreSQL execution or real quantities.

The external hostname could not resolve in the development environment. Live schema, barcode uniqueness across hierarchy paths, subsection/weight-range availability, return signs, production values and query performance still require verification from the deployment network.
