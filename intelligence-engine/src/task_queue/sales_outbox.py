import json
from sqlalchemy import text
from ..db.connection import get_db_session


def publish_sales_outbox(queue):
    """Retry producer failures; duplicate stream entries share the same task ID."""
    with get_db_session() as session:
        if not session.execute(text("SELECT to_regclass('sales_turnover_forecast_runs')")).scalar():
            return
        rows = session.execute(text('''SELECT task_id, snapshot_run_id, branch_id, created_at
            FROM sales_turnover_forecast_runs WHERE queued_at IS NULL
            ORDER BY created_at LIMIT 20 FOR UPDATE SKIP LOCKED''')).mappings().all()
        for row in rows:
            task = {'task_id': row['task_id'], 'task_type': 'sales_turnover_forecast',
                    'created_at': row['created_at'].isoformat(),
                    'payload': {'snapshot_run_id': row['snapshot_run_id'], 'branch_id': row['branch_id']}}
            queue.client.xadd(queue.stream, {'task': json.dumps(task)})
            session.execute(text('UPDATE sales_turnover_forecast_runs SET queued_at = CURRENT_TIMESTAMP WHERE task_id = :id'),
                            {'id': row['task_id']})
