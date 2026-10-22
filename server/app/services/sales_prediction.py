import json
import os
from datetime import datetime
from uuid import uuid4
from sqlalchemy import func, text
from app.extensions import db, redis_client
from app.models.sales_prediction import (
    SalesPredictionSyncRun,
    SalesTurnoverDailySnapshot as Daily,
    SalesTurnoverForecastRun as Forecast,
    SalesPrediction,
)


def latest_snapshot():
    return SalesPredictionSyncRun.query.order_by(SalesPredictionSyncRun.created_at.desc()).first()


def enqueue_sales_forecast(user_id, branch_id=None, include_external=False, run_id=None, allow_gemini_fallback=False):
    if allow_gemini_fallback and not include_external:
        raise ValueError('Enable external data before enabling Gemini fallback')
    run = db.session.get(SalesPredictionSyncRun, run_id) if run_id else latest_snapshot()
    if not run:
        raise ValueError('Run Sales Prediction Data Sync first')
    if branch_id is not None and not Daily.query.filter_by(run_id=run.id, branch_id=branch_id).first():
        raise ValueError('Location is not present in this sales snapshot')
    task_id = str(uuid4())
    record = Forecast(task_id=task_id, snapshot_run_id=run.id, branch_id=branch_id,
                      requested_by=int(user_id), include_external=include_external,
                      allow_gemini_fallback=allow_gemini_fallback)
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
        return {'snapshot': None, 'locations': [], 'history': [], 'predictions': [], 'forecast_run': None}
    locations = [{'id': r[0], 'name': r[1]} for r in db.session.query(Daily.branch_id, func.max(Daily.location_name))
                 .filter(Daily.run_id == run.id).group_by(Daily.branch_id).order_by(func.max(Daily.location_name))]
    query = db.session.query(Daily.sales_date, func.sum(Daily.net_turnover)).filter(Daily.run_id == run.id)
    if branch_id is not None:
        query = query.filter(Daily.branch_id == branch_id)
    history = [{'ds': d.isoformat(), 'y': float(y)} for d, y in query.group_by(Daily.sales_date).order_by(Daily.sales_date)]

    # Query unversioned predictions for this branch/all-locations
    predictions = []
    try:
        if db.session.execute(text("SELECT to_regclass('sales_predictions')")).scalar():
            if branch_id is not None:
                rows = db.session.execute(text('''
                    SELECT sales_date, predicted_turnover, yhat_lower, yhat_upper
                    FROM sales_predictions WHERE branch_id = :branch
                    ORDER BY sales_date ASC
                '''), {'branch': branch_id}).fetchall()
            else:
                rows = db.session.execute(text('''
                    SELECT sales_date, predicted_turnover, yhat_lower, yhat_upper
                    FROM sales_predictions WHERE branch_id IS NULL
                    ORDER BY sales_date ASC
                ''')).fetchall()
            predictions = [{
                'ds': r[0].isoformat() if hasattr(r[0], 'isoformat') else str(r[0]),
                'yhat': float(r[1]),
                'yhat_lower': float(r[2]) if r[2] is not None else None,
                'yhat_upper': float(r[3]) if r[3] is not None else None
            } for r in rows]

        # Fallback to intelligence_forecasts if sales_predictions has not accumulated rows yet
        if not predictions and db.session.execute(text("SELECT to_regclass('intelligence_forecasts')")).scalar():
            dim = f'branch:{branch_id}' if branch_id is not None else 'all_locations'
            fb_rows = db.session.execute(text('''
                SELECT DISTINCT ON (ds) ds, baseline_yhat, yhat_lower, yhat_upper
                FROM intelligence_forecasts
                WHERE metric_name = 'sales_net_turnover' AND (dimension = :dim OR (dimension IS NULL AND :dim = 'all_locations'))
                ORDER BY ds ASC, created_at DESC
            '''), {'dim': dim}).fetchall()
            predictions = [{
                'ds': r[0].isoformat() if hasattr(r[0], 'isoformat') else str(r[0]),
                'yhat': float(r[1]),
                'yhat_lower': float(r[2]) if r[2] is not None else None,
                'yhat_upper': float(r[3]) if r[3] is not None else None
            } for r in fb_rows]
    except Exception:
        pass

    # Forecast run is queried by branch, not tied strictly to the current snapshot_run_id
    forecast = Forecast.query.filter_by(branch_id=branch_id).order_by(Forecast.created_at.desc()).first()
    return {
        'snapshot': {'id': run.id, 'cutoff_date': run.cutoff_date.isoformat(),
                     'synced_at': run.created_at.isoformat() + 'Z', 'source_count': run.source_count,
                     'diagnostics': run.diagnostics},
        'locations': locations,
        'history': history,
        'predictions': predictions,
        'forecast_run': {'task_id': forecast.task_id, 'result': forecast.result_json} if forecast else None
    }
