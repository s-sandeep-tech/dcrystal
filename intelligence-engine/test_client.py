#!/usr/bin/env python3
"""
Test client to enqueue tasks to IntelligenceEngine via Redis and poll/wait for results.
Can be executed directly from host or inside docker.
"""
import time
import json
import uuid
import sys
import argparse
from datetime import datetime, timedelta

try:
    from src.config import settings
    from src.task_queue.protocol import TaskRequest, TaskType, TaskStatus
    from src.task_queue.redis_manager import RedisManager
except ImportError:
    # Ensure src is in search path
    import os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from src.config import settings
    from src.task_queue.protocol import TaskRequest, TaskType, TaskStatus
    from src.task_queue.redis_manager import RedisManager


def generate_sample_timeseries(days: int = 30):
    """Generates synthetic historical order volume series."""
    base_date = datetime.now() - timedelta(days=days)
    series = []
    for i in range(days):
        dt = base_date + timedelta(days=i)
        # Weekly pattern: higher on Mon-Wed, lower on Sun
        day_mult = 0.7 if dt.weekday() == 6 else 1.15
        val = round((100 + (i * 1.5) + (i % 7) * 8) * day_mult, 1)
        series.append({"ds": dt.strftime("%Y-%m-%d"), "y": val})
    return series

def generate_sample_orders():
    """Generates synthetic order records for tabular risk prediction."""
    return [
        {
            "order_id": "ORD-1001",
            "priority": "Critical Urgent",
            "collection_type": "Bridal Gold",
            "origin": "Factory-A",
            "destination": "Showroom-Mumbai",
            "risk_level": 45
        },
        {
            "order_id": "ORD-1002",
            "priority": "Normal",
            "collection_type": "Lightweight Diamond",
            "origin": "Factory-B",
            "destination": "Showroom-Delhi",
            "risk_level": 10
        },
        {
            "order_id": "ORD-1003",
            "priority": "High",
            "collection_type": "Antique Temple",
            "origin": "Central Hub",
            "destination": "Showroom-Bangalore",
            "risk_level": 25
        }
    ]

def main():
    parser = argparse.ArgumentParser(description="IntelligenceEngine Test Task Dispatcher")
    parser.add_argument(
        "--action",
        choices=["health", "forecast", "predict", "hybrid", "signals"],
        default="hybrid",
        help="Task type to submit"
    )
    parser.add_argument("--horizon", type=int, default=14, help="Forecast horizon days")
    parser.add_argument("--region", type=str, default="Western India", help="Region for climate context")
    args = parser.parse_args()

    redis_mgr = RedisManager()
    if not redis_mgr.ping():
        print(f"[ERROR] Cannot connect to Redis at {settings.REDIS_HOST}:{settings.REDIS_PORT}")
        sys.exit(1)

    task_id = f"test-{uuid.uuid4().hex[:8]}"

    if args.action == "health":
        task = TaskRequest(
            task_id=task_id,
            task_type=TaskType.HEALTH,
            payload={}
        )
    elif args.action == "forecast":
        task = TaskRequest(
            task_id=task_id,
            task_type=TaskType.FORECAST,
            payload={
                "metric_name": "daily_order_volume",
                "horizon_days": args.horizon,
                "series": generate_sample_timeseries(35)
            }
        )
    elif args.action == "predict":
        task = TaskRequest(
            task_id=task_id,
            task_type=TaskType.PREDICT,
            payload={
                "prediction_type": "order_delay_risk",
                "records": generate_sample_orders()
            }
        )
    elif args.action == "signals":
        task = TaskRequest(
            task_id=task_id,
            task_type=TaskType.EXTERNAL_SIGNALS,
            payload={
                "region": args.region,
                "factors": ["monsoon", "highway logistics disruptions", "upcoming festival rush"]
            }
        )
    else:  # hybrid
        task = TaskRequest(
            task_id=task_id,
            task_type=TaskType.HYBRID_FORECAST,
            payload={
                "metric_name": "showroom_demand",
                "horizon_days": args.horizon,
                "region": args.region,
                "external_factors": ["monsoon rainstorms", "Dhanteras festival advance orders"],
                "series": generate_sample_timeseries(40)
            }
        )

    print(f"\n[1] Enqueuing task '{task.task_type.value}' (ID: {task_id}) to Redis stream '{redis_mgr.stream}'...")
    success = redis_mgr.push_task(task)
    if not success:
        print("[ERROR] Failed to push task to Redis.")
        sys.exit(1)

    print(f"[2] Waiting for IntelligenceEngine worker to process...")
    max_wait = redis_mgr.max_attempts * (redis_mgr.lease_ms / 1000 + 60)
    start = time.time()
    result = None

    while time.time() - start < max_wait:
        result = redis_mgr.get_task_result(task_id)
        if result and result.get("status") in [TaskStatus.COMPLETED.value, TaskStatus.FAILED.value]:
            break
        time.sleep(0.5)

    if not result or result.get("status") not in [TaskStatus.COMPLETED.value, TaskStatus.FAILED.value]:
        print(f"[TIMEOUT] No result returned within {max_wait} seconds.")
        print(f"Make sure intelligence-engine worker is running (`python src/worker.py` or docker container).")
        sys.exit(1)

    print(f"\n[3] Result Received in {result.get('execution_time_sec')}s! Status: {result.get('status')}")
    print("=" * 60)
    print(json.dumps(result.get("result", {}), indent=2))
    if result.get("error"):
        print(f"Error: {result['error']}")
    print("=" * 60)
    if result.get("status") == TaskStatus.FAILED.value:
        sys.exit(1)

if __name__ == "__main__":
    main()
