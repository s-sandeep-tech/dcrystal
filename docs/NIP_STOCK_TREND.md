# NIP Stock Trend Analysis

- Route: `/nip-stock-trend-analysis`.
- Source: `ext_view.vw_weight_level_excess_nip_barcode_data`.
- Snapshot: `nip_stock_trend_snapshots`.
- Settings task: **NIP Stock Trend Analysis Sync**, key `nip_stock_trend` (manual).
- Each comparison group shows Total Stock, NIP Stock (`is_nip=true`), and Excess Stock
  (`is_excess=true`). There is no implicit NIP-only filter. Explicit sidebar filters
  apply to all three series. NIP and Excess may overlap and must not be added to Total.

The sync streams 20,000 rows per batch in one consistent source transaction. It
validates nonempty data, non-null unique `(date, uid)` keys and exact row/weight/pieces
totals before publishing. Dates present in the source are replaced atomically;
older dates absent from the source remain. Failed syncs retain the previous data.
Source rows must be barcode stock balances, not duplicate joins or stock movements.
Historical dates cannot be reconstructed from a current-only view. Such a view
starts with one reporting date and accumulates dates on subsequent syncs.

Gross weight is SUM(gross_wt)/1000 kg; pieces is SUM(pieces). NIP/Excess use conditional
SUM on the same measure and filtered records. Summary indicators use Total only.
The table and Excel show the same three measures. Null measurements
remain unavailable. For weeks (Monday start), months, calendar quarters and years,
select the last available **common reporting date** in each period, then display
that day's grouped balance. Never sum daily balances across the interval.
Absent group/date points are gaps, not backfilled or interpolated observations.

Opening and closing are the first/last observed daily filtered portfolio balance.
Change = closing - opening; change % = change/opening*100 (N/A when opening=0).
Average is the mean of observed daily balances, not the mean of sampled period ends.
The optional moving average is trailing three displayed periods and requires all
three values. Table, graph, summaries and Excel share the applied filters.

State, Branch Status and Top/Middle/Bottom Category are disabled because the view
does not supply them and a category rule was not specified. No values are inferred.
Business-head and showroom-manager branch restrictions reuse existing local branch
metadata; report access is controlled through normal menu assignments. Assign the
new menu through RBAC after running the registration SQL. No roles are auto-granted.

Deployment: restart server and sync-consumer, register/assign the report menu, then
run the new Settings sync. Table creation is automatic on first sync. No existing
inventory/fulfilment snapshots or scheduled tasks are changed.
