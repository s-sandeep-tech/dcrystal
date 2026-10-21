import time
import signal
import sys
import os
from datetime import datetime
from typing import Dict, Any

# Ensure project root is in sys.path
base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if base_dir not in sys.path:
    sys.path.insert(0, base_dir)

try:
    from src.config import settings
    from src.utils.logger import logger
    from src.db.connection import init_db, check_db_health
    from src.db.reader import DatabaseReader
    from src.db.writer import DatabaseWriter
    from src.task_queue.protocol import TaskRequest, TaskResult, TaskType, TaskStatus
    from src.task_queue.redis_manager import RedisManager
    from src.models.forecaster import TimeSeriesForecaster
    from src.models.predictor import TabularPredictor
    from src.external.gemini_enricher import GeminiExternalEnricher
    from src.hybrid.orchestrator import HybridIntelligenceOrchestrator
except ImportError:
    from .config import settings
    from .utils.logger import logger
    from .db.connection import init_db, check_db_health
    from .db.reader import DatabaseReader
    from .db.writer import DatabaseWriter
    from .task_queue.protocol import TaskRequest, TaskResult, TaskType, TaskStatus
    from .task_queue.redis_manager import RedisManager
    from .models.forecaster import TimeSeriesForecaster
    from .models.predictor import TabularPredictor
    from .external.gemini_enricher import GeminiExternalEnricher
    from .hybrid.orchestrator import HybridIntelligenceOrchestrator



class IntelligenceWorker:
    """Main worker daemon listening to Redis queue and dispatching AI/ML intelligence tasks."""

    def __init__(self):
        self.running = True
        self.redis_manager = RedisManager()
        self.forecaster = TimeSeriesForecaster()
        self.predictor = TabularPredictor()
        self.enricher = GeminiExternalEnricher()
        self.hybrid_orchestrator = HybridIntelligenceOrchestrator()

        self._register_signals()

    def _register_signals(self):
        signal.signal(signal.SIGINT, self._handle_shutdown)
        signal.signal(signal.SIGTERM, self._handle_shutdown)

    def _handle_shutdown(self, signum, frame):
        logger.info(f"Received signal {signum}. Initiating graceful shutdown...")
        self.running = False

    def start(self):
        """Starts worker lifecycle."""
        logger.info("=" * 60)
        logger.info("  INTELLIGENCE ENGINE DAEMON STARTING")
        logger.info(f"  Redis Queue: {settings.REDIS_QUEUE_NAME}")
        logger.info(f"  Redis Host : {settings.REDIS_HOST}:{settings.REDIS_PORT}")
        logger.info(f"  Gemini Model: {settings.GEMINI_MODEL}")
        logger.info("=" * 60)

        # Initialize exclusive DB tables
        try:
            init_db()
        except Exception as e:
            logger.warning(f"Database initialization warning (will retry on task processing): {e}")

        # Check initial Redis connectivity
        while self.running and not self.redis_manager.ping():
            logger.warning("Waiting for Redis to become available...")
            time.sleep(3)

        logger.info("Connected to Redis broker. Worker listening for tasks...")

        while self.running:
            try:
                task = self.redis_manager.pop_task(timeout=5)
                if not task:
                    continue

                self.process_task(task)
            except Exception as e:
                logger.error(f"Unexpected error in consumer loop: {e}", exc_info=True)
                time.sleep(1)

        logger.info("Intelligence Worker terminated cleanly.")

    def process_task(self, task: TaskRequest):
        """Dispatches and processes a single task request."""
        task_id = task.task_id
        task_type = task.task_type
        payload = task.payload or {}

        logger.info(f"[{task_id}] Received task '{task_type.value}'")
        start_time = time.time()

        # Update Redis & DB status
        self.redis_manager.update_task_status(task_id, TaskStatus.PROCESSING)
        DatabaseWriter.log_task_start(task_id, task_type.value, parameters=payload)

        result_data: Dict[str, Any] = {}
        error_msg = None
        status = TaskStatus.COMPLETED

        try:
            if task_type == TaskType.HEALTH:
                db_healthy = check_db_health()
                redis_healthy = self.redis_manager.ping()
                result_data = {
                    "service": "intelligence-engine",
                    "status": "healthy" if db_healthy and redis_healthy else "degraded",
                    "database_connected": db_healthy,
                    "redis_connected": redis_healthy,
                    "timestamp": datetime.utcnow().isoformat()
                }

            elif task_type == TaskType.FORECAST:
                metric_name = payload.get("metric_name", "order_volume")
                horizon_days = int(payload.get("horizon_days", 14))
                series = payload.get("series")

                # If no series in payload, attempt to query from DB
                if not series:
                    series = DatabaseReader.get_order_timeseries(
                        start_date=payload.get("start_date"),
                        end_date=payload.get("end_date"),
                        dimension=payload.get("dimension"),
                        dimension_value=payload.get("dimension_value")
                    )

                forecast_res = self.forecaster.run_forecast(series, horizon_days=horizon_days)
                forecast_items = forecast_res.get("forecast", [])

                # Persist to exclusive forecasts table
                DatabaseWriter.save_forecasts(
                    task_id=task_id,
                    metric_name=metric_name,
                    forecast_items=forecast_items,
                    dimension=payload.get("dimension")
                )

                result_data = {
                    "metric_name": metric_name,
                    "horizon_days": horizon_days,
                    "forecast": forecast_items,
                    "metrics": forecast_res.get("metrics", {})
                }

            elif task_type == TaskType.PREDICT:
                records = payload.get("records")
                prediction_type = payload.get("prediction_type", "delay_risk")

                if not records:
                    records = DatabaseReader.get_tabular_orders_for_prediction(
                        status=payload.get("status"),
                        limit=int(payload.get("limit", 200))
                    )

                predictions = self.predictor.predict(records, prediction_type=prediction_type)

                # Persist to exclusive predictions table
                DatabaseWriter.save_predictions(task_id=task_id, prediction_items=predictions)

                result_data = {
                    "prediction_type": prediction_type,
                    "count": len(predictions),
                    "predictions": predictions
                }

            elif task_type == TaskType.HYBRID_FORECAST:
                metric_name = payload.get("metric_name", "order_volume")
                horizon_days = int(payload.get("horizon_days", 14))
                region = payload.get("region", "India")
                external_factors = payload.get("external_factors")
                series = payload.get("series")

                if not series:
                    series = DatabaseReader.get_order_timeseries(
                        start_date=payload.get("start_date"),
                        end_date=payload.get("end_date")
                    )

                result_data = self.hybrid_orchestrator.run_hybrid_forecast(
                    task_id=task_id,
                    metric_name=metric_name,
                    series_data=series,
                    horizon_days=horizon_days,
                    region=region,
                    external_factors=external_factors,
                    dimension=payload.get("dimension")
                )

            elif task_type == TaskType.EXTERNAL_SIGNALS:
                region = payload.get("region", "India")
                industry = payload.get("industry", "jewelry_manufacturing_and_retail")
                factors = payload.get("factors")

                signals = self.enricher.analyze_external_context(
                    region=region,
                    industry=industry,
                    specific_factors=factors
                )

                # Save signal
                signal_id = DatabaseWriter.save_external_signal(
                    event_type=signals.get("event_type", "climate"),
                    summary=signals.get("summary", ""),
                    region=region,
                    severity=signals.get("severity", "medium"),
                    impact_direction=signals.get("impact_direction", "neutral"),
                    impact_multiplier=float(signals.get("impact_multiplier", 1.0)),
                    raw_response=signals
                )
                signals["signal_id"] = signal_id
                result_data = signals

            elif task_type == TaskType.TRAIN_PREDICTOR:
                records = payload.get("training_records")
                if not records:
                    records = DatabaseReader.get_tabular_orders_for_prediction(limit=1000)
                target_col = payload.get("target_column", "risk_level")
                fit_res = self.predictor.train_or_fit(records, target_column=target_col)
                result_data = fit_res

            else:
                error_msg = f"Unsupported task type '{task_type}'"
                status = TaskStatus.FAILED

        except Exception as e:
            logger.error(f"[{task_id}] Task processing failed: {e}", exc_info=True)
            error_msg = str(e)
            status = TaskStatus.FAILED

        exec_time = round(time.time() - start_time, 3)

        # Log finish to DB
        DatabaseWriter.log_task_finish(task_id, status=status.value, error_message=error_msg)

        # Save result to Redis
        task_result = TaskResult(
            task_id=task_id,
            task_type=task_type,
            status=status,
            execution_time_sec=exec_time,
            result=result_data,
            error=error_msg
        )
        self.redis_manager.save_task_result(task_result)

        logger.info(f"[{task_id}] Task finished with status '{status.value}' in {exec_time}s")

if __name__ == "__main__":
    worker = IntelligenceWorker()
    worker.start()
