from flask import render_template, request, jsonify, session
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.dashboard import dashboard_bp
from app.models import Notification, User, LocationWiseOldGoldSettlementTransferSnapshot
from app.extensions import db
from sqlalchemy import func, case
from datetime import datetime
from zoneinfo import ZoneInfo
import logging

logger = logging.getLogger(__name__)


def split_filter_values(value):
    return [item.strip() for item in (value or '').split(',') if item.strip()]


def ensure_table_exists():
    try:
        LocationWiseOldGoldSettlementTransferSnapshot.__table__.create(db.engine, checkfirst=True)
    except Exception as e:
        logger.debug(f"ensure_table_exists notice: {e}")


def build_filters(query):
    search = request.args.get('search', '').strip()
    offices = split_filter_values(request.args.get('office'))
    locations = split_filter_values(request.args.get('location'))
    divisions = split_filter_values(request.args.get('division'))
    group_name = request.args.get('group', '').strip()
    purities = split_filter_values(request.args.get('purity'))
    from_date = request.args.get('from_date', '').strip()
    to_date = request.args.get('to_date', '').strip()
    enable_date_filter = request.args.get('enable_date_filter', 'false') == 'true'

    if search:
        query = query.filter(
            (LocationWiseOldGoldSettlementTransferSnapshot.office.ilike(f"%{search}%")) |
            (LocationWiseOldGoldSettlementTransferSnapshot.locationname.ilike(f"%{search}%")) |
            (LocationWiseOldGoldSettlementTransferSnapshot.division.ilike(f"%{search}%")) |
            (LocationWiseOldGoldSettlementTransferSnapshot.groupname.ilike(f"%{search}%"))
        )
    if offices:
        query = query.filter(LocationWiseOldGoldSettlementTransferSnapshot.office.in_(offices))
    if locations:
        query = query.filter(LocationWiseOldGoldSettlementTransferSnapshot.locationname.in_(locations))
    if divisions:
        query = query.filter(LocationWiseOldGoldSettlementTransferSnapshot.division.in_(divisions))
    if group_name:
        query = query.filter(LocationWiseOldGoldSettlementTransferSnapshot.groupname == group_name)
    if purities:
        query = query.filter(LocationWiseOldGoldSettlementTransferSnapshot.purity.in_(purities))

    if enable_date_filter and from_date and to_date:
        try:
            fd = datetime.strptime(from_date, '%Y-%m-%d').date()
            td = datetime.strptime(to_date, '%Y-%m-%d').date()
            query = query.filter(func.date(LocationWiseOldGoldSettlementTransferSnapshot.transdate).between(fd, td))
        except ValueError:
            pass

    return query


def get_aggregation_columns():
    trans_date = func.cast(LocationWiseOldGoldSettlementTransferSnapshot.transdate, db.Date)
    curr_date = func.current_date()

    cond_2_5 = (LocationWiseOldGoldSettlementTransferSnapshot.transdate.isnot(None)) & (trans_date.between(curr_date - 5, curr_date - 2))
    cond_6_10 = (LocationWiseOldGoldSettlementTransferSnapshot.transdate.isnot(None)) & (trans_date.between(curr_date - 10, curr_date - 6))
    cond_11_15 = (LocationWiseOldGoldSettlementTransferSnapshot.transdate.isnot(None)) & (trans_date.between(curr_date - 15, curr_date - 11))
    cond_gt_15 = (LocationWiseOldGoldSettlementTransferSnapshot.transdate.isnot(None)) & (trans_date < curr_date - 15)

    return [
        # Overall Totals
        func.coalesce(func.sum(LocationWiseOldGoldSettlementTransferSnapshot.grwt), 0).label('tot_grwt'),
        func.coalesce(func.sum(LocationWiseOldGoldSettlementTransferSnapshot.netwt), 0).label('tot_netwt'),
        func.coalesce(func.sum(LocationWiseOldGoldSettlementTransferSnapshot.stwt), 0).label('tot_stwt'),

        # 2-5 days settlement
        func.coalesce(func.sum(case((cond_2_5, LocationWiseOldGoldSettlementTransferSnapshot.grwt), else_=0)), 0).label('grwt_2_5'),
        func.coalesce(func.sum(case((cond_2_5, LocationWiseOldGoldSettlementTransferSnapshot.netwt), else_=0)), 0).label('netwt_2_5'),
        func.coalesce(func.sum(case((cond_2_5, LocationWiseOldGoldSettlementTransferSnapshot.stwt), else_=0)), 0).label('stwt_2_5'),

        # 2-5 days transfer
        func.coalesce(func.sum(case((cond_2_5, LocationWiseOldGoldSettlementTransferSnapshot.transfer_grwt), else_=0)), 0).label('transfer_grwt_2_5'),
        func.coalesce(func.sum(case((cond_2_5, LocationWiseOldGoldSettlementTransferSnapshot.transfer_netwt), else_=0)), 0).label('transfer_netwt_2_5'),
        func.coalesce(func.sum(case((cond_2_5, LocationWiseOldGoldSettlementTransferSnapshot.transfer_stwt), else_=0)), 0).label('transfer_stwt_2_5'),

        # 6-10 days settlement
        func.coalesce(func.sum(case((cond_6_10, LocationWiseOldGoldSettlementTransferSnapshot.grwt), else_=0)), 0).label('grwt_6_10'),
        func.coalesce(func.sum(case((cond_6_10, LocationWiseOldGoldSettlementTransferSnapshot.netwt), else_=0)), 0).label('netwt_6_10'),
        func.coalesce(func.sum(case((cond_6_10, LocationWiseOldGoldSettlementTransferSnapshot.stwt), else_=0)), 0).label('stwt_6_10'),

        # 6-10 days transfer
        func.coalesce(func.sum(case((cond_6_10, LocationWiseOldGoldSettlementTransferSnapshot.transfer_grwt), else_=0)), 0).label('transfer_grwt_6_10'),
        func.coalesce(func.sum(case((cond_6_10, LocationWiseOldGoldSettlementTransferSnapshot.transfer_netwt), else_=0)), 0).label('transfer_netwt_6_10'),
        func.coalesce(func.sum(case((cond_6_10, LocationWiseOldGoldSettlementTransferSnapshot.transfer_stwt), else_=0)), 0).label('transfer_stwt_6_10'),

        # 11-15 days settlement
        func.coalesce(func.sum(case((cond_11_15, LocationWiseOldGoldSettlementTransferSnapshot.grwt), else_=0)), 0).label('grwt_11_15'),
        func.coalesce(func.sum(case((cond_11_15, LocationWiseOldGoldSettlementTransferSnapshot.netwt), else_=0)), 0).label('netwt_11_15'),
        func.coalesce(func.sum(case((cond_11_15, LocationWiseOldGoldSettlementTransferSnapshot.stwt), else_=0)), 0).label('stwt_11_15'),

        # 11-15 days transfer
        func.coalesce(func.sum(case((cond_11_15, LocationWiseOldGoldSettlementTransferSnapshot.transfer_grwt), else_=0)), 0).label('transfer_grwt_11_15'),
        func.coalesce(func.sum(case((cond_11_15, LocationWiseOldGoldSettlementTransferSnapshot.transfer_netwt), else_=0)), 0).label('transfer_netwt_11_15'),
        func.coalesce(func.sum(case((cond_11_15, LocationWiseOldGoldSettlementTransferSnapshot.transfer_stwt), else_=0)), 0).label('transfer_stwt_11_15'),

        # >15 days settlement
        func.coalesce(func.sum(case((cond_gt_15, LocationWiseOldGoldSettlementTransferSnapshot.grwt), else_=0)), 0).label('grwt_gt_15'),
        func.coalesce(func.sum(case((cond_gt_15, LocationWiseOldGoldSettlementTransferSnapshot.netwt), else_=0)), 0).label('netwt_gt_15'),
        func.coalesce(func.sum(case((cond_gt_15, LocationWiseOldGoldSettlementTransferSnapshot.stwt), else_=0)), 0).label('stwt_gt_15'),

        # >15 days transfer
        func.coalesce(func.sum(case((cond_gt_15, LocationWiseOldGoldSettlementTransferSnapshot.transfer_grwt), else_=0)), 0).label('transfer_grwt_gt_15'),
        func.coalesce(func.sum(case((cond_gt_15, LocationWiseOldGoldSettlementTransferSnapshot.transfer_netwt), else_=0)), 0).label('transfer_netwt_gt_15'),
        func.coalesce(func.sum(case((cond_gt_15, LocationWiseOldGoldSettlementTransferSnapshot.transfer_stwt), else_=0)), 0).label('transfer_stwt_gt_15'),

        # Transfer Totals
        func.coalesce(func.sum(LocationWiseOldGoldSettlementTransferSnapshot.transfer_grwt), 0).label('tot_transfer_grwt'),
        func.coalesce(func.sum(LocationWiseOldGoldSettlementTransferSnapshot.transfer_netwt), 0).label('tot_transfer_netwt'),
        func.coalesce(func.sum(LocationWiseOldGoldSettlementTransferSnapshot.transfer_stwt), 0).label('tot_transfer_stwt'),
    ]


def compute_global_stats(base_query):
    agg_cols = get_aggregation_columns()
    stat_row = base_query.with_entities(*agg_cols).first()

    tot_grwt = float(stat_row.tot_grwt if stat_row else 0.0)
    tot_netwt = float(stat_row.tot_netwt if stat_row else 0.0)
    tot_stwt = float(stat_row.tot_stwt if stat_row else 0.0)

    def calc_perc(val):
        if tot_grwt <= 0:
            return 0.0
        return min(100.0, round((float(val or 0.0) / tot_grwt) * 100.0, 1))

    grwt_2_5 = float(stat_row.grwt_2_5 if stat_row else 0.0)
    netwt_2_5 = float(stat_row.netwt_2_5 if stat_row else 0.0)
    stwt_2_5 = float(stat_row.stwt_2_5 if stat_row else 0.0)

    trans_grwt_2_5 = float(stat_row.transfer_grwt_2_5 if stat_row else 0.0)
    trans_netwt_2_5 = float(stat_row.transfer_netwt_2_5 if stat_row else 0.0)
    trans_stwt_2_5 = float(stat_row.transfer_stwt_2_5 if stat_row else 0.0)

    grwt_6_10 = float(stat_row.grwt_6_10 if stat_row else 0.0)
    netwt_6_10 = float(stat_row.netwt_6_10 if stat_row else 0.0)
    stwt_6_10 = float(stat_row.stwt_6_10 if stat_row else 0.0)

    trans_grwt_6_10 = float(stat_row.transfer_grwt_6_10 if stat_row else 0.0)
    trans_netwt_6_10 = float(stat_row.transfer_netwt_6_10 if stat_row else 0.0)
    trans_stwt_6_10 = float(stat_row.transfer_stwt_6_10 if stat_row else 0.0)

    grwt_11_15 = float(stat_row.grwt_11_15 if stat_row else 0.0)
    netwt_11_15 = float(stat_row.netwt_11_15 if stat_row else 0.0)
    stwt_11_15 = float(stat_row.stwt_11_15 if stat_row else 0.0)

    trans_grwt_11_15 = float(stat_row.transfer_grwt_11_15 if stat_row else 0.0)
    trans_netwt_11_15 = float(stat_row.transfer_netwt_11_15 if stat_row else 0.0)
    trans_stwt_11_15 = float(stat_row.transfer_stwt_11_15 if stat_row else 0.0)

    grwt_gt_15 = float(stat_row.grwt_gt_15 if stat_row else 0.0)
    netwt_gt_15 = float(stat_row.netwt_gt_15 if stat_row else 0.0)
    stwt_gt_15 = float(stat_row.stwt_gt_15 if stat_row else 0.0)

    trans_grwt_gt_15 = float(stat_row.transfer_grwt_gt_15 if stat_row else 0.0)
    trans_netwt_gt_15 = float(stat_row.transfer_netwt_gt_15 if stat_row else 0.0)
    trans_stwt_gt_15 = float(stat_row.transfer_stwt_gt_15 if stat_row else 0.0)

    tot_trans_grwt = float(stat_row.tot_transfer_grwt if stat_row else 0.0)
    tot_trans_netwt = float(stat_row.tot_transfer_netwt if stat_row else 0.0)
    tot_trans_stwt = float(stat_row.tot_transfer_stwt if stat_row else 0.0)

    return {
        'total_grwt': f"{tot_grwt:,.3f}",
        'total_netwt': f"{tot_netwt:,.3f}",
        'total_stwt': f"{tot_stwt:,.3f}",

        'grwt_2_5': f"{grwt_2_5:,.3f}",
        'netwt_2_5': f"{netwt_2_5:,.3f}",
        'stwt_2_5': f"{stwt_2_5:,.3f}",
        'perc_2_5': calc_perc(grwt_2_5),

        'transfer_grwt_2_5': f"{trans_grwt_2_5:,.3f}",
        'transfer_netwt_2_5': f"{trans_netwt_2_5:,.3f}",
        'transfer_stwt_2_5': f"{trans_stwt_2_5:,.3f}",

        'grwt_6_10': f"{grwt_6_10:,.3f}",
        'netwt_6_10': f"{netwt_6_10:,.3f}",
        'stwt_6_10': f"{stwt_6_10:,.3f}",
        'perc_6_10': calc_perc(grwt_6_10),

        'transfer_grwt_6_10': f"{trans_grwt_6_10:,.3f}",
        'transfer_netwt_6_10': f"{trans_netwt_6_10:,.3f}",
        'transfer_stwt_6_10': f"{trans_stwt_6_10:,.3f}",

        'grwt_11_15': f"{grwt_11_15:,.3f}",
        'netwt_11_15': f"{netwt_11_15:,.3f}",
        'stwt_11_15': f"{stwt_11_15:,.3f}",
        'perc_11_15': calc_perc(grwt_11_15),

        'transfer_grwt_11_15': f"{trans_grwt_11_15:,.3f}",
        'transfer_netwt_11_15': f"{trans_netwt_11_15:,.3f}",
        'transfer_stwt_11_15': f"{trans_stwt_11_15:,.3f}",

        'grwt_gt_15': f"{grwt_gt_15:,.3f}",
        'netwt_gt_15': f"{netwt_gt_15:,.3f}",
        'stwt_gt_15': f"{stwt_gt_15:,.3f}",
        'perc_gt_15': calc_perc(grwt_gt_15),

        'transfer_grwt_gt_15': f"{trans_grwt_gt_15:,.3f}",
        'transfer_netwt_gt_15': f"{trans_netwt_gt_15:,.3f}",
        'transfer_stwt_gt_15': f"{trans_stwt_gt_15:,.3f}",

        'transfer_grwt': f"{tot_trans_grwt:,.3f}",
        'transfer_netwt': f"{tot_trans_netwt:,.3f}",
        'transfer_stwt': f"{tot_trans_stwt:,.3f}",
        'transfer_perc': calc_perc(tot_trans_grwt),
    }


def fetch_filter_options():
    def get_distinct(column):
        return [
            r[0] for r in db.session.query(column).distinct().order_by(column).all()
            if r[0] and str(r[0]).strip()
        ]

    return {
        'offices': get_distinct(LocationWiseOldGoldSettlementTransferSnapshot.office),
        'locations': get_distinct(LocationWiseOldGoldSettlementTransferSnapshot.locationname),
        'divisions': get_distinct(LocationWiseOldGoldSettlementTransferSnapshot.division),
        'groups': get_distinct(LocationWiseOldGoldSettlementTransferSnapshot.groupname),
        'purities': [str(p) for p in get_distinct(LocationWiseOldGoldSettlementTransferSnapshot.purity)],
    }


def get_sort_order_clause(sort_by, sort_order, group_cols):
    trans_date = func.cast(LocationWiseOldGoldSettlementTransferSnapshot.transdate, db.Date)
    curr_date = func.current_date()

    cond_2_5 = (LocationWiseOldGoldSettlementTransferSnapshot.transdate.isnot(None)) & (trans_date.between(curr_date - 5, curr_date - 2))
    cond_6_10 = (LocationWiseOldGoldSettlementTransferSnapshot.transdate.isnot(None)) & (trans_date.between(curr_date - 10, curr_date - 6))
    cond_11_15 = (LocationWiseOldGoldSettlementTransferSnapshot.transdate.isnot(None)) & (trans_date.between(curr_date - 15, curr_date - 11))
    cond_gt_15 = (LocationWiseOldGoldSettlementTransferSnapshot.transdate.isnot(None)) & (trans_date < curr_date - 15)

    sort_map = {
        'days_2_5': func.coalesce(func.sum(case((cond_2_5, LocationWiseOldGoldSettlementTransferSnapshot.grwt), else_=0)), 0),
        'days_2_5_settle': func.coalesce(func.sum(case((cond_2_5, LocationWiseOldGoldSettlementTransferSnapshot.grwt), else_=0)), 0),
        'days_2_5_trans': func.coalesce(func.sum(case((cond_2_5, LocationWiseOldGoldSettlementTransferSnapshot.transfer_grwt), else_=0)), 0),

        'days_6_10': func.coalesce(func.sum(case((cond_6_10, LocationWiseOldGoldSettlementTransferSnapshot.grwt), else_=0)), 0),
        'days_6_10_settle': func.coalesce(func.sum(case((cond_6_10, LocationWiseOldGoldSettlementTransferSnapshot.grwt), else_=0)), 0),
        'days_6_10_trans': func.coalesce(func.sum(case((cond_6_10, LocationWiseOldGoldSettlementTransferSnapshot.transfer_grwt), else_=0)), 0),

        'days_11_15': func.coalesce(func.sum(case((cond_11_15, LocationWiseOldGoldSettlementTransferSnapshot.grwt), else_=0)), 0),
        'days_11_15_settle': func.coalesce(func.sum(case((cond_11_15, LocationWiseOldGoldSettlementTransferSnapshot.grwt), else_=0)), 0),
        'days_11_15_trans': func.coalesce(func.sum(case((cond_11_15, LocationWiseOldGoldSettlementTransferSnapshot.transfer_grwt), else_=0)), 0),

        'days_gt_15': func.coalesce(func.sum(case((cond_gt_15, LocationWiseOldGoldSettlementTransferSnapshot.grwt), else_=0)), 0),
        'days_gt_15_settle': func.coalesce(func.sum(case((cond_gt_15, LocationWiseOldGoldSettlementTransferSnapshot.grwt), else_=0)), 0),
        'days_gt_15_trans': func.coalesce(func.sum(case((cond_gt_15, LocationWiseOldGoldSettlementTransferSnapshot.transfer_grwt), else_=0)), 0),

        'total_wt': func.coalesce(func.sum(LocationWiseOldGoldSettlementTransferSnapshot.grwt), 0),
        'total_settle': func.coalesce(func.sum(LocationWiseOldGoldSettlementTransferSnapshot.grwt), 0),
        'transfer_wt': func.coalesce(func.sum(LocationWiseOldGoldSettlementTransferSnapshot.transfer_grwt), 0),
        'total_trans': func.coalesce(func.sum(LocationWiseOldGoldSettlementTransferSnapshot.transfer_grwt), 0),
    }

    is_desc = (sort_order or 'asc').lower() == 'desc'

    if sort_by in sort_map:
        expr = sort_map[sort_by]
        order_clauses = [expr.desc() if is_desc else expr.asc()]
        for col in group_cols:
            order_clauses.append(col.asc())
        return order_clauses
    else:
        return [col.desc() if is_desc else col.asc() for col in group_cols]


@dashboard_bp.route('/location-wise-old-gold-settlement-transfer-summary')
def location_wise_old_gold_settlement_transfer_summary():
    try:
        ensure_table_exists()
        unread_count = Notification.query.filter_by(is_read=False).count()
        sync_time = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%I:%M %p")
        filter_options = fetch_filter_options()

        return render_template(
            'location_wise_old_gold_settlement_transfer.html',
            unread_count=unread_count,
            sync_time=sync_time,
            stats=None,
            rows=[],
            pagination=None,
            current_level='office',
            sort_by='hierarchy',
            sort_order='asc',
            filter_options=filter_options
        )
    except Exception as e:
        logger.error(f"Error in location_wise_old_gold_settlement_transfer_summary: {str(e)}", exc_info=True)
        return f"Error: {str(e)}", 500


@dashboard_bp.route('/partial/location-wise-old-gold-settlement-transfer')
def get_location_wise_old_gold_partial():
    try:
        ensure_table_exists()
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)

        parent_level = request.args.get('parent_level', '').strip()
        parent_value = request.args.get('parent_value', '').strip()
        office_val = request.args.get('office_val', '').strip()
        location_val = request.args.get('location_val', '').strip()
        division_val = request.args.get('division_val', '').strip()
        group_val = request.args.get('group_val', '').strip()

        is_child_rows = bool(parent_level)

        base_q = db.session.query(LocationWiseOldGoldSettlementTransferSnapshot)
        base_q = build_filters(base_q)

        # Determine hierarchy drill down
        # Hierarchy: office -> locationname -> division -> groupname -> purity
        if parent_level == 'office':
            base_q = base_q.filter(LocationWiseOldGoldSettlementTransferSnapshot.office == parent_value)
            group_cols = [
                LocationWiseOldGoldSettlementTransferSnapshot.office,
                LocationWiseOldGoldSettlementTransferSnapshot.locationname
            ]
            level = 'locationname'
        elif parent_level == 'locationname':
            if office_val:
                base_q = base_q.filter(LocationWiseOldGoldSettlementTransferSnapshot.office == office_val)
            base_q = base_q.filter(LocationWiseOldGoldSettlementTransferSnapshot.locationname == parent_value)
            group_cols = [
                LocationWiseOldGoldSettlementTransferSnapshot.office,
                LocationWiseOldGoldSettlementTransferSnapshot.locationname,
                LocationWiseOldGoldSettlementTransferSnapshot.division
            ]
            level = 'division'
        elif parent_level == 'division':
            if office_val:
                base_q = base_q.filter(LocationWiseOldGoldSettlementTransferSnapshot.office == office_val)
            if location_val:
                base_q = base_q.filter(LocationWiseOldGoldSettlementTransferSnapshot.locationname == location_val)
            base_q = base_q.filter(LocationWiseOldGoldSettlementTransferSnapshot.division == parent_value)
            group_cols = [
                LocationWiseOldGoldSettlementTransferSnapshot.office,
                LocationWiseOldGoldSettlementTransferSnapshot.locationname,
                LocationWiseOldGoldSettlementTransferSnapshot.division,
                LocationWiseOldGoldSettlementTransferSnapshot.groupname
            ]
            level = 'groupname'
        elif parent_level == 'groupname':
            if office_val:
                base_q = base_q.filter(LocationWiseOldGoldSettlementTransferSnapshot.office == office_val)
            if location_val:
                base_q = base_q.filter(LocationWiseOldGoldSettlementTransferSnapshot.locationname == location_val)
            if division_val:
                base_q = base_q.filter(LocationWiseOldGoldSettlementTransferSnapshot.division == division_val)
            base_q = base_q.filter(LocationWiseOldGoldSettlementTransferSnapshot.groupname == parent_value)
            group_cols = [
                LocationWiseOldGoldSettlementTransferSnapshot.office,
                LocationWiseOldGoldSettlementTransferSnapshot.locationname,
                LocationWiseOldGoldSettlementTransferSnapshot.division,
                LocationWiseOldGoldSettlementTransferSnapshot.groupname,
                LocationWiseOldGoldSettlementTransferSnapshot.purity
            ]
            level = 'purity'
        else:
            group_cols = [LocationWiseOldGoldSettlementTransferSnapshot.office]
            level = 'office'

        sort_by = request.args.get('sort_by', 'hierarchy').strip()
        sort_order = request.args.get('sort_order', 'asc').strip()

        row_agg_cols = get_aggregation_columns()
        order_by_clauses = get_sort_order_clause(sort_by, sort_order, group_cols)
        main_q = base_q.with_entities(*(group_cols + row_agg_cols))
        main_q = main_q.group_by(*group_cols).order_by(*order_by_clauses)

        pagination = main_q.paginate(page=page, per_page=per_page, error_out=False)

        processed_rows = []
        for r in pagination.items:
            label = ''
            off = r[0] or 'Unknown'
            loc = r[1] if len(group_cols) > 1 else ''
            div = r[2] if len(group_cols) > 2 else ''
            grp = r[3] if len(group_cols) > 3 else ''
            pur = r[4] if len(group_cols) > 4 else ''

            if level == 'office':
                label = off
            elif level == 'locationname':
                label = loc or 'Unknown'
            elif level == 'division':
                label = div or 'Unknown'
            elif level == 'groupname':
                label = grp or 'Unknown'
            elif level == 'purity':
                label = pur or 'Unknown'

            processed_rows.append({
                'office': off,
                'locationname': loc,
                'division': div,
                'groupname': grp,
                'purity': pur,
                'label': label,
                'level': level,
                'grwt_2_5': float(r.grwt_2_5 or 0.0),
                'netwt_2_5': float(r.netwt_2_5 or 0.0),
                'stwt_2_5': float(r.stwt_2_5 or 0.0),
                'transfer_grwt_2_5': float(r.transfer_grwt_2_5 or 0.0),
                'transfer_netwt_2_5': float(r.transfer_netwt_2_5 or 0.0),
                'transfer_stwt_2_5': float(r.transfer_stwt_2_5 or 0.0),

                'grwt_6_10': float(r.grwt_6_10 or 0.0),
                'netwt_6_10': float(r.netwt_6_10 or 0.0),
                'stwt_6_10': float(r.stwt_6_10 or 0.0),
                'transfer_grwt_6_10': float(r.transfer_grwt_6_10 or 0.0),
                'transfer_netwt_6_10': float(r.transfer_netwt_6_10 or 0.0),
                'transfer_stwt_6_10': float(r.transfer_stwt_6_10 or 0.0),

                'grwt_11_15': float(r.grwt_11_15 or 0.0),
                'netwt_11_15': float(r.netwt_11_15 or 0.0),
                'stwt_11_15': float(r.stwt_11_15 or 0.0),
                'transfer_grwt_11_15': float(r.transfer_grwt_11_15 or 0.0),
                'transfer_netwt_11_15': float(r.transfer_netwt_11_15 or 0.0),
                'transfer_stwt_11_15': float(r.transfer_stwt_11_15 or 0.0),

                'grwt_gt_15': float(r.grwt_gt_15 or 0.0),
                'netwt_gt_15': float(r.netwt_gt_15 or 0.0),
                'stwt_gt_15': float(r.stwt_gt_15 or 0.0),
                'transfer_grwt_gt_15': float(r.transfer_grwt_gt_15 or 0.0),
                'transfer_netwt_gt_15': float(r.transfer_netwt_gt_15 or 0.0),
                'transfer_stwt_gt_15': float(r.transfer_stwt_gt_15 or 0.0),

                'tot_grwt': float(r.tot_grwt or 0.0),
                'tot_netwt': float(r.tot_netwt or 0.0),
                'tot_stwt': float(r.tot_stwt or 0.0),
                'tot_transfer_grwt': float(r.tot_transfer_grwt or 0.0),
                'tot_transfer_netwt': float(r.tot_transfer_netwt or 0.0),
                'tot_transfer_stwt': float(r.tot_transfer_stwt or 0.0),
            })

        # Calculate overall stats for updated headers
        stats_query = db.session.query(LocationWiseOldGoldSettlementTransferSnapshot)
        stats_query = build_filters(stats_query)
        stats = compute_global_stats(stats_query)

        return render_template(
            'partials/_view_location_wise_old_gold_settlement_transfer.html',
            rows=processed_rows,
            pagination=pagination if not is_child_rows else None,
            current_level=level,
            is_child_rows=is_child_rows,
            parent_level=parent_level,
            parent_value=parent_value,
            sort_by=sort_by,
            sort_order=sort_order,
            stats=stats
        )
    except Exception as e:
        logger.error(f"Error in get_location_wise_old_gold_partial: {str(e)}", exc_info=True)
        return f'<div class="p-8 text-center text-red-500 font-bold">Backend Error: {str(e)}</div>', 200


@dashboard_bp.route('/api/location-wise-old-gold-settlement-transfer/options')
def location_wise_old_gold_options():
    try:
        ensure_table_exists()
        return jsonify(fetch_filter_options())
    except Exception as e:
        logger.error(f"Error in location_wise_old_gold_options: {str(e)}")
        return jsonify({"error": str(e)}), 500


@dashboard_bp.route('/sync/location-wise-old-gold-settlement-transfer', methods=['POST'])
def sync_location_wise_old_gold_settlement_transfer():
    from app.utils.sync_manager import sync_location_wise_old_gold_settlement_transfer_data
    user_id = session.get('user_id')
    return jsonify(sync_location_wise_old_gold_settlement_transfer_data(user_id))
