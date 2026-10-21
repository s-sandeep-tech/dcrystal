import json
import redis
from typing import Optional, Dict, Any, Tuple
from ..config import settings
from ..utils.logger import logger
from .protocol import TaskRequest, TaskResult, TaskStatus

class RedisManager:
    """Manages Redis connection, queue pop operations, status reporting, and pubsub."""

    def __init__(self):
        self.client = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            password=settings.REDIS_PASSWORD,
            decode_responses=True,
            socket_timeout=15,
            socket_connect_timeout=10,
            health_check_interval=30
        )
        self.queue_name = settings.REDIS_QUEUE_NAME
        self.result_prefix = settings.REDIS_RESULT_PREFIX
        self.event_channel = settings.REDIS_EVENT_CHANNEL
        self.ttl = settings.REDIS_TASK_TTL_SECONDS

    def ping(self) -> bool:
        """Checks Redis connection health."""
        try:
            return self.client.ping()
        except Exception as e:
            logger.warning(f"Redis ping failed: {e}")
            return False

    def pop_task(self, timeout: int = 5) -> Optional[TaskRequest]:
        """
        Blocks on the task queue using BLPOP until a task arrives or timeout expires.
        """
        try:
            res = self.client.blpop(self.queue_name, timeout=timeout)
            if not res:
                return None

            _, raw_json = res
            data = json.loads(raw_json)
            return TaskRequest(**data)
        except (redis.exceptions.TimeoutError, TimeoutError):
            # Normal idle BLPOP cycle
            return None
        except json.JSONDecodeError as jde:
            logger.error(f"Malformed JSON in queue {self.queue_name}: {jde}")
            return None

            return None
        except Exception as e:
            logger.error(f"Error popping from Redis queue: {e}")
            return None

    def push_task(self, task: TaskRequest) -> bool:
        """Pushes a task into the Redis queue (useful for clients or dispatchers)."""
        try:
            self.client.rpush(self.queue_name, json.dumps(task.model_dump()))
            return True
        except Exception as e:
            logger.error(f"Failed to push task {task.task_id} to {self.queue_name}: {e}")
            return False

    def update_task_status(self, task_id: str, status: TaskStatus, progress: Optional[float] = None) -> None:
        """Updates lightweight status hash for a task."""
        key = f"{self.result_prefix}{task_id}"
        mapping = {"status": status.value}
        if progress is not None:
            mapping["progress"] = str(progress)
        try:
            self.client.hset(key, mapping=mapping)
            self.client.expire(key, self.ttl)
        except Exception as e:
            logger.error(f"Failed to update task status in Redis for {task_id}: {e}")

    def save_task_result(self, result: TaskResult) -> None:
        """Stores final task result in Redis hash and publishes notification event."""
        key = f"{self.result_prefix}{result.task_id}"
        try:
            data = result.to_dict()
            self.client.hset(
                key,
                mapping={
                    "status": result.status.value,
                    "task_type": result.task_type.value,
                    "execution_time_sec": str(result.execution_time_sec),
                    "result_json": json.dumps(result.result or {}),
                    "error": result.error or "",
                    "completed_at": result.created_at
                }
            )
            self.client.expire(key, self.ttl)

            # Publish completion event
            self.client.publish(
                self.event_channel,
                json.dumps({
                    "event": "task_completed" if result.status == TaskStatus.COMPLETED else "task_failed",
                    "task_id": result.task_id,
                    "task_type": result.task_type.value,
                    "status": result.status.value
                })
            )
        except Exception as e:
            logger.error(f"Failed to save task result in Redis for {result.task_id}: {e}")

    def get_task_result(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves task status and result from Redis hash."""
        key = f"{self.result_prefix}{task_id}"
        try:
            raw = self.client.hgetall(key)
            if not raw:
                return None
            if "result_json" in raw and raw["result_json"]:
                raw["result"] = json.loads(raw["result_json"])
            return raw
        except Exception as e:
            logger.error(f"Error fetching task {task_id} from Redis: {e}")
            return None
