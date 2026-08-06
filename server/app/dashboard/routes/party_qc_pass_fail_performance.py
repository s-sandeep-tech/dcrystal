from flask import render_template, request, jsonify, session
from flask_jwt_extended import jwt_required
from app.dashboard import dashboard_bp
from app.models import Notification, PartyQcPassFailSnapshot
from app.extensions import db
from sqlalchemy import func, desc, asc, case
from datetime import datetime
from zoneinfo import ZoneInfo
import logging

logger = logging.getLogger(__name__)

MONTH_LIST = ['April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December', 'January', 'February', 'March']


def split_filter_values(value):
    return [v.strip() for v in (value or '').split(',') if v.strip()]


def apply_multi_filter(query, column, value):
    values = split_filter_values(value)
    if not values:
        return query
    if len(values) == 1:
        return query.filter(column == values[0])
    return query.filter(column.in_(values))


@dashboard_bp.route('/party-qc-pass-fail-performance')
def party_qc_pass_fail_performance():
    try:
        unread_count = Notification.query.filter_by(is_read=False).count()
        sync_time = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%I:%M %p")

        # Filters & Sorting
        search = request.args.get('search', '').strip()
        party = request.args.get('party', '')
        order_type = request.args.get('order_type', '')
        provision_type = request.args.get('provision_type', '')
        qc_gt_zero = request.args.get('qc_gt_zero', '')
        sort_by = request.args.get('sort_by', 'party').strip().lower()
        sort_dir = request.args.get('sort_dir', 'asc').strip().lower()

        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)

        def apply_filters(query):
            if search:
                query = query.filter(PartyQcPassFailSnapshot.party.ilike(f"%{search}%"))
            query = apply_multi_filter(query, PartyQcPassFailSnapshot.party, party)
            query = apply_multi_filter(query, PartyQcPassFailSnapshot.order_type, order_type)
            query = apply_multi_filter(query, PartyQcPassFailSnapshot.provision_type, provision_type)
            if qc_gt_zero == 'true' or qc_gt_zero == '1':
                query = query.filter(PartyQcPassFailSnapshot.qc_failed_pcs > 0)
            return query

        def get_options(column):
            return [
                r[0] for r in db.session.query(column)
                .filter(column.isnot(None), column != '')
                .distinct().order_by(column).all()
                if r[0]
            ]

        filter_options = {
            'parties': get_options(PartyQcPassFailSnapshot.party),
            'order_types': get_options(PartyQcPassFailSnapshot.order_type),
            'provision_types': get_options(PartyQcPassFailSnapshot.provision_type),
        }

        db_months_q = db.session.query(
            PartyQcPassFailSnapshot.month
        ).filter(PartyQcPassFailSnapshot.month.isnot(None), PartyQcPassFailSnapshot.month != '').distinct()
        db_months = [r[0] for r in apply_filters(db_months_q).all()]

        months = [m for m in MONTH_LIST if m in db_months]
        if not months:
            months = [m for m in db_months]
        if not months:
            months = ['April', 'May', 'June', 'July', 'August']

        # Global Aggregate Stats
        agg_cols = [
            func.sum(PartyQcPassFailSnapshot.qc_issue_pcs).label('total_issue_pcs'),
            func.sum(PartyQcPassFailSnapshot.qc_issue_wt).label('total_issue_wt'),
            func.sum(PartyQcPassFailSnapshot.qc_passed_pcs).label('total_passed_pcs'),
            func.sum(PartyQcPassFailSnapshot.qc_passed_wt).label('total_passed_wt'),
            func.sum(PartyQcPassFailSnapshot.qc_failed_pcs).label('total_failed_pcs'),
            func.sum(PartyQcPassFailSnapshot.qc_failed_wt).label('total_failed_wt'),
        ]
        agg_q = db.session.query(*agg_cols)
        agg_q = apply_filters(agg_q)
        aggs = agg_q.first()

        stats = {
            'qc_issue_pcs': f"{int(aggs.total_issue_pcs or 0):,}",
            'qc_issue_wt': f"{float(aggs.total_issue_wt or 0.0):,.3f}",
            'qc_passed_pcs': f"{int(aggs.total_passed_pcs or 0):,}",
            'qc_passed_wt': f"{float(aggs.total_passed_wt or 0.0):,.3f}",
            'qc_failed_pcs': f"{int(aggs.total_failed_pcs or 0):,}",
            'qc_failed_wt': f"{float(aggs.total_failed_wt or 0.0):,.3f}",
        }

        level = 'party'

        # Main query distinct parties paginated with optional month sorting
        if sort_by in [m.lower() for m in months]:
            # Sort by total issue weight for that month
            month_match = next((m for m in months if m.lower() == sort_by), None)
            sort_weight_expr = func.sum(
                func.coalesce(
                    func.nullif(
                        case(
                            (func.lower(PartyQcPassFailSnapshot.month) == sort_by, PartyQcPassFailSnapshot.qc_issue_wt),
                            else_=0
                        ), 0
                    ), 0
                )
            )
            main_q = db.session.query(PartyQcPassFailSnapshot.party, sort_weight_expr.label('sort_wt'))
            main_q = apply_filters(main_q).group_by(PartyQcPassFailSnapshot.party)
            if sort_dir == 'desc':
                main_q = main_q.order_by(desc('sort_wt'), PartyQcPassFailSnapshot.party)
            else:
                main_q = main_q.order_by(asc('sort_wt'), PartyQcPassFailSnapshot.party)
        else:
            main_q = db.session.query(PartyQcPassFailSnapshot.party)
            main_q = apply_filters(main_q).group_by(PartyQcPassFailSnapshot.party)
            if sort_dir == 'desc':
                main_q = main_q.order_by(desc(PartyQcPassFailSnapshot.party))
            else:
                main_q = main_q.order_by(asc(PartyQcPassFailSnapshot.party))

        pagination = main_q.paginate(page=page, per_page=per_page, error_out=False)

        parties_page = [r[0] for r in pagination.items]

        processed_rows = []
        if parties_page:
            pivot_q = db.session.query(
                PartyQcPassFailSnapshot.party,
                PartyQcPassFailSnapshot.month,
                func.sum(PartyQcPassFailSnapshot.qc_issue_pcs).label('issue_pcs'),
                func.sum(PartyQcPassFailSnapshot.qc_issue_wt).label('issue_wt'),
                func.sum(PartyQcPassFailSnapshot.qc_passed_pcs).label('passed_pcs'),
                func.sum(PartyQcPassFailSnapshot.qc_passed_wt).label('passed_wt'),
                func.sum(PartyQcPassFailSnapshot.qc_failed_pcs).label('failed_pcs'),
                func.sum(PartyQcPassFailSnapshot.qc_failed_wt).label('failed_wt'),
            ).filter(PartyQcPassFailSnapshot.party.in_(parties_page))
            pivot_q = apply_filters(pivot_q)
            pivot_records = pivot_q.group_by(PartyQcPassFailSnapshot.party, PartyQcPassFailSnapshot.month).all()

            data_map = {}
            for r in pivot_records:
                p_name = r.party
                m_name = r.month
                if p_name not in data_map:
                    data_map[p_name] = {}
                data_map[p_name][m_name] = {
                    'issue_pcs': int(r.issue_pcs or 0),
                    'issue_wt': float(r.issue_wt or 0.0),
                    'passed_pcs': int(r.passed_pcs or 0),
                    'passed_wt': float(r.passed_wt or 0.0),
                    'failed_pcs': int(r.failed_pcs or 0),
                    'failed_wt': float(r.failed_wt or 0.0),
                }

            for p_name in parties_page:
                p_data = data_map.get(p_name, {})
                processed_rows.append({
                    'party': p_name,
                    'months_data': p_data,
                    'level': level
                })

        return render_template('party_qc_pass_fail_performance.html',
                             unread_count=unread_count,
                             sync_time=sync_time,
                             stats=stats,
                             rows=processed_rows,
                             months=months,
                             pagination=pagination,
                             current_level=level,
                             sort_by=sort_by,
                             sort_dir=sort_dir,
                             filter_options=filter_options)
    except Exception as e:
        logger.error(f"Error in party_qc_pass_fail_performance: {str(e)}")
        return f"Error: {str(e)}", 500


@dashboard_bp.route('/partial/party-qc-pass-fail-performance')
@jwt_required()
def get_party_qc_pass_fail_performance_partial():
    try:
        search = request.args.get('search', '').strip()
        party = request.args.get('party', '')
        order_type = request.args.get('order_type', '')
        provision_type = request.args.get('provision_type', '')
        qc_gt_zero = request.args.get('qc_gt_zero', '')
        sort_by = request.args.get('sort_by', 'party').strip().lower()
        sort_dir = request.args.get('sort_dir', 'asc').strip().lower()

        parent_party = request.args.get('parent_party', '')

        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)
        target_level = request.args.get('target_level', '')
        is_child_rows = request.args.get('is_child_rows', 'false') == 'true'

        def apply_filters(query):
            if search:
                query = query.filter(PartyQcPassFailSnapshot.party.ilike(f"%{search}%"))
            query = apply_multi_filter(query, PartyQcPassFailSnapshot.party, party)
            query = apply_multi_filter(query, PartyQcPassFailSnapshot.order_type, order_type)
            query = apply_multi_filter(query, PartyQcPassFailSnapshot.provision_type, provision_type)
            if qc_gt_zero == 'true' or qc_gt_zero == '1':
                query = query.filter(PartyQcPassFailSnapshot.qc_failed_pcs > 0)
            return query

        db_months_q = db.session.query(
            PartyQcPassFailSnapshot.month
        ).filter(PartyQcPassFailSnapshot.month.isnot(None), PartyQcPassFailSnapshot.month != '').distinct()
        db_months = [r[0] for r in apply_filters(db_months_q).all()]

        months = [m for m in MONTH_LIST if m in db_months]
        if not months:
            months = [m for m in db_months]
        if not months:
            months = ['April', 'May', 'June', 'July', 'August']

        # Global Aggregate Stats
        agg_cols = [
            func.sum(PartyQcPassFailSnapshot.qc_issue_pcs).label('total_issue_pcs'),
            func.sum(PartyQcPassFailSnapshot.qc_issue_wt).label('total_issue_wt'),
            func.sum(PartyQcPassFailSnapshot.qc_passed_pcs).label('total_passed_pcs'),
            func.sum(PartyQcPassFailSnapshot.qc_passed_wt).label('total_passed_wt'),
            func.sum(PartyQcPassFailSnapshot.qc_failed_pcs).label('total_failed_pcs'),
            func.sum(PartyQcPassFailSnapshot.qc_failed_wt).label('total_failed_wt'),
        ]
        agg_q = db.session.query(*agg_cols)
        agg_q = apply_filters(agg_q)
        aggs = agg_q.first()

        stats = {
            'qc_issue_pcs': f"{int(aggs.total_issue_pcs or 0):,}",
            'qc_issue_wt': f"{float(aggs.total_issue_wt or 0.0):,.3f}",
            'qc_passed_pcs': f"{int(aggs.total_passed_pcs or 0):,}",
            'qc_passed_wt': f"{float(aggs.total_passed_wt or 0.0):,.3f}",
            'qc_failed_pcs': f"{int(aggs.total_failed_pcs or 0):,}",
            'qc_failed_wt': f"{float(aggs.total_failed_wt or 0.0):,.3f}",
        }

        level = target_level or 'party'

        if is_child_rows and parent_party:
            metrics = ['QC ISSUE TOTAL', 'QC PASSED TOTAL', 'QC FAILED TOTAL']

            pivot_q = db.session.query(
                PartyQcPassFailSnapshot.month,
                func.sum(PartyQcPassFailSnapshot.qc_issue_pcs).label('issue_pcs'),
                func.sum(PartyQcPassFailSnapshot.qc_issue_wt).label('issue_wt'),
                func.sum(PartyQcPassFailSnapshot.qc_passed_pcs).label('passed_pcs'),
                func.sum(PartyQcPassFailSnapshot.qc_passed_wt).label('passed_wt'),
                func.sum(PartyQcPassFailSnapshot.qc_failed_pcs).label('failed_pcs'),
                func.sum(PartyQcPassFailSnapshot.qc_failed_wt).label('failed_wt'),
            ).filter(PartyQcPassFailSnapshot.party == parent_party)
            pivot_q = apply_filters(pivot_q)
            records = pivot_q.group_by(PartyQcPassFailSnapshot.month).all()

            month_map = {r.month: r for r in records}

            processed_rows = []
            for metric in metrics:
                row_months = {}
                for m in months:
                    rec = month_map.get(m)
                    if rec:
                        if metric == 'QC ISSUE TOTAL':
                            pcs, wt = int(rec.issue_pcs or 0), float(rec.issue_wt or 0.0)
                        elif metric == 'QC PASSED TOTAL':
                            pcs, wt = int(rec.passed_pcs or 0), float(rec.passed_wt or 0.0)
                        else:
                            pcs, wt = int(rec.failed_pcs or 0), float(rec.failed_wt or 0.0)
                    else:
                        pcs, wt = 0, 0.0
                    row_months[m] = {'pcs': pcs, 'wt': wt}

                processed_rows.append({
                    'party': parent_party,
                    'metric_name': metric,
                    'months_data': row_months,
                    'level': 'metric'
                })

            pagination = None
        else:
            if sort_by in [m.lower() for m in months]:
                sort_weight_expr = func.sum(
                    func.coalesce(
                        func.nullif(
                            case(
                                (func.lower(PartyQcPassFailSnapshot.month) == sort_by, PartyQcPassFailSnapshot.qc_issue_wt),
                                else_=0
                            ), 0
                        ), 0
                    )
                )
                main_q = db.session.query(PartyQcPassFailSnapshot.party, sort_weight_expr.label('sort_wt'))
                main_q = apply_filters(main_q).group_by(PartyQcPassFailSnapshot.party)
                if sort_dir == 'desc':
                    main_q = main_q.order_by(desc('sort_wt'), PartyQcPassFailSnapshot.party)
                else:
                    main_q = main_q.order_by(asc('sort_wt'), PartyQcPassFailSnapshot.party)
            else:
                main_q = db.session.query(PartyQcPassFailSnapshot.party)
                main_q = apply_filters(main_q).group_by(PartyQcPassFailSnapshot.party)
                if sort_dir == 'desc':
                    main_q = main_q.order_by(desc(PartyQcPassFailSnapshot.party))
                else:
                    main_q = main_q.order_by(asc(PartyQcPassFailSnapshot.party))

            pagination = main_q.paginate(page=page, per_page=per_page, error_out=False)
            parties_page = [r[0] for r in pagination.items]

            processed_rows = []
            if parties_page:
                pivot_q = db.session.query(
                    PartyQcPassFailSnapshot.party,
                    PartyQcPassFailSnapshot.month,
                    func.sum(PartyQcPassFailSnapshot.qc_issue_pcs).label('issue_pcs'),
                    func.sum(PartyQcPassFailSnapshot.qc_issue_wt).label('issue_wt'),
                    func.sum(PartyQcPassFailSnapshot.qc_passed_pcs).label('passed_pcs'),
                    func.sum(PartyQcPassFailSnapshot.qc_passed_wt).label('passed_wt'),
                    func.sum(PartyQcPassFailSnapshot.qc_failed_pcs).label('failed_pcs'),
                    func.sum(PartyQcPassFailSnapshot.qc_failed_wt).label('failed_wt'),
                ).filter(PartyQcPassFailSnapshot.party.in_(parties_page))
                pivot_q = apply_filters(pivot_q)
                pivot_records = pivot_q.group_by(PartyQcPassFailSnapshot.party, PartyQcPassFailSnapshot.month).all()

                data_map = {}
                for r in pivot_records:
                    p_name = r.party
                    m_name = r.month
                    if p_name not in data_map:
                        data_map[p_name] = {}
                    data_map[p_name][m_name] = {
                        'issue_pcs': int(r.issue_pcs or 0),
                        'issue_wt': float(r.issue_wt or 0.0),
                        'passed_pcs': int(r.passed_pcs or 0),
                        'passed_wt': float(r.passed_wt or 0.0),
                        'failed_pcs': int(r.failed_pcs or 0),
                        'failed_wt': float(r.failed_wt or 0.0),
                    }

                for p_name in parties_page:
                    p_data = data_map.get(p_name, {})
                    processed_rows.append({
                        'party': p_name,
                        'months_data': p_data,
                        'level': 'party'
                    })

        return render_template('partials/_view_party_qc_pass_fail_performance.html',
                             rows=processed_rows,
                             months=months,
                             pagination=pagination,
                             stats=stats,
                             current_level=level,
                             sort_by=sort_by,
                             sort_dir=sort_dir,
                             is_child_rows=is_child_rows)
    except Exception as e:
        logger.error(f"Error in get_party_qc_pass_fail_performance_partial: {str(e)}")
        return f'<div class="p-4 text-red-500">Error: {str(e)}</div>', 500
