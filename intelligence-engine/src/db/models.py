from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, DateTime, Date, Text, JSON, Boolean, Index
)
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class IntelligenceTaskResult(Base):
    """Durable terminal result, committed with task output rows."""
    __tablename__ = "intelligence_task_results"
    task_id = Column(String(100), primary_key=True)
    result_json = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

class IntelligenceForecast(Base):
    """Stores quantitative and hybrid time-series projections."""
    __tablename__ = 'intelligence_forecasts'

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String(100), index=True, nullable=False)
    metric_name = Column(String(100), index=True, nullable=False)
    dimension = Column(String(100), nullable=True)  # e.g., location, showroom, category
    ds = Column(Date, nullable=False, index=True)
    baseline_yhat = Column(Float, nullable=False)
    adjusted_yhat = Column(Float, nullable=True)
    yhat_lower = Column(Float, nullable=True)
    yhat_upper = Column(Float, nullable=True)
    external_multiplier = Column(Float, default=1.0)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index('idx_forecast_metric_ds', 'metric_name', 'ds'),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "task_id": self.task_id,
            "metric_name": self.metric_name,
            "dimension": self.dimension,
            "ds": self.ds.isoformat() if self.ds else None,
            "baseline_yhat": self.baseline_yhat,
            "adjusted_yhat": self.adjusted_yhat,
            "yhat_lower": self.yhat_lower,
            "yhat_upper": self.yhat_upper,
            "external_multiplier": self.external_multiplier,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


class IntelligencePrediction(Base):
    """Stores tabular regression/classification predictions (e.g. XGBoost delay risks)."""
    __tablename__ = 'intelligence_predictions'

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String(100), index=True, nullable=False)
    entity_type = Column(String(50), index=True, nullable=False)  # 'order', 'supplier', 'product'
    entity_id = Column(String(100), index=True, nullable=False)
    prediction_type = Column(String(50), index=True, nullable=False)  # 'delay_risk', 'lead_time'
    predicted_value = Column(Float, nullable=True)
    risk_score = Column(Float, nullable=True)  # Normalized 0.0 - 1.0
    confidence = Column(Float, nullable=True)
    features_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "task_id": self.task_id,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "prediction_type": self.prediction_type,
            "predicted_value": self.predicted_value,
            "risk_score": self.risk_score,
            "confidence": self.confidence,
            "features_json": self.features_json,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


class IntelligenceExternalSignal(Base):
    """Stores Gemini-extracted climate alerts, macroeconomic events, and disruption factors."""
    __tablename__ = 'intelligence_external_signals'

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_type = Column(String(50), index=True, nullable=False)  # 'climate', 'festival', 'logistics'
    region = Column(String(100), index=True, nullable=True)
    severity = Column(String(50), default='medium')  # 'low', 'medium', 'high', 'extreme'
    impact_direction = Column(String(20), default='neutral')  # 'negative', 'positive', 'neutral'
    impact_multiplier = Column(Float, default=1.0)
    summary = Column(Text, nullable=False)
    source = Column(String(100), default='gemini_api')
    raw_response = Column(JSON, nullable=True)
    valid_from = Column(DateTime, nullable=True)
    valid_until = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "event_type": self.event_type,
            "region": self.region,
            "severity": self.severity,
            "impact_direction": self.impact_direction,
            "impact_multiplier": self.impact_multiplier,
            "summary": self.summary,
            "source": self.source,
            "valid_from": self.valid_from.isoformat() if self.valid_from else None,
            "valid_until": self.valid_until.isoformat() if self.valid_until else None,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


class IntelligenceTaskRun(Base):
    """Audit logs for tasks processed by IntelligenceEngine."""
    __tablename__ = 'intelligence_task_runs'

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String(100), unique=True, index=True, nullable=False)
    task_type = Column(String(50), index=True, nullable=False)
    status = Column(String(50), default='pending', index=True)  # 'pending', 'processing', 'completed', 'failed'
    start_time = Column(DateTime, default=datetime.utcnow, nullable=False)
    end_time = Column(DateTime, nullable=True)
    duration_seconds = Column(Float, nullable=True)
    parameters_json = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "task_id": self.task_id,
            "task_type": self.task_type,
            "status": self.status,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_seconds": self.duration_seconds,
            "parameters_json": self.parameters_json,
            "error_message": self.error_message
        }
