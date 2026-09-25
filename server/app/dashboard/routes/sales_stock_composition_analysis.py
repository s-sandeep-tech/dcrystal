from datetime import date, datetime
from zoneinfo import ZoneInfo
import json
import logging
from flask import current_app, jsonify, render_template, request, session
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy import func
from app.dashboard import dashboard_bp
from app.extensions import db
from app.models.sales_stock_composition_analysis import SalesStockCompositionAnalysisSnapshot as S
from app.models.core import Notification
from app.services.sales_stock_composition_analysis import (
    HIERARCHY,
    FILTERS,
    composition_analysis_data,
    dimension,
    calculate_fy_factor,
)
from app.utils.decorators import require_report_access, require_role, require_perm

logger = logging.getLogger(__name__)

ROUTE_URL = '/sales-stock-composition-analysis'
ALIAS_URL = '/sales-stock-composition'


@dashboard_bp.route(ROUTE_URL)
@dashboard_bp.route(ALIAS_URL)
@require_report_access(ROUTE_URL)
def sales_stock_composition_analysis_page():
    try:
        unread_count = Notification.query.filter_by(is_read=False).count()
        snapshot_date = db.session.query(func.max(S.date)).scalar()
        sync_time = snapshot_date.strftime("%d, %I:%M %p") if snapshot_date else datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%I:%M %p")
        permissions = session.get('permissions', [])
        
        factor, fy_days, elapsed_days, fy_label = calculate_fy_factor(snapshot_date or date.today())

        return render_template(
            'sales_stock_composition_analysis.html',
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
        logger.exception("Error rendering sales_stock_composition_analysis page: %s", str(e))
        db.session.rollback()
        return render_template(
            'sales_stock_composition_analysis.html',
            unread_count=0,
            sync_time="LIVE",
            permissions=session.get('permissions', []),
            factor=1.0,
            fy_label="FY",
            stats={},
            rows=[],
            total=None
        )


@dashboard_bp.route('/partial/sales-stock-composition-analysis')
@dashboard_bp.route('/partial/sales-stock-composition')
@jwt_required()
@require_report_access(ROUTE_URL)
def get_sales_stock_composition_analysis_partial():
    try:
        date_str = request.args.get('date', '').strip()
        if date_str:
            cutoff = date.fromisoformat(date_str)
        else:
            cutoff = db.session.query(func.max(S.date)).scalar()

        selections = {}
        for k in FILTERS:
            vals = request.args.getlist(k)
            if not vals and request.args.get(k):
                vals = [v.strip() for v in request.args.get(k).split(',') if v.strip()]
            if vals:
                selections[k] = vals

        path_str = request.args.get('path', '[]')
        path = json.loads(path_str) if path_str else []

        data = composition_analysis_data(cutoff, selections, path=path)

        return render_template(
            'partials/_view_sales_stock_composition_analysis.html',
            rows=data.get('rows', []),
            total=data.get('total'),
            stats=data.get('stats', {}),
            level=data.get('level', 'section'),
            can_expand=data.get('can_expand', True),
            factor=data.get('factor', 1.0),
            fy_label=data.get('fy_label', 'FY'),
            path=path,
            cutoff=cutoff,
            search=request.args.get('search', '')
        )
    except Exception as e:
        logger.exception("Error in sales_stock_composition_analysis partial: %s", str(e))
        db.session.rollback()
        return render_template(
            'partials/_view_sales_stock_composition_analysis.html',
            error_message=str(e),
            rows=[],
            total=None,
            stats={}
        )


@dashboard_bp.route('/partial/sales-stock-composition-analysis/branch')
@dashboard_bp.route('/partial/sales-stock-composition/branch')
@jwt_required()
@require_report_access(ROUTE_URL)
def get_sales_stock_composition_analysis_branch():
    try:
        date_str = request.args.get('date', '').strip()
        if date_str:
            cutoff = date.fromisoformat(date_str)
        else:
            cutoff = db.session.query(func.max(S.date)).scalar()

        path_str = request.args.get('path', '[]')
        path = json.loads(path_str) if path_str else []

        selections = {}
        for k in FILTERS:
            vals = request.args.getlist(k)
            if not vals and request.args.get(k):
                vals = [v.strip() for v in request.args.get(k).split(',') if v.strip()]
            if vals:
                selections[k] = vals

        data = composition_analysis_data(cutoff, selections, path=path)

        return render_template(
            'partials/_view_sales_stock_composition_analysis_branch.html',
            rows=data.get('rows', []),
            parent_path=path,
            can_expand=data.get('can_expand', False),
            level=data.get('level')
        )
    except Exception as e:
        logger.exception("Error in sales_stock_composition_analysis branch: %s", str(e))
        db.session.rollback()
        return f'<tr><td colspan="6" class="p-2 text-center text-red-500 text-xs">Error: {str(e)}</td></tr>', 200


@dashboard_bp.route('/api/sales-stock-composition-analysis/options')
@dashboard_bp.route('/api/sales-stock-composition/options')
@jwt_required()
@require_report_access(ROUTE_URL)
def sales_stock_composition_analysis_options():
    try:
        dates = [r[0].isoformat() for r in db.session.query(S.date).filter(S.date.isnot(None)).distinct().order_by(S.date.desc())]
        
        locations = [
            {'value': str(r[0]), 'label': r[1] or str(r[0])}
            for r in db.session.query(S.branch_id, func.max(S.location_name))
            .filter(S.branch_id.isnot(None))
            .group_by(S.branch_id)
            .order_by(func.max(S.location_name))
        ]
        
        sections = [r[0] for r in db.session.query(dimension('section')).distinct().order_by(dimension('section')) if r[0]]
        classifications = [r[0] for r in db.session.query(dimension('classification')).distinct().order_by(dimension('classification')) if r[0]]
        
        return jsonify({
            'dates': dates,
            'locations': locations,
            'sections': sections,
            'classifications': classifications
        })
    except Exception as e:
        logger.exception("Error fetching sales_stock_composition_analysis options: %s", str(e))
        db.session.rollback()
        return jsonify({'dates': [], 'locations': [], 'sections': [], 'classifications': []})


@dashboard_bp.route('/api/sync/sales-stock-composition-analysis', methods=['POST'])
@dashboard_bp.route('/api/sales-stock-composition/sync', methods=['POST'])
@require_role(['ADMIN', 'DATA_SYNC_USER'])
def trigger_sync_sales_stock_composition_analysis():
    from app.utils.sync_manager import sync_sales_stock_composition_analysis_data
    from app.models.auth import User
    user = db.session.get(User, int(get_jwt_identity()))
    return jsonify(sync_sales_stock_composition_analysis_data(user.user_id))


@dashboard_bp.route('/api/sales-stock-composition-analysis/export', methods=['POST'])
@jwt_required()
@require_report_access(ROUTE_URL)
@require_perm('report.export')
def export_sales_stock_composition_analysis():
    try:
        from app.utils.export_service import create_export_job
        data = request.get_json() or {}
        filters = data.get('filters', {})
        socket_id = data.get('socket_id')
        user_id = get_jwt_identity()

        task_payload = {
            'report_type': 'sales_stock_composition_analysis',
            'filters': filters,
            'socket_id': socket_id,
            'user_id': user_id
        }

        job_result = create_export_job(task_payload)
        return jsonify(job_result), 200
    except Exception as e:
        logger.exception("Failed to queue sales_stock_composition_analysis export: %s", str(e))
        return jsonify({"status": "error", "message": str(e)}), 500
