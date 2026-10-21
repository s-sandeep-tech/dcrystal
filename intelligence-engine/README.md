# IntelligenceEngine

Autonomous, decoupled AI/ML microservice for **Time-Series Forecasting** (Prophet), **Predictive Modeling** (XGBoost), and **Hybrid External Intelligence** (Gemini API).

---

## 🌟 Key Features

1. **Zero External Project Dependencies**:
   - Runs in its own container/virtualenv.
   - Communicates via **Redis Streams** (`intelligence_queue:stream`) using JSON payloads.
2. **Exclusive PostgreSQL Database Layer**:
   - Zero coupling to `server/app/models/`.
   - Manages its own dedicated SQLAlchemy 2.0 ORM tables:
     - `intelligence_forecasts`
     - `intelligence_predictions`
     - `intelligence_external_signals`
     - `intelligence_task_runs`
3. **Hybrid Intelligence**:
   - **Internal Quantitative Modeling**:
     - **Prophet**: Non-linear time-series forecasting with trend, seasonality, and confidence intervals.
     - **XGBoost**: Feature-rich tabular regression/classification for delay risk, lead times, and SLA compliance.
   - **External Qualitative Intelligence (Gemini API)**:
     - Real-time climate alerts (monsoons, floods, severe storms), regional festivals, and supply chain disruptions.
     - Automatically blends external multipliers (`adjusted_yhat = baseline_yhat * impact_multiplier`) with quantitative forecasts.

---

## 📁 Project Structure

```
intelligence-engine/
├── Dockerfile                  # Standalone container (Python 3.11-slim)
├── requirements.txt            # ML + SQLAlchemy + Redis + Google GenAI dependencies
├── README.md                   # This documentation
├── .env.example                # Environment template
├── test_client.py              # CLI utility to dispatch test jobs and view results
└── src/
    ├── config.py               # Pydantic settings (Redis, DB, Gemini API)
    ├── worker.py               # Main Redis consumer daemon
    ├── db/
    │   ├── connection.py       # Standalone SQLAlchemy engine & auto-migration
    │   ├── models.py           # Exclusive ORM tables
    │   ├── reader.py           # Parameterized historical read queries
    │   └── writer.py           # Persistence helper
    ├── queue/
    │   ├── protocol.py         # Task & result schema definitions
    │   └── redis_manager.py    # Redis BLPOP, hash storage, and pub/sub
    ├── models/
    │   ├── forecaster.py       # Prophet time-series engine
    │   └── predictor.py        # XGBoost tabular engine
    ├── external/
    │   └── gemini_enricher.py  # Google Gemini API client
    ├── hybrid/
    │   └── orchestrator.py     # Blends Prophet + Gemini context
    └── utils/
        └── logger.py           # Structured logging
```

---

## 🚀 Running with Docker Compose

IntelligenceEngine is configured in the root `docker-compose.yml`:

```bash
# Build and run the entire stack including IntelligenceEngine
docker compose up -d --build intelligence-engine

# View logs
docker compose logs -f intelligence-engine
```

---

## 🧪 Testing via CLI

You can submit test tasks from the host machine or from inside the container:

```bash
# Test healthcheck
python test_client.py --action health

# Test Prophet forecasting
python test_client.py --action forecast --horizon 14

# Test XGBoost tabular predictions
python test_client.py --action predict

# Test Gemini climate & external signals
python test_client.py --action signals --region "Western India"

# Test Hybrid forecast (Prophet + Gemini)
python test_client.py --action hybrid --horizon 14 --region "Mumbai, Maharashtra"
```

---

## 📡 Redis API Contract

### Inbound Stream: `intelligence_queue:stream`

Requires Redis 6.2 or newer. Producers use `RedisManager.push_task()` or
`XADD intelligence_queue:stream * task '<JSON payload>'`:

```json
{
  "task_id": "req-101",
  "task_type": "hybrid_forecast",
  "payload": {
    "metric_name": "daily_order_volume",
    "horizon_days": 14,
    "region": "Maharashtra, India",
    "external_factors": ["monsoon rainstorms"],
    "series": [
      {"ds": "2026-10-01", "y": 140.0},
      {"ds": "2026-10-02", "y": 145.5}
    ]
  }
}
```

### Result Storage: `intelligence:task:{task_id}` (Hash)

- `status`: `pending` | `processing` | `retrying` | `completed` | `failed`
- `execution_time_sec`: float
- `result_json`: JSON result containing forecast / prediction payload
- `error`: Error message if failed

### Delivery, Retries and Recovery

- Consumer group: `intelligence-workers`, with a unique consumer per worker process.
- Default lease/retry delay: 120 seconds (`REDIS_TASK_LEASE_SECONDS`, minimum 30).
  A background heartbeat renews the lease every third of that interval.
- Default execution limit: 3 deliveries (`REDIS_TASK_MAX_ATTEMPTS`). Abandoned
  deliveries count toward the limit. Recovery uses `XAUTOCLAIM`; after failure,
  tasks remain pending until the lease expires, then retry automatically.
- Exhausted or malformed tasks go to `intelligence_queue:dead`. Dead-letter insertion
  and acknowledgement are atomic. Inspect with `XRANGE intelligence_queue:dead - +`.
- Task output, task-run completion and `intelligence_task_results` are committed in
  one PostgreSQL transaction. `task_id` is the idempotency key: do not reuse it for
  different requests. Terminal retries replay the stored result instead of rewriting
  outputs. PostgreSQL advisory locks prevent concurrent execution of the same task.
- Redis result/status errors propagate. If Redis fails after a database commit,
  recovery republishes the durable result before acknowledging. If the database
  is unavailable, messages remain pending even past the attempt limit until a
  terminal status can be persisted. Do not delete result receipts while duplicates
  or pending deliveries may still exist.
- Delivery is at-least-once, not exactly-once execution. External API calls and model
  file activation cannot join the PostgreSQL transaction; a crash before database
  commit may repeat those operations. Database output rows do not duplicate.

### Deployment

Stop the old intelligence workers before starting the new version; do not run
legacy `BLPOP` consumers alongside Streams workers. The new worker atomically
migrates up to 100 old `intelligence_queue` list entries per poll. The test client
and shared producer now write directly to the stream. Update external producers
to `XADD` as above; legacy list submissions remain compatible during migration.

```sh
docker compose stop intelligence-engine
docker compose up -d --no-deps --build intelligence-engine
```

Startup creates the new `intelligence_task_results` table (existing tables need
no destructive migration). Inspect pending work using:

```sh
docker compose exec redis redis-cli XPENDING intelligence_queue:stream intelligence-workers
docker compose exec redis redis-cli XLEN intelligence_queue:dead
```

To retry a dead-letter task after fixing its cause, resubmit its original payload
with a **new task_id**; otherwise the durable failed receipt is replayed.

Worker-crash recovery assumes Redis retains its data. The existing shared Redis
Compose service has no persistent volume/AOF configuration. Production must use
durable Redis storage and backups; plan a data-preserving migration before
recreating that service. This change does not restart or replace shared Redis.

### Recovery Integration Tests

Use dedicated disposable PostgreSQL and Redis instances, never production:

```sh
INTELLIGENCE_INTEGRATION_TESTS=1 REDIS_HOST=127.0.0.1 REDIS_PORT=16379 \
SQLALCHEMY_DATABASE_URI=postgresql+psycopg2://postgres:test@127.0.0.1:15432/postgres \
python -m unittest discover -s tests -v
```

# Persistent Tabular Models

Successful `TRAIN_PREDICTOR` tasks save the fitted model, category encoder,
feature schema and target metadata together. The worker reloads the active
artifact at startup. Training or saving failures leave the previous model active
and report the training task as failed. Training results include `model_id`.

`MODEL_STORE_DIR` defaults to this project's `model_store` directory. Docker
Compose mounts the `intelligence_models` named volume at `/app/model_store`.
Rebuild/recreate the worker to apply this configuration:

```sh
docker compose up -d --build intelligence-engine
```

Train once after deployment; models from the old in-memory-only implementation
cannot be recovered after that process stops. Artifacts survive container
recreation, but not deletion of the volume (`docker compose down -v`). Back up
the entire volume, including `active.json`. Older versioned artifacts remain
available; the active pointer is replaced atomically after a successful save.

Only allow trusted administrators to write this directory: joblib artifacts
can execute Python code when loaded. Do not load uploaded or third-party files.
Runtime dependency versions must match training versions; incompatible or
corrupt active artifacts stop startup instead of silently using another model.
Keep the deployed image for reproducible restarts. When upgrading ML libraries,
retrain using a separate model directory before switching production over.

With no saved model, the existing heuristic remains available and startup logs
an explicit warning. Predictions use the fitted training encoder, accept unseen
categories, and reject missing feature columns. Prefer explicit `feature_columns`
in training tasks to exclude identifiers and unintended inputs.

Run focused tests from `intelligence-engine` with its dependencies installed:

```sh
python -m unittest discover -s tests -v
```
