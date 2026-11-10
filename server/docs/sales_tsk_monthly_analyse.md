# Monthly Sales & TSK Analysis

New page: `/sales-tsk-monthly-analyse?start=2026-04-01&end=2026-10-31`.
New protected APIs: `/api/sales-tsk-monthly-analyse/options` and `/api/sales-tsk-monthly-analyse/matrix`.

The existing performance report and its redirects are not modified. This report has separate routes, template, JavaScript, scoped layout CSS, and service. It imports the existing live source connection, date parsing, filter options, parameterized predicates, and turnover aggregates. No model, migration, or snapshot is created.

### Memory and filter loading

The shared dropdown loader now queries one dimension at a time with scalar
`SELECT DISTINCT`, rather than maintaining twelve distinct array aggregates in
one query. This also benefits the original Sales & TSK report. The tradeoff is
additional source scans; verify latency against the production view. The monthly
report sets transaction-local `work_mem = '4MB'` and disables parallel query
workers so sort/hash operations can spill without multiplying parallel-worker
allocations. This is a per-operation budget, not a total PostgreSQL memory cap.

The browser reuses loaded/in-flight dropdowns for an unchanged date range.
Changing Group By requests only the matrix; Apply Filters reuses options when
dates are unchanged. Refresh explicitly reloads options, failed requests remain
retryable, and superseded date requests cannot overwrite newer results.

Use the root `./compose.sh up -d --build server` launcher to apply the server
container limit of 60% of Docker-engine RAM. This does not limit the external
database. Live query plans and memory measurements are still required to confirm
the production error is resolved.

Group By options, in order: Group, Purity, Classification, Make, Collection, Section (default), Type, Wide Range. Each groups on the corresponding `_id` field and uses the matching label column (`group` is quoted). Missing IDs form an Unspecified group. Source metadata is checked before querying; the source must provide `barcode`. Pieces count distinct non-null barcodes per grouping/month, plus one for every null-barcode row (equivalent to assigning each null a unique fallback). Missing columns produce an error naming the columns. Live schema verification is still required because the external database was unreachable during implementation.

Dates are inclusive, up to twelve calendar months, defaulting to the current financial year to date in Asia/Kolkata. All existing location, product and transaction filters are reused. Changing Group By immediately refreshes the applied date/filter selection; Apply Filters commits other edits. Query parameters preserve the selection.

Each selected month contains weight (kg) / pieces, share, net turnover, total TSK, MC Profit, and sales growth. MC Profit sums the source `mcprofit` field with its supplied signs, includes matching invoice/return records, and displays in Cr with full-value tooltips. Net turnover includes configured signed returns. Weight and TSK retain source signs. Pieces are barcode counts; monthly footer pieces sum the displayed group counts. Amounts display in Cr with full-value tooltips. Share is group net turnover / monthly net turnover, unavailable for non-positive monthly totals. Bars clamp to 0–100% but labels retain actual values. Growth is `(current - previous) / abs(previous) * 100`. First months, missing records, zero prior values, and partial boundary months are excluded from growth comparisons. Empty months have zero totals. Footer rates are computed from monthly totals, not averages of row percentages.

The new menu has its own report grant. Register on deployment:

```sh
python scripts/add_sales_tsk_monthly_analyse_menu.py
```

This idempotent script creates only the new menu and an ADMIN grant, retaining existing report menus and grants. Assign other roles through existing RBAC management; restart application workers after deployment.

Validation:

```sh
python -m unittest discover -s tests -p 'test_sales_tsk*py' -v
```

Fixture browser checks cover all eight grouping options, month-range changes, reset, mobile sidebar, and dark mode. These checks do not verify live source schema, quantities, or database query latency.
