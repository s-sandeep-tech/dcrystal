from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from flask import current_app, jsonify, render_template, request
from app.dashboard import dashboard_bp
from app.services import sales_tsk_monthly_analyse as report
from app.utils.decorators import require_report_access

REPORT = '/sales-tsk-monthly-analyse'


def json_numbers(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {key: json_numbers(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_numbers(item) for item in value]
    return value


@dashboard_bp.route(REPORT)
@require_report_access(REPORT)
def sales_tsk_monthly_analyse_page():
    start, end = report.source.defaults()
    return render_template('sales_tsk_monthly_analyse.html', unread_count=0,
                           filter_fields=report.source.FILTERS, groups=report.GROUPS, start=start, end=end)


@dashboard_bp.route('/api/sales-tsk-monthly-analyse/<segment>')
@require_report_access(REPORT)
def sales_tsk_monthly_analyse_segment(segment):
    if segment not in {'options', 'matrix'}:
        return jsonify(message='Unknown report segment.'), 404
    try:
        filters = report.parse_filters(request.args)
        response = jsonify(data=json_numbers(report.load_segment(segment, filters)),
                           fetched_at=datetime.now(ZoneInfo('Asia/Kolkata')).isoformat())
        response.headers['Cache-Control'] = 'no-store'
        return response
    except ValueError as error:
        return jsonify(message=str(error)), 400
    except report.source.SourceDataError as error:
        return jsonify(message=str(error)), 422
    except Exception:
        current_app.logger.exception('Monthly sales analysis failed: %s', segment)
        return jsonify(message='External sales data is temporarily unavailable. Please retry.'), 503
