# Purchase plan branch filters

Branch Type and Branch Status are multi-select filters on
`/sales-stock-composition-analysis-for-purchase-plan`. They apply to sales,
provision/shop stock, drilldowns, contributor charts and location factors.
Export requests include the selected values as arrays.

Before deploying the updated application against an existing database, run:

```sh
docker compose exec -T db psql -U meetaccess -d dcrystaldb < server/scripts/add_composition_branch_filters.sql
docker compose up -d --build server sync-consumer
```

Then run the existing Sales & Stock Composition Analysis sync. Its source is
`ext_view.item_wise_tsk_summary_view`; the sync now maps `branch_type` and
`branch_status`, also accepting quoted `Branch_type` and `Branch_status` column
names. The source reader already uses `SELECT *`, so no additional source query
is needed. Missing/null/blank values appear as `(Unspecified)` in the filters.
Existing snapshot rows remain unspecified until resynced. If the external view
does not expose these fields, its owner must add them to populate the filters.
