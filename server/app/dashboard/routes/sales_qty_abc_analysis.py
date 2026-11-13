from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from flask import current_app, jsonify, render_template, request
from app.dashboard import dashboard_bp
from app.services import sales_qty_abc_analysis as report
from app.utils.decorators import require_report_access

REPORT = '/sales-qty-abc-analysis'


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
def sales_qty_abc_analysis_page():
    start, end = report.defaults()
    return render_template('sales_qty_abc_analysis.html', unread_count=0,
                           filter_fields=report.FILTERS, levels=report.LEVELS, abc_bases=report.ABC_BASES,
                           start=start, end=end)


@dashboard_bp.route('/api/sales-qty-abc-analysis/<segment>')
@require_report_access(REPORT)
def sales_qty_abc_analysis_segment(segment):
    if segment not in {'options', 'hierarchy'}:
        return jsonify(message='Unknown report segment.'), 404
    try:
        data = report.load_segment(segment, report.parse_filters(request.args))
        response = jsonify(data=json_numbers(data), fetched_at=datetime.now(ZoneInfo('Asia/Kolkata')).isoformat())
        response.headers['Cache-Control'] = 'no-store'
        return response
    except ValueError as error:
        return jsonify(message=str(error)), 400
    except report.SourceDataError as error:
        return jsonify(message=str(error)), 422
    except Exception:
        current_app.logger.exception('Sales quantity ABC analysis failed: %s', segment)
        return jsonify(message='External sales data is temporarily unavailable. Please retry.'), 503
