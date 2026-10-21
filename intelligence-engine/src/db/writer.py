from datetime import datetime, date
from typing import List, Dict, Any, Optional
from .connection import get_db_session
from .models import (
    IntelligenceForecast,
    IntelligencePrediction,
    IntelligenceExternalSignal,
    IntelligenceTaskRun
)
from ..utils.logger import logger

class DatabaseWriter:
    """Handles persisting ML and hybrid intelligence outputs into exclusive tables."""

    @staticmethod
    def log_task_start(task_id: str, task_type: str, parameters: Optional[Dict[str, Any]] = None) -> None:
        """Records task entry in intelligence_task_runs with 'processing' status."""
        try:
            with get_db_session() as session:
                task_run = session.query(IntelligenceTaskRun).filter_by(task_id=task_id).first()
                if task_run is None:
                    task_run = IntelligenceTaskRun(task_id=task_id, task_type=task_type)
                    session.add(task_run)
                task_run.status = "processing"
                task_run.start_time = datetime.utcnow()
                task_run.end_time = None
                task_run.error_message = None
                task_run.parameters_json = parameters
                session.flush()
        except Exception as e:
            logger.error(f"Failed to log task start for {task_id}: {e}")
            raise

    @staticmethod
    def log_task_finish(task_id: str, status: str = "completed", error_message: Optional[str] = None) -> None:
        """Updates task run status, duration, and error message if failed."""
        try:
            with get_db_session() as session:
                task_run = session.query(IntelligenceTaskRun).filter_by(task_id=task_id).first()
                if task_run is None:
                    raise RuntimeError(f"Missing task run {task_id}")
                if task_run:
                    now = datetime.utcnow()
                    task_run.status = status
                    task_run.end_time = now
                    if task_run.start_time:
                        task_run.duration_seconds = (now - task_run.start_time).total_seconds()
                    task_run.error_message = error_message
        except Exception as e:
            logger.error(f"Failed to log task finish for {task_id}: {e}")
            raise

    @staticmethod
    def save_forecasts(
        task_id: str,
        metric_name: str,
        forecast_items: List[Dict[str, Any]],
        dimension: Optional[str] = None
    ) -> int:
        """
        Batch inserts forecast intervals into intelligence_forecasts.
        """
        if not forecast_items:
            return 0

        inserted_count = 0
        try:
            with get_db_session() as session:
                for item in forecast_items:
                    ds_val = item.get("ds")
                    if isinstance(ds_val, str):
                        ds_date = datetime.strptime(ds_val[:10], "%Y-%m-%d").date()
                    elif isinstance(ds_val, (datetime, date)):
                        ds_date = ds_val if isinstance(ds_val, date) else ds_val.date()
                    else:
                        raise ValueError("Forecast row is missing a valid date")

                    record = IntelligenceForecast(
                        task_id=task_id,
                        metric_name=metric_name,
                        dimension=dimension,
                        ds=ds_date,
                        baseline_yhat=float(item.get("baseline_yhat", item.get("yhat", 0.0))),
                        adjusted_yhat=float(item.get("adjusted_yhat")) if item.get("adjusted_yhat") is not None else None,
                        yhat_lower=float(item.get("yhat_lower")) if item.get("yhat_lower") is not None else None,
                        yhat_upper=float(item.get("yhat_upper")) if item.get("yhat_upper") is not None else None,
                        external_multiplier=float(item.get("external_multiplier", 1.0))
                    )
                    session.add(record)
                    inserted_count += 1
            logger.info(f"Successfully saved {inserted_count} forecast entries for task {task_id}")
            return inserted_count
        except Exception as e:
            logger.error(f"Failed to save forecasts for task {task_id}: {e}", exc_info=True)
            raise

    @staticmethod
    def save_predictions(
        task_id: str,
        prediction_items: List[Dict[str, Any]]
    ) -> int:
        """
        Batch inserts predictions into intelligence_predictions.
        """
        if not prediction_items:
            return 0

        inserted_count = 0
        try:
            with get_db_session() as session:
                for item in prediction_items:
                    record = IntelligencePrediction(
                        task_id=task_id,
                        entity_type=item.get("entity_type", "order"),
                        entity_id=str(item.get("entity_id", "unknown")),
                        prediction_type=item.get("prediction_type", "delay_risk"),
                        predicted_value=float(item.get("predicted_value")) if item.get("predicted_value") is not None else None,
                        risk_score=float(item.get("risk_score")) if item.get("risk_score") is not None else None,
                        confidence=float(item.get("confidence")) if item.get("confidence") is not None else None,
                        features_json=item.get("features_json") or item.get("features")
                    )
                    session.add(record)
                    inserted_count += 1
            logger.info(f"Successfully saved {inserted_count} predictions for task {task_id}")
            return inserted_count
        except Exception as e:
            logger.error(f"Failed to save predictions for task {task_id}: {e}", exc_info=True)
            raise

    @staticmethod
    def save_external_signal(
        event_type: str,
        summary: str,
        region: Optional[str] = None,
        severity: str = "medium",
        impact_direction: str = "neutral",
        impact_multiplier: float = 1.0,
        raw_response: Optional[Dict[str, Any]] = None,
        valid_from: Optional[datetime] = None,
        valid_until: Optional[datetime] = None
    ) -> Optional[int]:
        """Saves a Gemini-derived external context event into intelligence_external_signals."""
        try:
            with get_db_session() as session:
                signal = IntelligenceExternalSignal(
                    event_type=event_type,
                    region=region,
                    severity=severity,
                    impact_direction=impact_direction,
                    impact_multiplier=impact_multiplier,
                    summary=summary,
                    source="gemini_api",
                    raw_response=raw_response,
                    valid_from=valid_from or datetime.utcnow(),
                    valid_until=valid_until
                )
                session.add(signal)
                session.flush()
                return signal.id
        except Exception as e:
            logger.error(f"Failed to save external signal: {e}", exc_info=True)
            raise
