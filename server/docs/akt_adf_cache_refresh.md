# AKT data-load completion callback

The existing ADF job calls `/api/akt/trigger-sync` on the deployed application. This repository contains the receiver, not the ADF pipeline or the source-table loader.

The callback must run after a successful, committed load of `muziris.akt_dhanteras_saledetails`. It should not run in parallel with the load or on a failure path. ADF activity dependencies cannot be verified or changed from this repository.

POST is preferred; the existing GET callback remains compatible. An optional JSON body is supported:

```json
{"message": "AKT data load completed"}
```

On success, the endpoint advances the persistent Redis cache generation, deletes all existing Transaction Performance filter-cache keys, and sends a refresh notification. Report responses retain a 3,000-second (50-minute) cache expiry. Reports already being calculated during the callback can only populate their old generation, which subsequent requests no longer read.

The callback returns HTTP 503 when invalidation fails. Configure retries for the ADF callback activity and retain a failed status if retries are exhausted. It no longer reports success when Redis cache invalidation fails. Repeated successful calls are safe; they advance the generation again and clear caches again.

Direct source-table updates without this callback are not automatically detected.

## Concurrent refreshes

Each generation and filter combination has a unique Redis lease. Its owner renews the lease while calculating the report, then atomically publishes the result (50-minute expiry) and releases ownership. Requests that lose the acquisition race recheck the cache before calculating. A request waits up to two seconds for an existing result, then returns HTTP 202 with Retry-After: 2; the report page polls automatically with a bounded retry count.

Different filters have independent leases. A dead worker's lease expires; an old owner cannot publish data or delete a successor's lock. If Redis is unavailable, report calculation returns HTTP 503 rather than allowing concurrent uncached database work. This replaces the previous direct-database fallback during a Redis outage.
