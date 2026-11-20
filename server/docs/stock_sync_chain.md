# Provision and stock detail sync chain

The sync worker runs `stock_drilldown_details` immediately after each `provision_stock_status` attempt finishes, including returned failures and raised exceptions. This applies to manual, scheduler, and third-party requests, all of which use the same queue worker.

The follow-up runs inline before the worker accepts another queue item or advances a scheduled all-sync batch. It reuses the combined drill-down routine (Size Level NIP Barcode, then Stock Processed Order Details). Each task retains its own status, progress events, duration, and SyncLog entry; the follow-up inherits the initiating user. A follow-up failure does not rewrite the parent status and does not prevent the daily batch from continuing.

The separate 11:30 AM drill-down schedule is removed. The 11 AM provision schedule is retained. Daily all-sync no longer includes a separate size-level barcode refresh; manual Sync All no longer enqueues a separate combined drill-down refresh. The standalone manual buttons remain available.

The queue worker gives Process Delay, Outstanding PO, Stage Delay, Order Delay Tracking, Pending Acceptance, Rejected Weight, and Hallmarking Delayed three attempts, with a five-second pause between failed attempts. Both returned errors and raised exceptions trigger retries. Failed transactions are rolled back before retrying. Progress remains processing until attempts are exhausted, and the worker records one final SyncLog result before advancing the batch. This applies to scheduled, manual, and third-party queue requests. Owner/Showroom Combined retains its segment-level retries, and Provision/Stock retains its startup and producer retries.

Restart the sync-consumer service after deploying. No database migration is required. The chain applies to attempts that reach worker completion; forced process termination is not a completion event and does not guarantee follow-up execution.

Validation:

```sh
python -m unittest discover -s tests -p test_stock_sync_chain.py -v
python -m unittest discover -s tests -p test_location_physical_stock_ordered_details.py -v
```

These tests use mocks and fixtures; they do not perform a production sync.
