from hashlib import sha256

from flask import current_app, jsonify, render_template, request
from redis import Redis
from redis.exceptions import RedisError
from flask_jwt_extended import get_jwt_identity

from app.dashboard import dashboard_bp
from app.extensions import REDIS_HOST, REDIS_PORT, db
from app.models.auth import User
from app.services import sales_xyz_drilldown as report
from app.utils.decorators import require_report_access

REPORT = '/sales-xyz-drilldown'
CACHE_TTL_SECONDS = 8 * 60 * 60
redis_client = Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True,
                     socket_connect_timeout=0.5, socket_timeout=0.5)


def current_owner_visibility():
    actor = db.session.get(User, int(get_jwt_identity()))
    if actor is None or not actor.is_active:
        raise PermissionError('Session expired. Please sign in again.')
    return report.owner_visibility([role.name for role in actor.roles], actor.user_id)


@dashboard_bp.route(REPORT)
@require_report_access(REPORT)
def sales_xyz_drilldown_page():
    start, end = report.defaults()
    return render_template('sales_xyz_drilldown.html', unread_count=0, start=start, end=end,
                           levels=report.HIERARCHIES['default'], hierarchies=report.HIERARCHIES, filter_fields=report.FILTERS,
                           excluded_makes=report.EXCLUDED_MAKES, excluded_sections=report.EXCLUDED_SECTIONS,
                           default_branch_types=report.DEFAULT_BRANCH_TYPES)


@dashboard_bp.route('/api/sales-xyz-drilldown/<segment>')
@require_report_access(REPORT)
def sales_xyz_drilldown_segment(segment):
    if segment not in {'options', 'hierarchy'}:
        return jsonify(message='Unknown report segment.'), 404
    try:
        filters = report.parse_filters(request.args)
        filters['owner_visibility'] = current_owner_visibility()
        if segment == 'hierarchy':
            parent = report.parse_parent(request.args.get('parent', '[]'), filters['hierarchy'])
            cache_params = (filters, parent)
        else:
            field = request.args.get('field')
            if field not in report.FILTERS:
                raise ValueError('Choose a valid filter.')
            cache_params = (field, filters['start'], filters['end'], filters['exclusions'], filters['owner_visibility'])
        digest = sha256(current_app.json.dumps(cache_params, sort_keys=True).encode()).hexdigest()
        key = f'sales-xyz-drilldown:v2:{segment}:{digest}'
        refresh = request.args.get('refresh') == '1'
        cached = None
        if not refresh:
            try:
                cached = redis_client.get(key)
            except RedisError:
                current_app.logger.debug('ABC Analysis Redis read failed', exc_info=True)
                key = None
        if cached is not None:
            response = current_app.response_class(cached, mimetype='application/json')
        else:
            with report.source_cursor() as cursor:
                data = (report.drilldown(cursor, filters, parent) if segment == 'hierarchy'
                        else report.options(cursor, filters, field))
            response = jsonify(data=data)
            if key is not None:
                try:
                    # A cache miss that began before Refresh must not overwrite its result.
                    redis_client.set(key, response.get_data(as_text=True), ex=CACHE_TTL_SECONDS, nx=not refresh)
                except RedisError:
                    current_app.logger.debug('ABC Analysis Redis write failed', exc_info=True)
        response.headers['Cache-Control'] = 'no-store'
        return response
    except PermissionError as error:
        return jsonify(message=str(error)), 401
    except ValueError as error:
        return jsonify(message=str(error)), 400
    except report.SourceDataError as error:
        return jsonify(message=str(error)), 422
    except Exception:
        current_app.logger.exception('Sales XYZ Drilldown request failed: %s', segment)
        return jsonify(message='External sales data is temporarily unavailable. Please retry.'), 503
