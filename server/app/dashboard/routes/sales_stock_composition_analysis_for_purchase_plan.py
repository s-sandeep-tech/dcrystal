from datetime import date, datetime
from zoneinfo import ZoneInfo
import json
import logging
from flask import current_app, jsonify, render_template, request, session
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy import func
from app.dashboard import dashboard_bp
from app.extensions import db
from app.models.sales_stock_composition_analysis import SalesStockCompositionAnalysisSnapshot as Snapshot
from app.models.core import Notification
from app.services.sales_stock_composition_analysis_for_purchase_plan import (
    HIERARCHY,
    FILTERS,
    SORT_KEYS,
    calculate_fy_factor,
    fetch_purchase_plan_composition_data,
    get_purchase_plan_options,
)
from app.utils.decorators import require_report_access, require_role, require_perm

logger = logging.getLogger(__name__)

ROUTE_URL = '/sales-stock-composition-analysis-for-purchase-plan'


def get_selected_date():
    val = request.args.get('date', '').strip()
    return date.fromisoformat(val) if val else None


def get_selected_sort():
    key = request.args.get('sort_by', 'label')
    order = request.args.get('sort_order', 'asc')
    return (key if key in SORT_KEYS else 'label', 'desc' if order == 'desc' else 'asc')


@dashboard_bp.route('/api/sales-stock-composition-analysis-for-purchase-plan/contributors')
@jwt_required()
@require_report_access(ROUTE_URL)
def sales_stock_composition_analysis_for_purchase_plan_contributors():
    try:
        path = json.loads(request.args.get('path', '[]'))
        if not isinstance(path, list) or len(path) > len(HIERARCHY) or not all(isinstance(v, str) for v in path):
            return jsonify(error='Invalid hierarchy path'), 400
        selections = {k: request.args.getlist(k) for k in FILTERS if request.args.getlist(k)}
        return jsonify(fetch_purchase_plan_composition_data(get_selected_date(), selections, path, contributors=True))
    except (ValueError, TypeError):
        return jsonify(error='Invalid chart filters'), 400
    except Exception:
        db.session.rollback()
        logger.exception('Unable to load sales contributors')
        return jsonify(error='Unable to load sales contributors'), 500


@dashboard_bp.route(ROUTE_URL)
@require_report_access(ROUTE_URL)
def sales_stock_composition_analysis_for_purchase_plan_page():
    try:
        unread_count = Notification.query.filter_by(is_read=False).count()
        snapshot_date = db.session.query(func.max(Snapshot.date)).scalar()
        sync_time = snapshot_date.strftime("%d, %I:%M %p") if snapshot_date else datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%I:%M %p")
        permissions = session.get('permissions', [])

        factor, fy_days, elapsed_days, fy_label = calculate_fy_factor(snapshot_date or date.today())

        return render_template(
            'sales_stock_composition_analysis_for_purchase_plan.html',
            unread_count=unread_count,
            sync_time=sync_time,
            permissions=permissions,
            factor=factor,
            fy_label=fy_label,
            stats={},
            rows=[],
            total=None
        )
    except Exception as e:
        logger.exception("Error rendering sales_stock_composition_analysis_for_purchase_plan page: %s", str(e))
        db.session.rollback()
        return render_template(
            'sales_stock_composition_analysis_for_purchase_plan.html',
            unread_count=0,
            sync_time="LIVE",
            permissions=session.get('permissions', []),
            factor=1.0,
            fy_label="FY",
            stats={},
            rows=[],
            total=None
        )


@dashboard_bp.route('/partial/sales-stock-composition-analysis-for-purchase-plan')
@jwt_required()
@require_report_access(ROUTE_URL)
def get_sales_stock_composition_analysis_for_purchase_plan_partial():
    try:
        selections = {}
        for k in FILTERS:
            vals = request.args.getlist(k)
            if not vals and request.args.get(k):
                vals = [v.strip() for v in request.args.get(k).split(',') if v.strip()]
            if vals:
                selections[k] = vals

        path_str = request.args.get('path', '[]')
        path = json.loads(path_str) if path_str else []

        sort_by, sort_order = get_selected_sort()
        data = fetch_purchase_plan_composition_data(get_selected_date(), selections, path=path,
                                                   sort_by=sort_by, sort_order=sort_order)

        return render_template(
            'partials/_view_sales_stock_composition_analysis_for_purchase_plan.html',
            rows=data.get('rows', []),
            total=data.get('total'),
            stats=data.get('stats', {}),
            level=data.get('level', 'section'),
            can_expand=data.get('can_expand', True),
            factor=data.get('factor', 1.0),
            fy_label=data.get('fy_label', 'FY'),
            path=path,
            search=request.args.get('search', ''),
            sort_by=sort_by,
            sort_order=sort_order,
        )
    except Exception as e:
        logger.exception("Error in sales_stock_composition_analysis_for_purchase_plan partial: %s", str(e))
        db.session.rollback()
        return render_template(
            'partials/_view_sales_stock_composition_analysis_for_purchase_plan.html',
            error_message=str(e),
            rows=[],
            total=None,
            stats={}
        )


@dashboard_bp.route('/partial/sales-stock-composition-analysis-for-purchase-plan/branch')
@jwt_required()
@require_report_access(ROUTE_URL)
def get_sales_stock_composition_analysis_for_purchase_plan_branch():
    try:
        path_str = request.args.get('path', '[]')
        path = json.loads(path_str) if path_str else []

        selections = {}
        for k in FILTERS:
            vals = request.args.getlist(k)
            if not vals and request.args.get(k):
                vals = [v.strip() for v in request.args.get(k).split(',') if v.strip()]
            if vals:
                selections[k] = vals

        sort_by, sort_order = get_selected_sort()
        data = fetch_purchase_plan_composition_data(get_selected_date(), selections, path=path,
                                                   sort_by=sort_by, sort_order=sort_order)

        return render_template(
            'partials/_view_sales_stock_composition_analysis_for_purchase_plan_branch.html',
            rows=data.get('rows', []),
            parent_path=path,
            can_expand=data.get('can_expand', False),
            level=data.get('level')
        )
    except Exception as e:
        logger.exception("Error in sales_stock_composition_analysis_for_purchase_plan branch: %s", str(e))
        db.session.rollback()
        return f'<tr><td colspan="4" class="p-2 text-center text-red-500 text-xs">Error: {str(e)}</td></tr>', 200


@dashboard_bp.route('/api/sales-stock-composition-analysis-for-purchase-plan/options')
@jwt_required()
@require_report_access(ROUTE_URL)
def sales_stock_composition_analysis_for_purchase_plan_options():
    try:
        return jsonify(get_purchase_plan_options())
    except Exception as e:
        logger.exception("Error fetching sales_stock_composition_analysis_for_purchase_plan options: %s", str(e))
        db.session.rollback()
        return jsonify({'dates': [], 'locations': [], 'sections': [], 'classifications': []})


@dashboard_bp.route('/api/sync/sales-stock-composition-analysis-for-purchase-plan', methods=['POST'])
@require_role(['ADMIN', 'DATA_SYNC_USER'])
def trigger_sync_sales_stock_composition_analysis_for_purchase_plan():
    from app.utils.sync_manager import sync_sales_stock_composition_analysis_data
    from app.models.auth import User
    user = db.session.get(User, int(get_jwt_identity()))
    return jsonify(sync_sales_stock_composition_analysis_data(user.user_id))


@dashboard_bp.route('/api/sales-stock-composition-analysis-for-purchase-plan/export', methods=['POST'])
@jwt_required()
@require_report_access(ROUTE_URL)
@require_perm('report.export')
def export_sales_stock_composition_analysis_for_purchase_plan():
    try:
        from app.utils.export_service import create_export_job
        data = request.get_json() or {}
        filters = data.get('filters', {})
        if filters.get('date'):
            date.fromisoformat(filters['date'])
        socket_id = data.get('socket_id')
        user_id = get_jwt_identity()

        task_payload = {
            'report_type': 'sales_stock_composition_analysis_for_purchase_plan',
            'filters': filters,
            'socket_id': socket_id,
            'user_id': user_id
        }

        job_result = create_export_job(task_payload)
        return jsonify(job_result), 200
    except Exception as e:
        logger.exception("Failed to queue sales_stock_composition_analysis_for_purchase_plan export: %s", str(e))
        return jsonify({"status": "error", "message": str(e)}), 500
