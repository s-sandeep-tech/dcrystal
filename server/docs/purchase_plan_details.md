# Purchase plan detail columns

The Purchase Plan report displays `Provision` and `Sales` after
Product Hierarchy, including every drilldown and Grand Total. Each cell shows
pieces (up to four decimal places) and weight in kilograms (three decimal places). Stored weights remain in grams;
the display divides them by 1,000.

Source: `ext_view.item_wise_tsk_summary_view`.

| Detail | Pieces | Weight |
| --- | --- | --- |
| Provision | `provision_qty` | `provision_weight` |
| Sales | `pieces` | `gross_weight` |

These are actual sums under the existing report filters and cutoff rules.
Annualisation continues to apply only to stock-turn calculations. Grand Total
uses the full filtered dataset, independent of the expanded hierarchy path.

Before deploying the updated server and sync consumer against an existing
database, apply the migration from the repository root:

```sh
docker compose exec -T db psql -v ON_ERROR_STOP=1 -U meetaccess -d dcrystaldb < server/scripts/add_composition_pieces.sql
docker compose up -d --build server sync-consumer
```

Then run the existing Sales & Stock Composition Analysis sync to populate
sales pieces and restore any fractional provision quantities truncated by
the old integer mapping. The source reader already selects all view columns.
The CSV importer also accepts `pieces` and decimal `provision_qty`.

Existing snapshots have null sales pieces until resynced. A group or total
containing missing sales quantities displays `N/A` for sales pieces; known
zero quantities display `0`. No-data totals are zero. The main-report cache
namespace is `purchase-plan:main:v3` so older cached responses are bypassed.
