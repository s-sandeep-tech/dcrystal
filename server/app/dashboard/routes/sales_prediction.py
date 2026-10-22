import json
import os
from flask import jsonify, render_template, request
from flask_jwt_extended import get_jwt_identity
from sqlalchemy import text
from app.dashboard import dashboard_bp
from app.extensions import db, redis_client
from app.models.auth import User
from app.models.sales_prediction import SalesTurnoverForecastRun
from app.services.sales_prediction import report_data, enqueue_sales_forecast
from app.utils.access_policy import effective_roles
from app.utils.decorators import require_report_access, require_role

REPORT = '/sales-turnover-forecast'


@dashboard_bp.route(REPORT)
@require_report_access(REPORT)
def sales_turnover_forecast_page():
    roles = effective_roles(db.session.get(User, int(get_jwt_identity())))
    return render_template('sales_turnover_forecast.html', can_forecast=bool(roles & {'ADMIN', 'DATA_SYNC_USER'}),
                           unread_count=0, sync_time='')


@dashboard_bp.route('/api/sales-turnover-forecast/data')
@require_report_access(REPORT)
def sales_turnover_forecast_data():
    try:
        branch = int(request.args['branch_id']) if request.args.get('branch_id') else None
        return jsonify(report_data(branch))
    except ValueError:
        return jsonify(message='Invalid location'), 400


@dashboard_bp.route('/api/sales-turnover-forecast/run', methods=['POST'])
@require_role(['ADMIN', 'DATA_SYNC_USER'])
def start_sales_turnover_forecast():
    try:
        body = request.get_json(silent=True) or {}
        branch = int(body['branch_id']) if body.get('branch_id') else None
        if type(body.get('include_external', False)) is not bool:
            raise ValueError('External context must be enabled or disabled')
        return jsonify(enqueue_sales_forecast(get_jwt_identity(), branch, body.get('include_external', False))), 202
    except (ValueError, TypeError) as error:
        return jsonify(message=str(error)), 400
    except Exception:
        db.session.rollback()
        return jsonify(message='Unable to queue forecast. Check the worker and Redis connection.'), 503


@dashboard_bp.route('/api/sales-turnover-forecast/tasks/<task_id>')
@require_report_access(REPORT)
def sales_turnover_forecast_status(task_id):
    record = db.session.get(SalesTurnoverForecastRun, task_id)
    if not record:
        return jsonify(message='Forecast task not found'), 404
    if record.result_json:
        return jsonify(status='completed', result=record.result_json)
    exists = db.session.execute(text("SELECT to_regclass('intelligence_task_results')")).scalar()
    if exists:
        receipt = db.session.execute(text('SELECT result_json FROM intelligence_task_results WHERE task_id = :id'), {'id': task_id}).scalar()
        if receipt:
            return jsonify(receipt)
    try:
        status = redis_client.hgetall(os.getenv('REDIS_RESULT_PREFIX', 'intelligence:task:') + task_id)
        return jsonify(status=status.get('status', 'pending'), error=status.get('error', ''))
    except Exception:
        return jsonify(message='Task status is temporarily unavailable'), 503


@dashboard_bp.route('/api/sync/sales-prediction-data', methods=['POST'])
@require_role(['ADMIN', 'DATA_SYNC_USER'])
def start_sales_prediction_sync():
    body = request.get_json(silent=True) or {}
    auto = body.get('forecast_after_sync', False)
    external = body.get('include_external', False)
    if type(auto) is not bool or type(external) is not bool:
        return jsonify(message='Invalid forecast options'), 400
    try:
        redis_client.rpush('sync_queue', json.dumps({'type': 'sales_prediction_data', 'user_id': get_jwt_identity(),
            'forecast_after_sync': auto, 'include_external': external}))
        return jsonify(status='success', message='Sales Prediction Data Sync queued'), 202
    except Exception:
        return jsonify(message='Unable to queue sales sync'), 503
