from datetime import datetime
from enum import Enum
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

class TaskType(str, Enum):
    FORECAST = "forecast"
    PREDICT = "predict"
    HYBRID_FORECAST = "hybrid_forecast"
    EXTERNAL_SIGNALS = "external_signals"
    TRAIN_PREDICTOR = "train_predictor"
    HEALTH = "health"

class TaskStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class TaskRequest(BaseModel):
    task_id: str
    task_type: TaskType
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    reply_to: Optional[str] = None
    payload: Dict[str, Any] = Field(default_factory=dict)

class TaskResult(BaseModel):
    task_id: str
    task_type: TaskType
    status: TaskStatus
    execution_time_sec: float = 0.0
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()
