from flask import render_template, request, jsonify, session
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.dashboard import dashboard_bp
from app.models.snapshots import PendingAcceptanceSnapshot, ReportFeedback, PendingAcceptanceAction, HallmarkingDelayedSnapshot, HallmarkingDelayedFeedback
from app.models.auth import User
from app.extensions import db, redis_client
from sqlalchemy import func, case
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import logging
import json
from app.utils.decorators import require_perm

logger = logging.getLogger(__name__)

class CachedPagination:
    def __init__(self, items, page, per_page, total):
        self.items = items
        self.page = page
        self.per_page = per_page
        self.total = total
        self.has_prev = page > 1
        self.has_next = (page * per_page) < total
        self.prev_num = page - 1
        self.next_num = page + 1
        self.pages = (total + per_page - 1) // per_page if per_page else 0

def generate_cache_key(prefix, snapshot_date=None, **kwargs):
    sorted_kwargs = dict(sorted(kwargs.items()))
    args_str = ":".join(f"{k}={v}" for k, v in sorted_kwargs.items() if v)
    date_str = snapshot_date.strftime("%Y%m%d%H%M%S") if snapshot_date else "latest"
    return f"{prefix}:{date_str}:{args_str}"

def get_latest_feedback_subquery(page_code='PA'):
    # Subquery for latest feedback
    group_cols = [
        ReportFeedback.collection_owner,
        ReportFeedback.make_owner,
        ReportFeedback.supplier,
        ReportFeedback.collection
    ]
    subq = db.session.query(
        *group_cols,
        func.max(ReportFeedback.created_at).label('max_date')
    ).filter(ReportFeedback.page_code == page_code).group_by(
        *group_cols
    ).subquery()
    
    return db.session.query(ReportFeedback).join(
        subq,
        db.and_(
            func.coalesce(ReportFeedback.collection_owner, '') == func.coalesce(subq.c.collection_owner, ''),
            func.coalesce(ReportFeedback.make_owner, '') == func.coalesce(subq.c.make_owner, ''),
            func.coalesce(ReportFeedback.supplier, '') == func.coalesce(subq.c.supplier, ''),
            func.coalesce(ReportFeedback.collection, '') == func.coalesce(subq.c.collection, ''),
            ReportFeedback.created_at == subq.c.max_date
        )
    ).filter(ReportFeedback.page_code == page_code).subquery()

def get_latest_hd_feedback_subquery():
    group_cols = [
        HallmarkingDelayedFeedback.collection_owner,
        HallmarkingDelayedFeedback.make_owner,
        HallmarkingDelayedFeedback.supplier,
        HallmarkingDelayedFeedback.collection,
        HallmarkingDelayedFeedback.office,
        HallmarkingDelayedFeedback.hm_agent
    ]
    subq = db.session.query(
        *group_cols,
        func.max(HallmarkingDelayedFeedback.created_at).label('max_date')
    ).group_by(
        *group_cols
    ).subquery()
    
    return db.session.query(HallmarkingDelayedFeedback).join(
        subq,
        db.and_(
            func.coalesce(HallmarkingDelayedFeedback.collection_owner, '') == func.coalesce(subq.c.collection_owner, ''),
            func.coalesce(HallmarkingDelayedFeedback.make_owner, '') == func.coalesce(subq.c.make_owner, ''),
            func.coalesce(HallmarkingDelayedFeedback.supplier, '') == func.coalesce(subq.c.supplier, ''),
            func.coalesce(HallmarkingDelayedFeedback.collection, '') == func.coalesce(subq.c.collection, ''),
            func.coalesce(HallmarkingDelayedFeedback.office, '') == func.coalesce(subq.c.office, ''),
            func.coalesce(HallmarkingDelayedFeedback.hm_agent, '') == func.coalesce(subq.c.hm_agent, ''),
            HallmarkingDelayedFeedback.created_at == subq.c.max_date
        )
    ).subquery()

def get_latest_wizard_action_subquery(status_filter='pending_to_deliver_not_barcoded', action_type=None):
    base_filter = PendingAcceptanceAction.status_filter == status_filter
    if action_type:
        base_filter = db.and_(base_filter, PendingAcceptanceAction.action_type == action_type)
        
    subq = db.session.query(
        PendingAcceptanceAction.collection_owner,
        PendingAcceptanceAction.make_owner,
        PendingAcceptanceAction.supplier,
        PendingAcceptanceAction.collection,
        func.max(PendingAcceptanceAction.created_at).label('max_date')
    ).filter(base_filter).group_by(
        PendingAcceptanceAction.collection_owner,
        PendingAcceptanceAction.make_owner,
        PendingAcceptanceAction.supplier,
        PendingAcceptanceAction.collection
    ).subquery()
    
    return db.session.query(PendingAcceptanceAction).join(
        subq,
        db.and_(
            func.coalesce(PendingAcceptanceAction.collection_owner, '') == func.coalesce(subq.c.collection_owner, ''),
            func.coalesce(PendingAcceptanceAction.make_owner, '') == func.coalesce(subq.c.make_owner, ''),
            func.coalesce(PendingAcceptanceAction.supplier, '') == func.coalesce(subq.c.supplier, ''),
            func.coalesce(PendingAcceptanceAction.collection, '') == func.coalesce(subq.c.collection, ''),
            PendingAcceptanceAction.created_at == subq.c.max_date
        )
    ).filter(base_filter).subquery()

def apply_filters(query, search, latest_date_query, collection_owner=None, make_owner=None, 
                supplier=None, collection=None, classification=None, feedback_status=None,
                order_type=None, order_request_type=None, delay=None,
                branch_type=None,
                from_date=None, to_date=None, enable_date_filter=False,
                status_filter=None, office=None, hm_agent=None):
    
    if status_filter == 'hallmarking_delayed':
        model = HallmarkingDelayedSnapshot
        query = query.filter(model.snapshot_date == latest_date_query)
        if search:
            query = query.filter(model.supplier.ilike(f"%{search}%") | 
                                 model.collection_owner.ilike(f"%{search}%") |
                                 model.make_owner.ilike(f"%{search}%") |
                                 model.collection.ilike(f"%{search}%") |
                                 model.office.ilike(f"%{search}%") |
                                 model.hm_agent.ilike(f"%{search}%"))
        if office:
            query = query.filter(model.office == office)
        if make_owner:
            query = query.filter(model.make_owner == make_owner)
        if collection_owner:
            query = query.filter(model.collection_owner == collection_owner)
        if collection:
            query = query.filter(model.collection == collection)
        if hm_agent:
            query = query.filter(model.hm_agent == hm_agent)
        if supplier:
            query = query.filter(model.supplier == supplier)
            
        return query

    # Default logic for PendingAcceptanceSnapshot
    query = query.filter(PendingAcceptanceSnapshot.snapshot_date == latest_date_query)

    if delay is not None:
        try:
            delay_val = int(delay)
            query = query.filter(func.current_date() - PendingAcceptanceSnapshot.delivery_target_date >= delay_val)
        except (ValueError, TypeError):
            pass

    if search:
        query = query.filter(PendingAcceptanceSnapshot.supplier.ilike(f"%{search}%") | 
                             PendingAcceptanceSnapshot.collection_owner.ilike(f"%{search}%") |
                             PendingAcceptanceSnapshot.make_owner.ilike(f"%{search}%") |
                             PendingAcceptanceSnapshot.collection.ilike(f"%{search}%"))
                             
    if collection_owner:
        query = query.filter(PendingAcceptanceSnapshot.collection_owner == collection_owner)
    if make_owner:
        query = query.filter(PendingAcceptanceSnapshot.make_owner == make_owner)
    if supplier:
        query = query.filter(PendingAcceptanceSnapshot.supplier == supplier)
    if collection:
        query = query.filter(PendingAcceptanceSnapshot.collection == collection)
    if classification:
        query = query.filter(PendingAcceptanceSnapshot.classification == classification)
    if order_type:
        query = query.filter(PendingAcceptanceSnapshot.order_type == order_type)
    if order_request_type:
        query = query.filter(PendingAcceptanceSnapshot.order_request_type == order_request_type)
    if branch_type:
        query = query.filter(PendingAcceptanceSnapshot.branch_type == branch_type)
        
    if enable_date_filter and from_date and to_date:
        try:
            fd = datetime.strptime(from_date, '%Y-%m-%d').date()
            td = datetime.strptime(to_date, '%Y-%m-%d').date()
            query = query.filter(PendingAcceptanceSnapshot.order_date.between(fd, td))
        except ValueError:
            pass
            
    return query

def get_base_query(query_filter_func=None, feedback_status=None, 
                   feedback_from_date=None, feedback_to_date=None, 
                   enable_feedback_date_filter=False, status_filter='pending_to_accept'):
    p_code = 'PA'
    if status_filter == 'pending_to_deliver':
        p_code = 'PD'
    elif status_filter == 'pending_to_deliver_not_barcoded':
        p_code = 'PNB'
    elif status_filter == 'hallmarking_delayed':
        p_code = 'HD'
    
    latest_feedback = get_latest_hd_feedback_subquery() if status_filter == 'hallmarking_delayed' else get_latest_feedback_subquery(page_code=p_code)
    latest_continue = get_latest_wizard_action_subquery(status_filter=status_filter, action_type='CONTINUE')
    latest_cancel = get_latest_wizard_action_subquery(status_filter=status_filter, action_type='CANCEL')
    
    if status_filter == 'hallmarking_delayed':
        q = db.session.query(
            HallmarkingDelayedSnapshot.office,
            HallmarkingDelayedSnapshot.make_owner,
            HallmarkingDelayedSnapshot.collection_owner,
            HallmarkingDelayedSnapshot.collection,
            HallmarkingDelayedSnapshot.hm_agent,
            HallmarkingDelayedSnapshot.supplier,
            func.sum(HallmarkingDelayedSnapshot.pieces).label('sum_pieces'),
            func.sum(HallmarkingDelayedSnapshot.weight).label('sum_weight')
        )
        if query_filter_func:
            q = query_filter_func(q)
            
        q = q.group_by(
            HallmarkingDelayedSnapshot.office,
            HallmarkingDelayedSnapshot.make_owner,
            HallmarkingDelayedSnapshot.collection_owner,
            HallmarkingDelayedSnapshot.collection,
            HallmarkingDelayedSnapshot.hm_agent,
            HallmarkingDelayedSnapshot.supplier
        ).subquery('agg_snapshot')

        query = db.session.query(
            q.c.office,
            q.c.make_owner,
            q.c.collection_owner,
            q.c.collection,
            q.c.hm_agent,
            q.c.supplier,
            q.c.sum_pieces,
            q.c.sum_weight,
            latest_feedback.c.feedback_text,
            latest_feedback.c.feedback_category,
            latest_feedback.c.username,
            latest_feedback.c.created_at
        ).outerjoin(
            latest_feedback,
            db.and_(
                func.coalesce(q.c.office, '') == func.coalesce(latest_feedback.c.office, ''),
                func.coalesce(q.c.make_owner, '') == func.coalesce(latest_feedback.c.make_owner, ''),
                func.coalesce(q.c.collection_owner, '') == func.coalesce(latest_feedback.c.collection_owner, ''),
                func.coalesce(q.c.collection, '') == func.coalesce(latest_feedback.c.collection, ''),
                func.coalesce(q.c.hm_agent, '') == func.coalesce(latest_feedback.c.hm_agent, ''),
                func.coalesce(q.c.supplier, '') == func.coalesce(latest_feedback.c.supplier, '')
            )
        )
    else:
        # Base query for aggregation
        q = db.session.query(
            PendingAcceptanceSnapshot.collection_owner,
            PendingAcceptanceSnapshot.make_owner,
            PendingAcceptanceSnapshot.supplier,
            PendingAcceptanceSnapshot.collection,
            func.sum(PendingAcceptanceSnapshot.order_wt).label('sum_order_wt'),
            func.sum(PendingAcceptanceSnapshot.accepted_wt).label('sum_accepted_wt'),
            func.sum(PendingAcceptanceSnapshot.pending_to_accepted_wt).label('sum_pending_to_accepted_wt'),
            func.sum(PendingAcceptanceSnapshot.pending_to_deliver_pcs).label('sum_pending_to_deliver_pcs'),
            func.sum(PendingAcceptanceSnapshot.pending_to_deliver_wt).label('sum_pending_to_deliver_wt'),
            func.sum(PendingAcceptanceSnapshot.not_barcoded_pcs).label('sum_not_barcoded_pcs'),
            func.sum(PendingAcceptanceSnapshot.not_barcoded_wt).label('sum_not_barcoded_wt')
        )
        
        if query_filter_func:
            q = query_filter_func(q)
            
        # Apply status filter
        if status_filter == 'pending_to_deliver':
            q = q.filter(PendingAcceptanceSnapshot.pending_to_deliver_pcs > 0)
        elif status_filter == 'pending_to_deliver_not_barcoded':
            q = q.filter(PendingAcceptanceSnapshot.not_barcoded_pcs > 0)
        else:
            # Default to pending_to_accept
            q = q.filter(PendingAcceptanceSnapshot.pending_to_accepted_wt > 0)

        q = q.group_by(
            PendingAcceptanceSnapshot.collection_owner,
            PendingAcceptanceSnapshot.make_owner,
            PendingAcceptanceSnapshot.supplier,
            PendingAcceptanceSnapshot.collection
        ).subquery('agg_snapshot')

        # Join with feedback
        query = db.session.query(
            q.c.collection_owner,
            q.c.make_owner,
            q.c.supplier,
            q.c.collection,
            q.c.sum_order_wt,
            q.c.sum_accepted_wt,
            q.c.sum_pending_to_accepted_wt,
            q.c.sum_pending_to_deliver_pcs,
            q.c.sum_pending_to_deliver_wt,
            q.c.sum_not_barcoded_pcs,
            q.c.sum_not_barcoded_wt,
            latest_feedback.c.feedback_text,
            latest_feedback.c.feedback_category,
            latest_feedback.c.username,
            latest_feedback.c.created_at,
            latest_continue.c.id.label('continue_id'),
            latest_continue.c.reason.label('continue_reason'),
            latest_continue.c.action_data.label('continue_data'),
            latest_continue.c.username.label('continue_username'),
            latest_continue.c.created_at.label('continue_created_at'),
            latest_cancel.c.id.label('cancel_id'),
            latest_cancel.c.reason.label('cancel_reason'),
            latest_cancel.c.action_data.label('cancel_data'),
            latest_cancel.c.username.label('cancel_username'),
            latest_cancel.c.created_at.label('cancel_created_at')
        ).outerjoin(
            latest_feedback,
            db.and_(
                func.coalesce(q.c.collection_owner, '') == func.coalesce(latest_feedback.c.collection_owner, ''),
                func.coalesce(q.c.make_owner, '') == func.coalesce(latest_feedback.c.make_owner, ''),
                func.coalesce(q.c.supplier, '') == func.coalesce(latest_feedback.c.supplier, ''),
                func.coalesce(q.c.collection, '') == func.coalesce(latest_feedback.c.collection, '')
            )
        ).outerjoin(
            latest_continue,
            db.and_(
                func.coalesce(q.c.collection_owner, '') == func.coalesce(latest_continue.c.collection_owner, ''),
                func.coalesce(q.c.make_owner, '') == func.coalesce(latest_continue.c.make_owner, ''),
                func.coalesce(q.c.supplier, '') == func.coalesce(latest_continue.c.supplier, ''),
                func.coalesce(q.c.collection, '') == func.coalesce(latest_continue.c.collection, '')
            )
        ).outerjoin(
            latest_cancel,
            db.and_(
                func.coalesce(q.c.collection_owner, '') == func.coalesce(latest_cancel.c.collection_owner, ''),
                func.coalesce(q.c.make_owner, '') == func.coalesce(latest_cancel.c.make_owner, ''),
                func.coalesce(q.c.supplier, '') == func.coalesce(latest_cancel.c.supplier, ''),
                func.coalesce(q.c.collection, '') == func.coalesce(latest_cancel.c.collection, '')
            )
        )

    if enable_feedback_date_filter and feedback_from_date and feedback_to_date:
        try:
            ffd = datetime.strptime(feedback_from_date, '%Y-%m-%d').date()
            ftd = datetime.strptime(feedback_to_date, '%Y-%m-%d').date()
            # Since created_at is DateTime, we compare using between
            ftd_plus_one = ftd + timedelta(days=1)
            query = query.filter(latest_feedback.c.created_at >= ffd, latest_feedback.c.created_at < ftd_plus_one)
        except ValueError:
            pass

    if feedback_status:
        if status_filter == 'pending_to_deliver_not_barcoded':
            if feedback_status == 'with':
                query = query.filter(db.or_(latest_continue.c.id != None, latest_cancel.c.id != None))
            elif feedback_status == 'without':
                query = query.filter(db.and_(latest_continue.c.id == None, latest_cancel.c.id == None))
        else:
            if feedback_status == 'with':
                query = query.filter(latest_feedback.c.feedback_text != None)
            elif feedback_status == 'without':
                query = query.filter(latest_feedback.c.feedback_text == None)
            
    if status_filter == 'pending_to_deliver':
        query = query.order_by(
            q.c.sum_pending_to_deliver_pcs.desc(), 
            (q.c.sum_order_wt - q.c.sum_accepted_wt).asc()
        )
    elif status_filter == 'pending_to_deliver_not_barcoded':
        query = query.order_by(
            q.c.sum_not_barcoded_pcs.desc(), 
            (q.c.sum_order_wt - q.c.sum_accepted_wt).asc()
        )
    elif status_filter == 'hallmarking_delayed':
        query = query.order_by(q.c.sum_pieces.desc(), q.c.sum_weight.desc())
    else:
        query = query.order_by(q.c.sum_accepted_wt.desc(), q.c.sum_pending_to_accepted_wt.desc())
    return query

def calculate_stats(query, status_filter='pending_to_accept'):
    try:
        s = query.order_by(None).subquery()
        if status_filter == 'hallmarking_delayed':
            res = db.session.query(
                func.sum(s.c.sum_pieces),
                func.sum(s.c.sum_weight),
                func.count(case(((s.c.feedback_text != None), 1))),
                func.count(case(((s.c.feedback_text == None), 1)))
            ).first()
            return {
                'total_pieces': float(res[0] or 0),
                'total_weight': float(res[1] or 0),
                'with_feedback': int(res[2] or 0),
                'without_feedback': int(res[3] or 0)
            }

        res = db.session.query(
            func.sum(s.c.sum_order_wt),
            func.sum(s.c.sum_accepted_wt),
            func.sum(s.c.sum_pending_to_accepted_wt),
            func.sum(s.c.sum_pending_to_deliver_pcs),
            func.sum(s.c.sum_pending_to_deliver_wt),
            func.sum(s.c.sum_not_barcoded_pcs),
            func.sum(s.c.sum_not_barcoded_wt),
            func.count(case((
                (s.c.continue_id != None) | (s.c.cancel_id != None) if status_filter == 'pending_to_deliver_not_barcoded' else (s.c.feedback_text != None), 
                1
            ))),
            func.count(case((
                (s.c.continue_id == None) & (s.c.cancel_id == None) if status_filter == 'pending_to_deliver_not_barcoded' else (s.c.feedback_text == None), 
                1
            )))
        ).first()
        
        return {
            'total_order_wt': float(res[0] or 0),
            'total_accepted_wt': float(res[1] or 0),
            'total_pending_to_accepted_wt': float(res[2] or 0),
            'total_pending_to_deliver_pcs': float(res[3] or 0),
            'total_pending_to_deliver_wt': float(res[4] or 0),
            'total_not_barcoded_pcs': float(res[5] or 0),
            'total_not_barcoded_wt': float(res[6] or 0),
            'with_feedback': int(res[7] or 0),
            'without_feedback': int(res[8] or 0)
        }
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error calculating stats: {str(e)}")
        return {
            'total_order_wt': 0,
            'total_accepted_wt': 0,
            'total_pending_to_accepted_wt': 0,
            'total_pending_to_deliver_pcs': 0,
            'total_pending_to_deliver_wt': 0,
            'total_not_barcoded_pcs': 0,
            'total_not_barcoded_wt': 0,
            'with_feedback': 0,
            'without_feedback': 0
        }

@dashboard_bp.route('/pending-acceptance-feedback')
@jwt_required()
def pending_acceptance():
    try:
        from app.models.core import Notification
        unread_count = Notification.query.filter_by(is_read=False).count()
        sync_time = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%I:%M %p")

        status_filter = request.args.get('status_filter', 'pending_to_accept')

        if status_filter == 'hallmarking_delayed':
            has_any_data = db.session.query(HallmarkingDelayedSnapshot.id).first()
            latest_date_query = db.session.query(func.max(HallmarkingDelayedSnapshot.snapshot_date)).scalar()
        else:
            has_any_data = db.session.query(PendingAcceptanceSnapshot.id).first()
            latest_date_query = db.session.query(func.max(PendingAcceptanceSnapshot.snapshot_date)).scalar()

        if not has_any_data:
            return render_template('pending_acceptance.html', 
                                 unread_count=unread_count, 
                                 sync_time=sync_time, 
                                 rows=[], 
                                 pagination=None,
                                 current_username='',
                                 filters={})

        search = request.args.get('search', '').strip()
        f_collection_owner = request.args.get('collection_owner', '')
        f_make_owner = request.args.get('make_owner', '')
        f_supplier = request.args.get('supplier', '')
        f_collection = request.args.get('collection', '')
        f_order_type = request.args.get('order_type', '')
        f_order_request_type = request.args.get('order_request_type', '')
        f_classification = request.args.get('classification', '')
        f_feedback_status = request.args.get('feedback_status', '')
        f_branch_type = request.args.get('branch_type', '')
        f_office = request.args.get('office', '')
        f_hm_agent = request.args.get('hm_agent', '')
        
        f_delay = request.args.get('delay')
        f_delay_enabled = request.args.get('delay_enabled', 'false') == 'true'
        
        # Default to 5 days if status is pending_to_deliver_not_barcoded and NOT explicitly disabled
        # This handles the initial load where delay might not be in URL yet
        if f_delay is None and status_filter == 'pending_to_deliver_not_barcoded' and request.args.get('delay_enabled') is None:
            f_delay = '5'
            f_delay_enabled = True
            
        if not f_delay_enabled:
            f_delay = None

        f_from_date = request.args.get('from_date', '')
        f_to_date = request.args.get('to_date', '')
        f_enable_date_filter = request.args.get('enable_date_filter', 'false') == 'true'

        f_feedback_from_date = request.args.get('feedback_from_date', '')
        f_feedback_to_date = request.args.get('feedback_to_date', '')
        f_enable_feedback_date_filter = request.args.get('enable_feedback_date_filter', 'false') == 'true'
        
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)
        # 1. Role-based bypass logic
        roles = [r.upper() for r in session.get('roles', [])]
        is_manager_2 = 'MANAGER_2' in roles
        is_admin = 'ADMIN' in roles
        current_username = session.get('username', '').strip()
        
        # Determine if we should apply the "own data only" restriction
        restrict_to_user = not is_admin and not is_manager_2 and current_username
        
        # 2. Update cache key to be user/role specific
        cache_key = generate_cache_key('pending_acc_main', latest_date_query, 
                                     username=current_username if restrict_to_user else 'admin',
                                     search=search, feedback_status=f_feedback_status,
                                     collection_owner=f_collection_owner,
                                     make_owner=f_make_owner, supplier=f_supplier, 
                                     collection=f_collection, 
                                     classification=f_classification,
                                     order_type=f_order_type,
                                     order_request_type=f_order_request_type,
                                     branch_type=f_branch_type,
                                     office=f_office,
                                     hm_agent=f_hm_agent,
                                     delay=f_delay,
                                     from_date=f_from_date,
                                     to_date=f_to_date,
                                     enable_date_filter=f_enable_date_filter,
                                     feedback_from_date=f_feedback_from_date,
                                     feedback_to_date=f_feedback_to_date,
                                     enable_feedback_date_filter=f_enable_feedback_date_filter,
                                     status_filter=status_filter,
                                     page=page, per_page=per_page)
        
        # 3. Helper to fetch filter lists
        def fetch_filter_options():
            status_filter = request.args.get('status_filter', 'pending_to_accept')
            if status_filter == 'hallmarking_delayed':
                base_q = db.session.query(HallmarkingDelayedSnapshot).filter(
                    HallmarkingDelayedSnapshot.snapshot_date == latest_date_query
                )
                if restrict_to_user:
                    u = current_username.lower()
                    base_q = base_q.filter(
                        (func.lower(func.trim(HallmarkingDelayedSnapshot.collection_owner)) == u) | 
                        (func.lower(func.trim(HallmarkingDelayedSnapshot.make_owner)) == u) 
                    )
                return {
                    'offices': [r[0] for r in base_q.with_entities(HallmarkingDelayedSnapshot.office).distinct().order_by(HallmarkingDelayedSnapshot.office).all()],
                    'make_owners': [r[0] for r in base_q.with_entities(HallmarkingDelayedSnapshot.make_owner).distinct().order_by(HallmarkingDelayedSnapshot.make_owner).all()],
                    'collection_owners': [current_username] if restrict_to_user else [r[0] for r in base_q.with_entities(HallmarkingDelayedSnapshot.collection_owner).distinct().order_by(HallmarkingDelayedSnapshot.collection_owner).all()],
                    'collections': [r[0] for r in base_q.with_entities(HallmarkingDelayedSnapshot.collection).distinct().order_by(HallmarkingDelayedSnapshot.collection).all()],
                    'hm_agents': [r[0] for r in base_q.with_entities(HallmarkingDelayedSnapshot.hm_agent).distinct().order_by(HallmarkingDelayedSnapshot.hm_agent).all()],
                    'suppliers': [r[0] for r in base_q.with_entities(HallmarkingDelayedSnapshot.supplier).distinct().order_by(HallmarkingDelayedSnapshot.supplier).all()],
                }

            base_q = db.session.query(PendingAcceptanceSnapshot).filter(
                PendingAcceptanceSnapshot.snapshot_date == latest_date_query
            )
            if restrict_to_user:
                u = current_username.lower()
                base_q = base_q.filter(
                    (func.lower(func.trim(PendingAcceptanceSnapshot.collection_owner)) == u) | 
                    (func.lower(func.trim(PendingAcceptanceSnapshot.make_owner)) == u) 
                )

            return {
                'collection_owners': [current_username] if restrict_to_user else [r[0] for r in base_q.with_entities(PendingAcceptanceSnapshot.collection_owner).distinct().order_by(PendingAcceptanceSnapshot.collection_owner).all()],
                'make_owners': [r[0] for r in base_q.with_entities(PendingAcceptanceSnapshot.make_owner).distinct().order_by(PendingAcceptanceSnapshot.make_owner).all()],
                'suppliers': [r[0] for r in base_q.with_entities(PendingAcceptanceSnapshot.supplier).distinct().order_by(PendingAcceptanceSnapshot.supplier).all()],
                'collections': [r[0] for r in base_q.with_entities(PendingAcceptanceSnapshot.collection).distinct().order_by(PendingAcceptanceSnapshot.collection).all()],
                'classifications': [r[0] for r in base_q.with_entities(PendingAcceptanceSnapshot.classification).distinct().order_by(PendingAcceptanceSnapshot.classification).all()],
                'order_types': [r[0] for r in base_q.with_entities(PendingAcceptanceSnapshot.order_type).distinct().order_by(PendingAcceptanceSnapshot.order_type).all()],
                'order_request_types': [r[0] for r in base_q.with_entities(PendingAcceptanceSnapshot.order_request_type).distinct().order_by(PendingAcceptanceSnapshot.order_request_type).all()],
                'branch_types': [r[0] for r in base_q.with_entities(PendingAcceptanceSnapshot.branch_type).distinct().order_by(PendingAcceptanceSnapshot.branch_type).all()],
            }

        filter_options = fetch_filter_options()

        return render_template('pending_acceptance.html', 
                             unread_count=unread_count, 
                             sync_time=sync_time, 
                             stats=None,
                             current_username=current_username,
                             filter_options=filter_options,
                             status_filter=status_filter,
                             initial_load=True)
                             
    except Exception as e:
        logger.error(f"Error in pending_acceptance: {str(e)}")
        return f"Error: {str(e)}", 500

def get_hierarchical_rows(flat_rows):
    """Transform flat rows into a hierarchical structure for drill-down."""
    import hashlib
    def get_id(*args):
        return hashlib.md5((":".join(map(str, args))).encode()).hexdigest()[:8]

    hierarchy = {}
    for r in flat_rows:
        m = r.get('make_owner') or 'Unknown'
        c = r.get('collection_owner') or 'Unknown'
        col = r.get('collection') or 'Unknown'
        s = r.get('supplier') or 'Unknown'
        
        if m not in hierarchy:
            hierarchy[m] = {'pcs': 0, 'wt': 0, 'order_wt': 0, 'accepted_wt': 0, 'children': {}}
        if c not in hierarchy[m]['children']:
            hierarchy[m]['children'][c] = {'pcs': 0, 'wt': 0, 'order_wt': 0, 'accepted_wt': 0, 'children': {}}
        if col not in hierarchy[m]['children'][c]['children']:
            hierarchy[m]['children'][c]['children'][col] = {'pcs': 0, 'wt': 0, 'order_wt': 0, 'accepted_wt': 0, 'children': []}
            
        hierarchy[m]['pcs'] += r.get('not_barcoded_pcs', 0)
        hierarchy[m]['wt'] += r.get('not_barcoded_wt', 0)
        hierarchy[m]['order_wt'] += r.get('order_wt', 0)
        hierarchy[m]['accepted_wt'] += r.get('accepted_wt', 0)
        
        hierarchy[m]['children'][c]['pcs'] += r.get('not_barcoded_pcs', 0)
        hierarchy[m]['children'][c]['wt'] += r.get('not_barcoded_wt', 0)
        hierarchy[m]['children'][c]['order_wt'] += r.get('order_wt', 0)
        hierarchy[m]['children'][c]['accepted_wt'] += r.get('accepted_wt', 0)
        
        hierarchy[m]['children'][c]['children'][col]['pcs'] += r.get('not_barcoded_pcs', 0)
        hierarchy[m]['children'][c]['children'][col]['wt'] += r.get('not_barcoded_wt', 0)
        hierarchy[m]['children'][c]['children'][col]['order_wt'] += r.get('order_wt', 0)
        hierarchy[m]['children'][c]['children'][col]['accepted_wt'] += r.get('accepted_wt', 0)
        
        hierarchy[m]['children'][c]['children'][col]['children'].append(r)

    result = []
    for m, m_data in sorted(hierarchy.items()):
        m_id = f"m_{get_id(m)}"
        result.append({
            'level': 1, 'id': m_id, 'parent_id': None, 'label': m,
            'not_barcoded_pcs': m_data['pcs'], 'not_barcoded_wt': m_data['wt'],
            'order_wt': m_data['order_wt'], 'accepted_wt': m_data['accepted_wt'],
            'is_leaf': False
        })
        for c, c_data in sorted(m_data['children'].items()):
            c_id = f"c_{get_id(m, c)}"
            result.append({
                'level': 2, 'id': c_id, 'parent_id': m_id, 'label': c,
                'not_barcoded_pcs': c_data['pcs'], 'not_barcoded_wt': c_data['wt'],
                'order_wt': c_data['order_wt'], 'accepted_wt': c_data['accepted_wt'],
                'is_leaf': False
            })
            for col, col_data in sorted(c_data['children'].items()):
                col_id = f"col_{get_id(m, c, col)}"
                result.append({
                    'level': 3, 'id': col_id, 'parent_id': c_id, 'label': col,
                    'not_barcoded_pcs': col_data['pcs'], 'not_barcoded_wt': col_data['wt'],
                    'order_wt': col_data['order_wt'], 'accepted_wt': col_data['accepted_wt'],
                    'is_leaf': False
                })
                for r in sorted(col_data['children'], key=lambda x: x.get('not_barcoded_wt', 0), reverse=True):
                    r_id = f"r_{get_id(m, c, col, r.get('supplier'))}"
                    r.update({
                        'level': 4, 'id': r_id, 'parent_id': col_id, 'label': r.get('supplier') or 'Unknown',
                        'is_leaf': True
                    })
                    result.append(r)
    return result

def get_hd_hierarchical_rows(flat_rows):
    """Transform flat rows into a hierarchical structure for Hallmarking Delayed (6 levels)."""
    import hashlib
    def get_id(*args):
        return hashlib.md5((":".join(map(str, args))).encode()).hexdigest()[:8]

    hierarchy = {}
    for r in flat_rows:
        off = r.get('office') or 'Unknown'
        mo = r.get('make_owner') or 'Unknown'
        co = r.get('collection_owner') or 'Unknown'
        col = r.get('collection') or 'Unknown'
        hma = r.get('hm_agent') or 'Unknown'
        s = r.get('supplier') or 'Unknown'
        
        # Level 1: Office
        if off not in hierarchy:
            hierarchy[off] = {'pcs': 0, 'wt': 0, 'children': {}}
        # Level 2: Make Owner
        if mo not in hierarchy[off]['children']:
            hierarchy[off]['children'][mo] = {'pcs': 0, 'wt': 0, 'children': {}}
        # Level 3: Collection Owner
        if co not in hierarchy[off]['children'][mo]['children']:
            hierarchy[off]['children'][mo]['children'][co] = {'pcs': 0, 'wt': 0, 'children': {}}
        # Level 4: Collection
        if col not in hierarchy[off]['children'][mo]['children'][co]['children']:
            hierarchy[off]['children'][mo]['children'][co]['children'][col] = {'pcs': 0, 'wt': 0, 'children': {}}
        # Level 5: Hallmark Agency
        if hma not in hierarchy[off]['children'][mo]['children'][co]['children'][col]['children']:
            hierarchy[off]['children'][mo]['children'][co]['children'][col]['children'][hma] = {'pcs': 0, 'wt': 0, 'children': []}
            
        pcs = r.get('sum_pieces', 0)
        wt = r.get('sum_weight', 0)
        
        hierarchy[off]['pcs'] += pcs
        hierarchy[off]['wt'] += wt
        
        hierarchy[off]['children'][mo]['pcs'] += pcs
        hierarchy[off]['children'][mo]['wt'] += wt
        
        hierarchy[off]['children'][mo]['children'][co]['pcs'] += pcs
        hierarchy[off]['children'][mo]['children'][co]['wt'] += wt
        
        hierarchy[off]['children'][mo]['children'][co]['children'][col]['pcs'] += pcs
        hierarchy[off]['children'][mo]['children'][co]['children'][col]['wt'] += wt
        
        hierarchy[off]['children'][mo]['children'][co]['children'][col]['children'][hma]['pcs'] += pcs
        hierarchy[off]['children'][mo]['children'][co]['children'][col]['children'][hma]['wt'] += wt
        
        hierarchy[off]['children'][mo]['children'][co]['children'][col]['children'][hma]['children'].append(r)

    result = []
    for off, off_data in sorted(hierarchy.items()):
        off_id = f"off_{get_id(off)}"
        result.append({
            'level': 1, 'id': off_id, 'parent_id': None, 'label': off,
            'sum_pieces': off_data['pcs'], 'sum_weight': off_data['wt'],
            'is_leaf': False
        })
        for mo, mo_data in sorted(off_data['children'].items()):
            mo_id = f"mo_{get_id(off, mo)}"
            result.append({
                'level': 2, 'id': mo_id, 'parent_id': off_id, 'label': mo,
                'sum_pieces': mo_data['pcs'], 'sum_weight': mo_data['wt'],
                'is_leaf': False
            })
            for co, co_data in sorted(mo_data['children'].items()):
                co_id = f"co_{get_id(off, mo, co)}"
                result.append({
                    'level': 3, 'id': co_id, 'parent_id': mo_id, 'label': co,
                    'sum_pieces': co_data['pcs'], 'sum_weight': co_data['wt'],
                    'is_leaf': False
                })
                for col, col_data in sorted(co_data['children'].items()):
                    col_id = f"col_{get_id(off, mo, co, col)}"
                    result.append({
                        'level': 4, 'id': col_id, 'parent_id': co_id, 'label': col,
                        'sum_pieces': col_data['pcs'], 'sum_weight': col_data['wt'],
                        'is_leaf': False
                    })
                    for hma, hma_data in sorted(col_data['children'].items()):
                        hma_id = f"hma_{get_id(off, mo, co, col, hma)}"
                        result.append({
                            'level': 5, 'id': hma_id, 'parent_id': col_id, 'label': hma,
                            'sum_pieces': hma_data['pcs'], 'sum_weight': hma_data['wt'],
                            'is_leaf': False
                        })
                        for r in sorted(hma_data['children'], key=lambda x: x.get('sum_weight', 0), reverse=True):
                            r_id = f"r_{get_id(off, mo, co, col, hma, r.get('supplier'))}"
                            r.update({
                                'level': 6, 'id': r_id, 'parent_id': hma_id, 'label': r.get('supplier') or 'Unknown',
                                'is_leaf': True
                            })
                            result.append(r)
    return result

@dashboard_bp.route('/partial/pending-acceptance-feedback')
@jwt_required()
def get_pending_acceptance_partial():
    try:
        status_filter = request.args.get('status_filter', 'pending_to_accept')
        if status_filter == 'hallmarking_delayed':
            latest_date_query = db.session.query(func.max(HallmarkingDelayedSnapshot.snapshot_date)).scalar()
        else:
            latest_date_query = db.session.query(func.max(PendingAcceptanceSnapshot.snapshot_date)).scalar()

        search = request.args.get('search', '').strip()
        f_collection_owner = request.args.get('collection_owner', '')
        f_make_owner = request.args.get('make_owner', '')
        f_supplier = request.args.get('supplier', '')
        f_collection = request.args.get('collection', '')
        f_classification = request.args.get('classification', '')
        f_order_type = request.args.get('order_type', '')
        f_order_request_type = request.args.get('order_request_type', '')
        f_branch_type = request.args.get('branch_type', '')
        f_feedback_status = request.args.get('feedback_status', '')
        f_delay = request.args.get('delay')
        f_delay_enabled = request.args.get('delay_enabled', 'false') == 'true'
        
        f_office = request.args.get('office', '')
        f_hm_agent = request.args.get('hm_agent', '')

        # Default to 5 days if status is pending_to_deliver_not_barcoded and NOT explicitly disabled
        if f_delay is None and status_filter == 'pending_to_deliver_not_barcoded' and request.args.get('delay_enabled') is None:
            f_delay = '5'
            f_delay_enabled = True

        if not f_delay_enabled:
            f_delay = None

        f_from_date = request.args.get('from_date', '')
        f_to_date = request.args.get('to_date', '')
        f_enable_date_filter = request.args.get('enable_date_filter', 'false') == 'true'

        f_feedback_from_date = request.args.get('feedback_from_date', '')
        f_feedback_to_date = request.args.get('feedback_to_date', '')
        f_enable_feedback_date_filter = request.args.get('enable_feedback_date_filter', 'false') == 'true'
        
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)
        
        # 1. Role-based bypass logic
        roles = [r.upper() for r in session.get('roles', [])]
        is_manager_2 = 'MANAGER_2' in roles
        is_admin = 'ADMIN' in roles
        current_username = session.get('username', '').strip()
        
        # Determine if restrict to user
        restrict_to_user = not is_admin and not is_manager_2 and current_username
        
        # 2. Update cache key to be user/role specific
        cache_key = generate_cache_key('pending_acc_partial', latest_date_query, 
                                     username=current_username if restrict_to_user else 'admin',
                                     search=search, feedback_status=f_feedback_status,
                                     collection_owner=f_collection_owner,
                                     make_owner=f_make_owner, supplier=f_supplier, 
                                     collection=f_collection, 
                                     classification=f_classification,
                                     order_type=f_order_type,
                                     order_request_type=f_order_request_type,
                                     branch_type=f_branch_type,
                                     office=f_office,
                                     hm_agent=f_hm_agent,
                                     delay=f_delay,
                                     from_date=f_from_date,
                                     to_date=f_to_date,
                                     enable_date_filter=f_enable_date_filter,
                                     feedback_from_date=f_feedback_from_date,
                                     feedback_to_date=f_feedback_to_date,
                                     enable_feedback_date_filter=f_enable_feedback_date_filter,
                                     status_filter=status_filter,
                                     page=page, per_page=per_page)
        
        cached_data = redis_client.get(cache_key)
        if cached_data:
            data = json.loads(cached_data)
            pagination = CachedPagination(data['rows'], page, per_page, data['total'])
            template_name = 'partials/_view_pending_acceptance.html'
            if status_filter == 'pending_to_deliver':
                template_name = 'partials/_view_pending_acceptance_to_deliver.html'
            elif status_filter == 'pending_to_deliver_not_barcoded':
                template_name = 'partials/_view_pending_acceptance_not_barcoded.html'
            elif status_filter == 'hallmarking_delayed':
                template_name = 'partials/_view_hallmarking_delayed.html'

            return render_template(template_name, 
                                 rows=data['rows'], 
                                 pagination=pagination,
                                 stats=data.get('stats', {}),
                                 status_filter=status_filter,
                                 current_username=current_username)

        # 3. Filter function to apply to base snapshot query before aggregation
        def filter_func(q):
            if restrict_to_user:
                u = current_username.lower()
                if status_filter == 'hallmarking_delayed':
                    q = q.filter(
                        (func.lower(func.trim(HallmarkingDelayedSnapshot.collection_owner)) == u) | 
                        (func.lower(func.trim(HallmarkingDelayedSnapshot.make_owner)) == u)
                    )
                else:
                    q = q.filter(
                        (func.lower(func.trim(PendingAcceptanceSnapshot.collection_owner)) == u) | 
                        (func.lower(func.trim(PendingAcceptanceSnapshot.make_owner)) == u)
                    )
            elif not is_admin and not is_manager_2 and not current_username:
                q = q.filter(False)
            
            return apply_filters(
                q, search, latest_date_query, 
                collection_owner=f_collection_owner, 
                make_owner=f_make_owner,
                supplier=f_supplier, 
                collection=f_collection,
                classification=f_classification,
                order_type=f_order_type, 
                order_request_type=f_order_request_type,
                branch_type=f_branch_type,
                delay=f_delay,
                from_date=f_from_date,
                to_date=f_to_date,
                enable_date_filter=f_enable_date_filter,
                status_filter=status_filter,
                office=f_office,
                hm_agent=f_hm_agent
            )

        query = get_base_query(query_filter_func=filter_func, feedback_status=f_feedback_status,
                               feedback_from_date=f_feedback_from_date,
                               feedback_to_date=f_feedback_to_date,
                               enable_feedback_date_filter=f_enable_feedback_date_filter,
                               status_filter=status_filter)
        
        # Calculate Stats (now passing the formulated query)
        stats = calculate_stats(query, status_filter=status_filter)
        
        

        # For hierarchical view, we fetch all relevant records to build the tree
        if status_filter == 'pending_to_deliver_not_barcoded':
            per_page = 2000
            
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        
        processed_rows = []
        if status_filter == 'hallmarking_delayed':
            for r in pagination.items:
                row_dict = {
                    'id': f"{getattr(r, 'office', '')}_{getattr(r, 'hm_agent', '')}_{getattr(r, 'make_owner', '')}_{getattr(r, 'collection_owner', '')}_{getattr(r, 'collection', '')}_{getattr(r, 'supplier', '')}",
                    'office': getattr(r, 'office', '') or '',
                    'hm_agent': getattr(r, 'hm_agent', '') or '',
                    'make_owner': getattr(r, 'make_owner', '') or '',
                    'collection_owner': getattr(r, 'collection_owner', '') or '',
                    'collection': getattr(r, 'collection', '') or '',
                    'supplier': getattr(r, 'supplier', '') or '',
                    'sum_pieces': float(getattr(r, 'sum_pieces', 0) or 0),
                    'sum_weight': float(getattr(r, 'sum_weight', 0) or 0),
                    'feedback_text': getattr(r, 'feedback_text', '') or '',
                    'feedback_category': getattr(r, 'feedback_category', '') or '',
                    'feedback_username': getattr(r, 'username', '') or '',
                    'feedback_date': (getattr(r, 'created_at') + timedelta(hours=5, minutes=30)).strftime('%Y-%m-%d %H:%M') if getattr(r, 'created_at', None) else '',
                }
                processed_rows.append(row_dict)
            
            processed_rows = get_hd_hierarchical_rows(processed_rows)
            pagination.total = len(processed_rows)
        else:
            for r in pagination.items:
                continue_data_formatted = ""
                cancel_data_formatted = ""
                has_action = False
                
                if getattr(r, 'continue_data', None):
                    has_action = True
                    try:
                        c_data = r.continue_data
                        # Handle new structure {schedules: [...], unselected_pos: [...]}
                        if isinstance(c_data, dict) and 'schedules' in c_data:
                            schedules = c_data['schedules']
                        else:
                            schedules = c_data if isinstance(c_data, list) else []

                        table_html = [
                            '<table class="w-full text-left text-[9px] text-gray-300">',
                            '<thead class="text-[8px] uppercase text-gray-500 border-b border-gray-700/50">',
                            '<tr><th class="pb-1 font-bold">Weight</th><th class="pb-1 font-bold text-right">Delivery Date</th></tr>',
                            '</thead><tbody class="divide-y divide-gray-800/50">'
                        ]
                        for d in schedules:
                            val = float(d.get('weight') or 0)
                            table_html.append(f'<tr><td class="py-1">{val:.3f} gms</td><td class="py-1 text-right">{d.get("delivery_date")}</td></tr>')
                        table_html.append('</tbody></table>')
                        
                        if isinstance(c_data, dict) and 'unselected_pos' in c_data:
                            unselected_count = len(c_data['unselected_pos'])
                            if unselected_count > 0:
                                table_html.append(f'<div class="mt-2 text-[8px] text-gray-400 uppercase font-black tracking-tighter border-t border-gray-700/50 pt-1">Unselected: {unselected_count} items</div>')
                        
                        continue_data_formatted = "".join(table_html)
                    except Exception:
                        pass

                if getattr(r, 'cancel_data', None):
                    has_action = True
                    try:
                        table_html = [
                            '<table class="w-full text-left text-[9px] text-gray-300">',
                            '<thead class="text-[8px] uppercase text-gray-500 border-b border-gray-700/50">',
                            '<tr><th class="pb-1 font-bold">PO Number</th><th class="pb-1 font-bold text-right">Weight</th></tr>',
                            '</thead><tbody class="divide-y divide-gray-800/50">'
                        ]
                        for d in r.cancel_data:
                            val = float(d.get('total_weight') or 0)
                            table_html.append(f'<tr><td class="py-1 font-bold">{d.get("po_number")}</td><td class="py-1 text-right">{val:.3f} gms</td></tr>')
                        table_html.append('</tbody></table>')
                        cancel_data_formatted = "".join(table_html)
                    except Exception:
                        pass

                row_dict = {
                    'id': f"{r.collection_owner}_{r.make_owner}_{r.supplier}_{r.collection}",
                    'collection_owner': r.collection_owner or '',
                    'make_owner': r.make_owner or '',
                    'supplier': r.supplier or '',
                    'collection': r.collection or '',
                    'branch_type': getattr(r, 'branch_type', ''),
                    'order_type': '', 
                    'order_request_type': '',
                    'order_wt': float(r.sum_order_wt or 0),
                    'accepted_wt': float(r.sum_accepted_wt or 0),
                    'pending_to_accepted_wt': float(r.sum_pending_to_accepted_wt or 0),
                    'pending_to_deliver_pcs': float(r.sum_pending_to_deliver_pcs or 0),
                    'pending_to_deliver_wt': float(r.sum_pending_to_deliver_wt or 0),
                    'not_barcoded_pcs': float(r.sum_not_barcoded_pcs or 0),
                    'not_barcoded_wt': float(r.sum_not_barcoded_wt or 0),
                    'feedback_text': r.feedback_text or '',
                    'feedback_category': r.feedback_category or '',
                    'feedback_username': r.username or '',
                    'feedback_date': (r.created_at + timedelta(hours=5, minutes=30)).strftime('%Y-%m-%d %H:%M') if r.created_at else '',
                    
                    'has_action': has_action,
                    'continue_reason': getattr(r, 'continue_reason', ''),
                    'continue_username': getattr(r, 'continue_username', ''),
                    'continue_date': (r.continue_created_at + timedelta(hours=5, minutes=30)).strftime('%Y-%m-%d %H:%M') if getattr(r, 'continue_created_at', None) else '',
                    'continue_data_formatted': continue_data_formatted,
                    
                    'cancel_reason': getattr(r, 'cancel_reason', ''),
                    'cancel_username': getattr(r, 'cancel_username', ''),
                    'cancel_date': (r.cancel_created_at + timedelta(hours=5, minutes=30)).strftime('%Y-%m-%d %H:%M') if getattr(r, 'cancel_created_at', None) else '',
                    'cancel_data_formatted': cancel_data_formatted
                }
                processed_rows.append(row_dict)
            
            if status_filter == 'pending_to_deliver_not_barcoded':
                processed_rows = get_hierarchical_rows(processed_rows)
                # Update pagination total to reflect tree rows
                pagination.total = len(processed_rows)
            
        cache_payload = {
            'rows': processed_rows,
            'total': pagination.total,
            'stats': stats
        }
        redis_client.setex(cache_key, 3600, json.dumps(cache_payload))
        
        template_name = 'partials/_view_pending_acceptance.html'
        if status_filter == 'pending_to_deliver':
            template_name = 'partials/_view_pending_acceptance_to_deliver.html'
        elif status_filter == 'pending_to_deliver_not_barcoded':
            template_name = 'partials/_view_pending_acceptance_not_barcoded.html'
        elif status_filter == 'hallmarking_delayed':
            template_name = 'partials/_view_hallmarking_delayed.html'

        return render_template(template_name, 
                             rows=processed_rows, 
                             pagination=pagination,
                             stats=stats,
                             status_filter=status_filter,
                             current_username=current_username)
                             
    except Exception as e:
        logger.error(f"Error in pending_acceptance_partial: {str(e)}")
        return f'<div class="p-8 text-center text-red-500 font-bold">Backend Error: {str(e)}</div>', 200

@dashboard_bp.route('/api/pending-acceptance-feedback/po-details')
@jwt_required()
def get_pending_acceptance_po_details():
    try:
        status_filter = request.args.get('status_filter', 'pending_to_accept')
        if status_filter == 'hallmarking_delayed':
            latest_date_query = db.session.query(func.max(HallmarkingDelayedSnapshot.snapshot_date)).scalar()
        else:
            latest_date_query = db.session.query(func.max(PendingAcceptanceSnapshot.snapshot_date)).scalar()
        
        collection_owner = request.args.get('collection_owner', '')
        make_owner = request.args.get('make_owner', '')
        supplier = request.args.get('supplier', '')
        collection = request.args.get('collection', '')
        classification = request.args.get('classification', '')
        
        # Apply global filters to match exactly what is in the main row
        search = request.args.get('search', '').strip()
        f_classification = request.args.get('classification', '')
        f_order_type = request.args.get('order_type', '')
        f_order_request_type = request.args.get('order_request_type', '')
        f_delay = request.args.get('delay')
        f_delay_enabled = request.args.get('delay_enabled', 'false') == 'true'
        if not f_delay_enabled:
            f_delay = None
            
        f_from_date = request.args.get('from_date')
        f_to_date = request.args.get('to_date')
        f_enable_date_filter = request.args.get('enable_date_filter') == 'true'

        
        query = db.session.query(
            PendingAcceptanceSnapshot.po_number,
            PendingAcceptanceSnapshot.po_date,
            PendingAcceptanceSnapshot.total_weight,
            PendingAcceptanceSnapshot.order_piece,
            PendingAcceptanceSnapshot.delivery_target_date,
            PendingAcceptanceSnapshot.supplier,
            func.sum(PendingAcceptanceSnapshot.order_wt).label('sum_order_wt'),
            func.sum(PendingAcceptanceSnapshot.accepted_wt).label('sum_accepted_wt'),
            func.sum(PendingAcceptanceSnapshot.pending_to_accepted_wt).label('sum_pending_to_accepted_wt'),
            func.sum(PendingAcceptanceSnapshot.pending_to_deliver_pcs).label('sum_pending_to_deliver_pcs'),
            func.sum(PendingAcceptanceSnapshot.pending_to_deliver_wt).label('sum_pending_to_deliver_wt'),
            func.sum(PendingAcceptanceSnapshot.not_barcoded_pcs).label('sum_not_barcoded_pcs'),
            func.sum(PendingAcceptanceSnapshot.not_barcoded_wt).label('sum_not_barcoded_wt')
        ).filter(
            PendingAcceptanceSnapshot.snapshot_date == latest_date_query,
            func.coalesce(PendingAcceptanceSnapshot.collection_owner, '') == collection_owner,
            func.coalesce(PendingAcceptanceSnapshot.make_owner, '') == make_owner,
            func.coalesce(PendingAcceptanceSnapshot.supplier, '') == supplier,
            func.coalesce(PendingAcceptanceSnapshot.collection, '') == collection
        )
        
        if search:
            query = query.filter(PendingAcceptanceSnapshot.supplier.ilike(f"%{search}%") | 
                                 PendingAcceptanceSnapshot.collection_owner.ilike(f"%{search}%") |
                                 PendingAcceptanceSnapshot.make_owner.ilike(f"%{search}%") |
                                 PendingAcceptanceSnapshot.collection.ilike(f"%{search}%"))
                                 
        if f_classification:
            query = query.filter(PendingAcceptanceSnapshot.classification == f_classification)
        
        if f_order_type:
            query = query.filter(PendingAcceptanceSnapshot.order_type == f_order_type)
        if f_order_request_type:
            query = query.filter(PendingAcceptanceSnapshot.order_request_type == f_order_request_type)
            
        if f_delay is not None:
            try:
                delay_val = int(f_delay)
                # (current_date - delivery_target_date) >= delay_val (Overdue)
                query = query.filter(func.current_date() - PendingAcceptanceSnapshot.delivery_target_date >= delay_val)
            except (ValueError, TypeError):
                pass
                
        if f_enable_date_filter and f_from_date and f_to_date:
            try:
                from datetime import datetime
                fd = datetime.strptime(f_from_date, '%Y-%m-%d').date()
                td = datetime.strptime(f_to_date, '%Y-%m-%d').date()
                query = query.filter(PendingAcceptanceSnapshot.order_date.between(fd, td))
            except ValueError:
                pass
                
        # Apply status filter
        if status_filter == 'pending_to_deliver':
            query = query.filter(PendingAcceptanceSnapshot.pending_to_deliver_pcs > 0)
        elif status_filter == 'pending_to_deliver_not_barcoded':
            query = query.filter(PendingAcceptanceSnapshot.not_barcoded_pcs > 0)
        else:
            query = query.filter(PendingAcceptanceSnapshot.pending_to_accepted_wt > 0)

        query = query.group_by(
            PendingAcceptanceSnapshot.po_number,
            PendingAcceptanceSnapshot.po_date,
            PendingAcceptanceSnapshot.total_weight,
            PendingAcceptanceSnapshot.order_piece,
            PendingAcceptanceSnapshot.delivery_target_date,
            PendingAcceptanceSnapshot.supplier
        )
        
        records = query.all()
        
        details = []
        status_filter = request.args.get('status_filter', 'pending_to_accept')
        totals = {
            'po_pieces': 0, 
            'po_weight': 0, 
            'order_wt': 0, 
            'accepted_wt': 0, 
            'pending_to_accepted_wt': 0,
            'pending_to_deliver_pcs': 0,
            'pending_to_deliver_wt': 0,
            'not_barcoded_pcs': 0,
            'not_barcoded_wt': 0
        }
        
        for r in records:
            po_w = float(r.total_weight or 0)
            po_p = float(r.order_piece or 0)
            o_w = float(r.sum_order_wt or 0)
            a_w = float(r.sum_accepted_wt or 0)
            p_a_w = float(r.sum_pending_to_accepted_wt or 0)
            p_d_p = float(r.sum_pending_to_deliver_pcs or 0)
            p_d_w = float(r.sum_pending_to_deliver_wt or 0)
            n_b_p = float(r.sum_not_barcoded_pcs or 0)
            n_b_w = float(r.sum_not_barcoded_wt or 0)
            
            totals['po_pieces'] += po_p
            totals['po_weight'] += po_w
            totals['order_wt'] += o_w
            totals['accepted_wt'] += a_w
            totals['pending_to_accepted_wt'] += p_a_w
            totals['pending_to_deliver_pcs'] += p_d_p
            totals['pending_to_deliver_wt'] += p_d_w
            totals['not_barcoded_pcs'] += n_b_p
            totals['not_barcoded_wt'] += n_b_w
            
            details.append({
                'po_number': r.po_number or 'N/A',
                'po_date': r.po_date.strftime('%Y-%m-%d') if r.po_date else '',
                'total_weight': po_w,
                'order_piece': po_p,
                'order_wt': o_w,
                'accepted_wt': a_w,
                'pending_to_accepted_wt': p_a_w,
                'pending_to_deliver_pcs': p_d_p,
                'pending_to_deliver_wt': p_d_w,
                'not_barcoded_pcs': n_b_p,
                'not_barcoded_wt': n_b_w,
                'delivery_target_date': r.delivery_target_date.strftime('%Y-%m-%d') if r.delivery_target_date else '',
                'vendor': r.supplier or 'N/A'
            })
            
        if request.headers.get('Accept') == 'application/json':
            existing_actions = {}
            try:
                actions = db.session.query(PendingAcceptanceAction).filter(
                    func.coalesce(PendingAcceptanceAction.collection_owner, '') == func.coalesce(collection_owner, ''),
                    func.coalesce(PendingAcceptanceAction.make_owner, '') == func.coalesce(make_owner, ''),
                    func.coalesce(PendingAcceptanceAction.supplier, '') == func.coalesce(supplier, ''),
                    func.coalesce(PendingAcceptanceAction.collection, '') == func.coalesce(collection, ''),
                    PendingAcceptanceAction.status_filter == status_filter
                ).order_by(PendingAcceptanceAction.created_at.desc()).all()
                for action in actions:
                    if action.action_type not in existing_actions:
                        existing_actions[action.action_type] = {
                            'action_type': action.action_type,
                            'reason': action.reason,
                            'action_data': action.action_data
                        }
            except Exception as ex:
                logger.error(f"Error fetching existing wizard action: {str(ex)}")

            return jsonify({'details': details, 'totals': totals, 'existing_actions': existing_actions})
            
        if status_filter == 'hallmarking_delayed':
            # Detailed records for HD
            f_office = request.args.get('office', '')
            f_hm_agent = request.args.get('hm_agent', '')
            
            q_hd = db.session.query(HallmarkingDelayedSnapshot).filter(
                HallmarkingDelayedSnapshot.snapshot_date == latest_date_query,
                func.coalesce(HallmarkingDelayedSnapshot.office, '') == f_office,
                func.coalesce(HallmarkingDelayedSnapshot.make_owner, '') == make_owner,
                func.coalesce(HallmarkingDelayedSnapshot.collection_owner, '') == collection_owner,
                func.coalesce(HallmarkingDelayedSnapshot.collection, '') == collection,
                func.coalesce(HallmarkingDelayedSnapshot.hm_agent, '') == f_hm_agent,
                func.coalesce(HallmarkingDelayedSnapshot.supplier, '') == supplier
            )
            records = q_hd.all()
            details = []
            totals = {'pieces': 0, 'weight': 0}
            for r in records:
                p = float(r.pieces or 0)
                w = float(r.weight or 0)
                totals['pieces'] += p
                totals['weight'] += w
                details.append({
                    'office': r.office,
                    'make_owner': r.make_owner,
                    'collection_owner': r.collection_owner,
                    'collection': r.collection,
                    'hm_agent': r.hm_agent,
                    'supplier': r.supplier,
                    'challan_date': r.challan_date.strftime('%Y-%m-%d') if r.challan_date else '',
                    'challan_no': r.challan_no,
                    'pieces': p,
                    'weight': w,
                    'receipt_date': r.receipt_date.strftime('%Y-%m-%d') if r.receipt_date else '',
                    'receipt_no': r.receipt_no
                })
            return render_template('partials/_view_hallmarking_delayed_details.html', details=details, totals=totals)

        return render_template('partials/_po_details_modal_generic.html', details=details, totals=totals, report_type='PA', status_filter=status_filter)
    except Exception as e:
        logger.error(f"Error in PO details load: {str(e)}")
        return f'<div class="p-8 text-center text-red-500 font-bold">Error loading PO Details: {str(e)}</div>', 200

@dashboard_bp.route('/api/pending-acceptance-feedback/feedback', methods=['POST'])
@jwt_required()
def save_pending_acceptance_feedback():
    try:
        data = request.json
        current_username = session.get('username', '').strip()
        
        collection_owner = data.get('collection_owner', '').strip()
        make_owner = data.get('make_owner')
        supplier = data.get('supplier')
        collection = data.get('collection')
        feedback_text = data.get('feedback_text', '').strip()
        feedback_category = data.get('feedback_category', '').strip()
        
        if not current_username:
            return jsonify({"status": "error", "message": "User session expired. Please login again."}), 401

        if not collection_owner or not feedback_text:
            return jsonify({"status": "error", "message": "Missing required fields"}), 400

        # Check: either the collector owner or the make owner can save feedback
        is_authorized = False
        allowed_owners = []
        if collection_owner:
            allowed_owners.append(collection_owner.strip().lower())
        if make_owner:
            allowed_owners.append(make_owner.strip().lower())
            
        if current_username.lower() in allowed_owners:
            is_authorized = True

        if not is_authorized:
            owners_str = " or ".join(filter(None, [collection_owner, make_owner]))
            return jsonify({
                "status": "error", 
                "message": f"Unauthorized. Only {owners_str} can save feedback for this record."
            }), 403
            
        status_f = data.get('status_filter', 'pending_to_accept')
        p_code = 'PA'
        office = data.get('office')
        hm_agent = data.get('hm_agent')
        
        if status_f == 'pending_to_deliver':
            p_code = 'PD'
        elif status_f == 'pending_to_deliver_not_barcoded':
            p_code = 'PNB'
        elif status_f == 'hallmarking_delayed':
            p_code = 'HD'
        
        current_username = session.get('username')
        
        if p_code == 'HD':
            feedback = HallmarkingDelayedFeedback.query.filter(
                func.coalesce(HallmarkingDelayedFeedback.collection_owner, '') == func.coalesce(collection_owner, ''),
                func.coalesce(HallmarkingDelayedFeedback.make_owner, '') == func.coalesce(make_owner, ''),
                func.coalesce(HallmarkingDelayedFeedback.supplier, '') == func.coalesce(supplier, ''),
                func.coalesce(HallmarkingDelayedFeedback.collection, '') == func.coalesce(collection, ''),
                func.coalesce(HallmarkingDelayedFeedback.office, '') == func.coalesce(office, ''),
                func.coalesce(HallmarkingDelayedFeedback.hm_agent, '') == func.coalesce(hm_agent, '')
            ).first()
            
            if feedback:
                feedback.feedback_text = feedback_text
                feedback.feedback_category = feedback_category
                feedback.username = current_username
                feedback.created_at = datetime.utcnow()
            else:
                feedback = HallmarkingDelayedFeedback(
                    collection_owner=collection_owner,
                    make_owner=make_owner,
                    supplier=supplier,
                    collection=collection,
                    office=office,
                    hm_agent=hm_agent,
                    feedback_text=feedback_text,
                    feedback_category=feedback_category,
                    username=current_username
                )
                db.session.add(feedback)
        else:
            feedback = ReportFeedback.query.filter(
                func.coalesce(ReportFeedback.collection_owner, '') == func.coalesce(collection_owner, ''),
                func.coalesce(ReportFeedback.make_owner, '') == func.coalesce(make_owner, ''),
                func.coalesce(ReportFeedback.supplier, '') == func.coalesce(supplier, ''),
                func.coalesce(ReportFeedback.collection, '') == func.coalesce(collection, ''),
                ReportFeedback.page_code == p_code
            ).first()
            
            if feedback:
                feedback.feedback_text = feedback_text
                feedback.feedback_category = feedback_category
                feedback.username = current_username
                feedback.created_at = datetime.utcnow()
                feedback.office = office
                feedback.hm_agent = hm_agent
            else:
                feedback = ReportFeedback(
                    collection_owner=collection_owner,
                    make_owner=make_owner,
                    supplier=supplier,
                    collection=collection,
                    office=office,
                    hm_agent=hm_agent,
                    feedback_text=feedback_text,
                    feedback_category=feedback_category,
                    username=current_username,
                    page_code=p_code
                )
                db.session.add(feedback)
        
        db.session.add(feedback)
        db.session.commit()
        
        # Clear cache for this route
        try:
            for key in redis_client.scan_iter("pending_acc_*"):
                redis_client.delete(key)
        except Exception as e:
            logger.error(f"Error clearing cache: {str(e)}")
            
        return jsonify({"status": "success", "message": "Feedback saved successfully"})
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error saving feedback: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@dashboard_bp.route('/api/pending-acceptance-feedback/wizard-action', methods=['POST'])
@jwt_required()
def save_pending_acceptance_wizard_action():
    try:
        data = request.json
        current_username = session.get('username', '').strip()
        
        collection_owner = data.get('collection_owner', '').strip()
        make_owner = data.get('make_owner')
        supplier = data.get('supplier')
        collection = data.get('collection')
        status_filter = data.get('status_filter')
        action_type = data.get('action_type')
        reason = data.get('reason')
        action_data = data.get('action_data')
        
        if not current_username:
            return jsonify({"status": "error", "message": "User session expired. Please login again."}), 401

        if not collection_owner or not action_type:
            return jsonify({"status": "error", "message": "Missing required fields"}), 400

        # Check: either the collector owner or the make owner can save feedback
        is_authorized = False
        allowed_owners = []
        if collection_owner:
            allowed_owners.append(collection_owner.strip().lower())
        if make_owner:
            allowed_owners.append(make_owner.strip().lower())
            
        if current_username.lower() in allowed_owners:
            is_authorized = True

        if not is_authorized:
            owners_str = " or ".join(filter(None, [collection_owner, make_owner]))
            return jsonify({
                "status": "error", 
                "message": f"Unauthorized. Only {owners_str} can perform this action."
            }), 403
            
        existing_action = PendingAcceptanceAction.query.filter(
            func.coalesce(PendingAcceptanceAction.collection_owner, '') == func.coalesce(collection_owner, ''),
            func.coalesce(PendingAcceptanceAction.make_owner, '') == func.coalesce(make_owner, ''),
            func.coalesce(PendingAcceptanceAction.supplier, '') == func.coalesce(supplier, ''),
            func.coalesce(PendingAcceptanceAction.collection, '') == func.coalesce(collection, ''),
            PendingAcceptanceAction.status_filter == status_filter,
            PendingAcceptanceAction.action_type == action_type
        ).first()

        if existing_action:
            return jsonify({"status": "error", "message": f"{action_type} action already exists and cannot be modified."}), 400
            
        new_action = PendingAcceptanceAction(
            collection_owner=collection_owner,
            make_owner=make_owner,
            supplier=supplier,
            collection=collection,
            status_filter=status_filter,
            action_type=action_type,
            reason=reason,
            action_data=action_data,
            username=current_username,
            created_at=datetime.utcnow()
        )
        db.session.add(new_action)
        db.session.commit()
        
        # Clear cache for this route
        try:
            for key in redis_client.scan_iter("pending_acc_*"):
                redis_client.delete(key)
        except Exception as e:
            logger.error(f"Error clearing cache: {str(e)}")
            
        return jsonify({"status": "success", "message": "Fulfillment action saved successfully"})
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error saving wizard action: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@dashboard_bp.route('/api/pending-acceptance-feedback/export', methods=['POST'])
@jwt_required()
@require_perm('report.export')
def queue_pending_acceptance_export():
    """Enqueue a background Excel export job for the pending acceptance report."""
    try:
        data = request.get_json(force=True) or {}
        filters = data.get('filters', {})
        socket_id = data.get('socket_id')
        user_id = get_jwt_identity()

        job_payload = json.dumps({
            'type': 'export_pending_acceptance',
            'filters': filters,
            'socket_id': socket_id,
            'user_id': user_id
        })
        redis_client.rpush('export_queue', job_payload)

        logger.info(f"Queued export_pending_acceptance job with filters: {filters}")
        return jsonify({
            'status': 'queued',
            'message': 'Export job enqueued. You will be notified when the file is ready.'
        }), 202
    except Exception as e:
        logger.error(f"Error queuing pending acceptance export: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500
