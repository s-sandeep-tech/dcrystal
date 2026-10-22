import json
import os
from datetime import datetime
from uuid import uuid4
from sqlalchemy import func
from app.extensions import db, redis_client
from app.models.sales_prediction import SalesPredictionSyncRun, SalesTurnoverDailySnapshot as Daily, SalesTurnoverForecastRun as Forecast


def latest_snapshot():
    return SalesPredictionSyncRun.query.order_by(SalesPredictionSyncRun.created_at.desc()).first()


def enqueue_sales_forecast(user_id, branch_id=None, include_external=False, run_id=None):
    run = db.session.get(SalesPredictionSyncRun, run_id) if run_id else latest_snapshot()
    if not run:
        raise ValueError('Run Sales Prediction Data Sync first')
    if branch_id is not None and not Daily.query.filter_by(run_id=run.id, branch_id=branch_id).first():
        raise ValueError('Location is not present in this sales snapshot')
    task_id = str(uuid4())
    record = Forecast(task_id=task_id, snapshot_run_id=run.id, branch_id=branch_id,
                      requested_by=int(user_id), include_external=include_external)
    db.session.add(record)
    db.session.commit()
    payload = {'task_id': task_id, 'task_type': 'sales_turnover_forecast',
               'created_at': datetime.utcnow().isoformat(),
               'payload': {'snapshot_run_id': run.id, 'branch_id': branch_id}}
    try:
        redis_client.xadd(os.getenv('REDIS_QUEUE_NAME', 'intelligence_queue') + ':stream', {'task': json.dumps(payload)})
        record.queued_at = datetime.utcnow()
        db.session.commit()
    except Exception:
        # Keep the durable request. The intelligence worker republishes the outbox.
        db.session.rollback()
    return {'task_id': task_id, 'status': 'pending', 'message': 'Three-day turnover forecast queued'}


def report_data(branch_id=None):
    run = latest_snapshot()
    if not run:
        return {'snapshot': None, 'locations': [], 'history': [], 'forecast_run': None}
    locations = [{'id': r[0], 'name': r[1]} for r in db.session.query(Daily.branch_id, func.max(Daily.location_name))
                 .filter(Daily.run_id == run.id).group_by(Daily.branch_id).order_by(func.max(Daily.location_name))]
    query = db.session.query(Daily.sales_date, func.sum(Daily.net_turnover)).filter(Daily.run_id == run.id)
    if branch_id is not None:
        query = query.filter(Daily.branch_id == branch_id)
    history = [{'ds': d.isoformat(), 'y': float(y)} for d, y in query.group_by(Daily.sales_date).order_by(Daily.sales_date)]
    forecast = Forecast.query.filter_by(snapshot_run_id=run.id, branch_id=branch_id).order_by(Forecast.created_at.desc()).first()
    return {'snapshot': {'id': run.id, 'cutoff_date': run.cutoff_date.isoformat(),
                         'synced_at': run.created_at.isoformat() + 'Z', 'source_count': run.source_count,
                         'diagnostics': run.diagnostics}, 'locations': locations, 'history': history,
            'forecast_run': {'task_id': forecast.task_id, 'result': forecast.result_json} if forecast else None}
