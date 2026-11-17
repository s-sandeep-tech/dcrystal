# NIP Stock Trend Analysis

- Route: `/nip-stock-trend-analysis`.
- Live source: `ext_view.vw_weight_level_excess_nip_barcode_data`.
- Rollback table: `nip_stock_trend_snapshots`.
- Each comparison group shows Total Stock, NIP Stock (`is_nip=true`), and Excess Stock
  (`is_excess=true`). There is no implicit NIP-only filter. Explicit sidebar filters
  apply to all three series. NIP and Excess may overlap and must not be added to Total.

Filter options, report data and Excel export query the external view in read-only
transactions. PostgreSQL applies the filters and aggregates the dated barcode
balances. Each request reads the view directly, including its latest reporting date.

Gross weight is SUM(gross_wt)/1000 kg; pieces is SUM(pieces). NIP/Excess use conditional
SUM on the same measure and filtered records. Summary indicators use Total only.
The table and Excel show the same three measures. Null measurements
remain unavailable. For weeks (Monday start), months, calendar quarters and years,
select the last available **common reporting date** in each period, then display
that day's grouped balance. Never sum daily balances across the interval.
Absent group/date points are gaps, not backfilled or interpolated observations.

The Line Chart tab shows exactly two portfolio series: NIP Stock and Excess Stock.
They use all filtered groups (independent of Top/Middle/Bottom limits), the selected
measurement, and the same period-end reporting dates as the bar chart. Missing
measurements remain gaps. Comparison/ranking and the bar Trendline controls are
disabled in this view; date, sidebar, interval and measurement controls still apply.

Opening and closing are the first/last observed daily filtered portfolio balance.
Change = closing - opening; change % = change/opening*100 (N/A when opening=0).
Average is the mean of observed daily balances, not the mean of sampled period ends.
The optional Trendline is a least-squares linear fit per displayed stock series,
using elapsed days between reporting dates. It requires at least two non-null
dated balances; missing values are excluded from fitting. It is a historical
trend, not a future forecast. Table, graph, summaries and Excel share the applied filters.

State, Branch Status and Category are omitted from the filter panel because the
view does not supply them and a category rule was not specified. No values are inferred.
Business-head and showroom-manager branch restrictions reuse existing local branch
metadata; report access is controlled through normal menu assignments. Assign the
new menu through RBAC after running the registration SQL. No roles are auto-granted.

Deploy the server and sync consumer together to switch report reads and retire the
manual Settings sync. The existing snapshot table and sync code are retained for
rollback. Revert the cutover and redeploy both services to restore snapshot reads
and manual refresh.
