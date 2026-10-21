# IntelligenceEngine

Autonomous, decoupled AI/ML microservice for **Time-Series Forecasting** (Prophet), **Predictive Modeling** (XGBoost), and **Hybrid External Intelligence** (Gemini API).

---

## 🌟 Key Features

1. **Zero External Project Dependencies**:
   - Runs in its own container/virtualenv.
   - Communicates strictly via **Redis queue** (`intelligence_queue`) using JSON payloads.
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

### Inbound Queue: `intelligence_queue` (List)

Tasks are pushed via `RPUSH` / `LPUSH`:

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

- `status`: `pending` | `processing` | `completed` | `failed`
- `execution_time_sec`: float
- `result_json`: JSON result containing forecast / prediction payload
- `error`: Error message if failed
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
