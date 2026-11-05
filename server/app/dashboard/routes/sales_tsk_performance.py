import csv
import io
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from flask import Response, current_app, jsonify, render_template, request
from app.dashboard import dashboard_bp
from app.services import sales_tsk_performance as report
from app.utils.decorators import require_report_access

REPORT = '/sales-tsk-performance'
SEGMENTS = {'options', 'kpis', 'trend', 'sections', 'branches', 'ledger', 'export'}


def json_numbers(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {key: json_numbers(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_numbers(item) for item in value]
    if isinstance(value, datetime):
        return value.isoformat()
    return value


@dashboard_bp.route(REPORT)
@require_report_access(REPORT)
def sales_tsk_performance_page():
    start, end = report.defaults()
    return render_template('sales_tsk_performance.html', unread_count=0,
                           filter_fields=report.FILTERS, start=start, end=end)


@dashboard_bp.route('/api/sales-tsk-performance/<segment>')
@require_report_access(REPORT)
def sales_tsk_performance_segment(segment):
    if segment not in SEGMENTS:
        return jsonify(message='Unknown report segment.'), 404
    try:
        filters = report.parse_filters(request.args)
        data = report.load_segment(segment, filters)
        if segment == 'export':
            output = io.StringIO()
            writer = csv.writer(output)
            keys = ['month', *report.METRICS, 'prior_turnover', 'yoy', 'leading_branch']
            writer.writerow(['Month', 'Invoice turnover', 'Returns (signed)', 'Net turnover',
                             'Net weight (source total)', 'TSK (source total)', 'Prior-year turnover', 'YoY %', 'Leading branch'])
            for row in data:
                values = [row.get(key) for key in keys]
                # Protect spreadsheet consumers from formula-like source labels.
                values = ["'" + v if isinstance(v, str) and v.lstrip().startswith(('=', '+', '-', '@')) else v for v in values]
                writer.writerow(values)
            return Response('\ufeff' + output.getvalue(), mimetype='text/csv', headers={
                'Content-Disposition': 'attachment; filename=sales-tsk-monthly-ledger.csv', 'Cache-Control': 'no-store'})
        response = jsonify(data=json_numbers(data), fetched_at=datetime.now(ZoneInfo('Asia/Kolkata')).isoformat())
        response.headers['Cache-Control'] = 'no-store'
        return response
    except ValueError as error:
        return jsonify(message=str(error)), 400
    except report.SourceDataError as error:
        return jsonify(message=str(error)), 422
    except Exception:
        current_app.logger.exception('Live sales TSK segment failed: %s', segment)
        return jsonify(message='External sales data is temporarily unavailable. Retry this segment.'), 503
