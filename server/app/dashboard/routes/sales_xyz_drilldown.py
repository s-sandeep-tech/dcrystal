from flask import current_app, jsonify, render_template, request

from app.dashboard import dashboard_bp
from app.services import sales_xyz_drilldown as report
from app.utils.decorators import require_report_access

REPORT = '/sales-xyz-drilldown'


@dashboard_bp.route(REPORT)
@require_report_access(REPORT)
def sales_xyz_drilldown_page():
    start, end = report.defaults()
    return render_template('sales_xyz_drilldown.html', unread_count=0, start=start, end=end,
                           levels=report.HIERARCHIES['default'], hierarchies=report.HIERARCHIES, filter_fields=report.FILTERS,
                           excluded_makes=report.EXCLUDED_MAKES, default_branch_types=report.DEFAULT_BRANCH_TYPES)


@dashboard_bp.route('/api/sales-xyz-drilldown/<segment>')
@require_report_access(REPORT)
def sales_xyz_drilldown_segment(segment):
    if segment not in {'options', 'hierarchy'}:
        return jsonify(message='Unknown report segment.'), 404
    try:
        filters = report.parse_filters(request.args)
        if segment == 'hierarchy':
            parent = report.parse_parent(request.args.get('parent', '[]'), filters['hierarchy'])
        else:
            field = request.args.get('field')
            if field not in report.FILTERS:
                raise ValueError('Choose a valid filter.')
        with report.source_cursor() as cursor:
            data = (report.drilldown(cursor, filters, parent) if segment == 'hierarchy'
                    else report.options(cursor, filters, field))
        response = jsonify(data=data)
        response.headers['Cache-Control'] = 'no-store'
        return response
    except ValueError as error:
        return jsonify(message=str(error)), 400
    except report.SourceDataError as error:
        return jsonify(message=str(error)), 422
    except Exception:
        current_app.logger.exception('Sales XYZ Drilldown request failed: %s', segment)
        return jsonify(message='External sales data is temporarily unavailable. Please retry.'), 503
