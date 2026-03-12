from flask import render_template, request, jsonify, session
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.dashboard import dashboard_bp
from app.models.snapshots import PendingAcceptanceSnapshot, PendingAcceptanceFeedback
from app.models.auth import User
from app.extensions import db, redis_client
from sqlalchemy import func, case
from datetime import datetime, timedelta
import logging
import json

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

def get_latest_feedback_subquery():
    # Subquery for latest feedback
    subq = db.session.query(
        PendingAcceptanceFeedback.collection_owner,
        PendingAcceptanceFeedback.make_owner,
        PendingAcceptanceFeedback.supplier,
        PendingAcceptanceFeedback.collection,
        func.max(PendingAcceptanceFeedback.created_at).label('max_date')
    ).filter(PendingAcceptanceFeedback.page_code == 'PA').group_by(
        PendingAcceptanceFeedback.collection_owner,
        PendingAcceptanceFeedback.make_owner,
        PendingAcceptanceFeedback.supplier,
        PendingAcceptanceFeedback.collection
    ).subquery()
    
    return db.session.query(PendingAcceptanceFeedback).join(
        subq,
        db.and_(
            func.coalesce(PendingAcceptanceFeedback.collection_owner, '') == func.coalesce(subq.c.collection_owner, ''),
            func.coalesce(PendingAcceptanceFeedback.make_owner, '') == func.coalesce(subq.c.make_owner, ''),
            func.coalesce(PendingAcceptanceFeedback.supplier, '') == func.coalesce(subq.c.supplier, ''),
            func.coalesce(PendingAcceptanceFeedback.collection, '') == func.coalesce(subq.c.collection, ''),
            PendingAcceptanceFeedback.created_at == subq.c.max_date
        )
    ).filter(PendingAcceptanceFeedback.page_code == 'PA').subquery()

def apply_filters(query, search, latest_date_query, collection_owner=None, make_owner=None, 
                supplier=None, collection=None, classification=None, feedback_status=None,
                order_type=None, order_request_type=None, delay=None):
    # Enforce latest snapshot date
    query = query.filter(PendingAcceptanceSnapshot.snapshot_date == latest_date_query)

    if delay is not None:
        try:
            delay_val = int(delay)
            # Safer comparison: order_date <= current_date - delay_days
            # This ensures items are at least N days old
            query = query.filter(PendingAcceptanceSnapshot.order_date <= func.current_date() - delay_val)
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
        
    return query

def get_base_query(query_filter_func=None, feedback_status=None):
    latest_feedback = get_latest_feedback_subquery()
    
    # Base query for aggregation
    q = db.session.query(
        PendingAcceptanceSnapshot.collection_owner,
        PendingAcceptanceSnapshot.make_owner,
        PendingAcceptanceSnapshot.supplier,
        PendingAcceptanceSnapshot.collection,
        PendingAcceptanceSnapshot.classification,
        func.sum(PendingAcceptanceSnapshot.order_wt).label('sum_order_wt'),
        func.sum(PendingAcceptanceSnapshot.accepted_wt).label('sum_accepted_wt'),
        func.sum(PendingAcceptanceSnapshot.pending_to_accepted_wt).label('sum_pending_to_accepted_wt')
    )
    
    if query_filter_func:
        q = query_filter_func(q)
        
    q = q.group_by(
        PendingAcceptanceSnapshot.collection_owner,
        PendingAcceptanceSnapshot.make_owner,
        PendingAcceptanceSnapshot.supplier,
        PendingAcceptanceSnapshot.collection,
        PendingAcceptanceSnapshot.classification
    ).subquery('agg_snapshot')

    # Join with feedback
    query = db.session.query(
        q.c.collection_owner,
        q.c.make_owner,
        q.c.supplier,
        q.c.collection,
        q.c.classification,
        q.c.sum_order_wt,
        q.c.sum_accepted_wt,
        q.c.sum_pending_to_accepted_wt,
        latest_feedback.c.feedback_text,
        latest_feedback.c.feedback_category,
        latest_feedback.c.username,
        latest_feedback.c.created_at
    ).outerjoin(
        latest_feedback,
        db.and_(
            func.coalesce(q.c.collection_owner, '') == func.coalesce(latest_feedback.c.collection_owner, ''),
            func.coalesce(q.c.make_owner, '') == func.coalesce(latest_feedback.c.make_owner, ''),
            func.coalesce(q.c.supplier, '') == func.coalesce(latest_feedback.c.supplier, ''),
            func.coalesce(q.c.collection, '') == func.coalesce(latest_feedback.c.collection, ''),
            func.coalesce(q.c.classification, '') == func.coalesce(latest_feedback.c.classification, '')
        )
    )

    if feedback_status:
        if feedback_status == 'with':
            query = query.filter(latest_feedback.c.feedback_text != None)
        elif feedback_status == 'without':
            query = query.filter(latest_feedback.c.feedback_text == None)
            
    query = query.order_by(q.c.sum_accepted_wt.desc(), q.c.sum_pending_to_accepted_wt.desc())
    return query

def calculate_stats(query):
    try:
        s = query.order_by(None).subquery()
        res = db.session.query(
            func.sum(s.c.sum_order_wt),
            func.sum(s.c.sum_accepted_wt),
            func.sum(s.c.sum_pending_to_accepted_wt),
            func.count(case((s.c.feedback_text != None, 1))),
            func.count(case((s.c.feedback_text == None, 1)))
        ).first()
        
        return {
            'total_order_wt': float(res[0] or 0),
            'total_accepted_wt': float(res[1] or 0),
            'total_pending_wt': float(res[2] or 0),
            'with_feedback': int(res[3] or 0),
            'without_feedback': int(res[4] or 0)
        }
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error calculating stats: {str(e)}")
        return {
            'total_order_wt': 0,
            'total_pending_wt': 0,
            'with_feedback': 0,
            'without_feedback': 0
        }

@dashboard_bp.route('/pending-acceptance-feedback')
@jwt_required()
def pending_acceptance():
    try:
        from app.models.core import Notification
        unread_count = Notification.query.filter_by(is_read=False).count()
        sync_time = datetime.now().strftime("%H:%M")

        has_any_data = db.session.query(PendingAcceptanceSnapshot.id).first()
        if not has_any_data:
            return render_template('pending_acceptance.html', 
                                 unread_count=unread_count, 
                                 sync_time=sync_time, 
                                 rows=[], 
                                 pagination=None,
                                 current_username='',
                                 filters={})

        latest_date_query = db.session.query(func.max(PendingAcceptanceSnapshot.snapshot_date)).scalar()
        
        search = request.args.get('search', '').strip()
        f_collection_owner = request.args.get('collection_owner', '')
        f_make_owner = request.args.get('make_owner', '')
        f_supplier = request.args.get('supplier', '')
        f_collection = request.args.get('collection', '')
        f_order_type = request.args.get('order_type', '')
        f_order_request_type = request.args.get('order_request_type', '')
        f_classification = request.args.get('classification', '')
        f_feedback_status = request.args.get('feedback_status', '')
        f_delay = request.args.get('delay')
        
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)
        # 1. Role-based bypass logic
        roles = [r.upper() for r in session.get('roles', [])]
        is_manager_2 = 'MANAGER_2' in roles
        is_admin = session.get('is_admin', False)
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
                                     delay=f_delay,
                                     page=page, per_page=per_page)
        
        # 3. Helper to fetch filter lists
        def fetch_filter_options():
            base_q = db.session.query(PendingAcceptanceSnapshot).filter(
                PendingAcceptanceSnapshot.snapshot_date == latest_date_query
            )
            if restrict_to_user:
                u = current_username.lower()
                base_q = base_q.filter(func.lower(func.trim(PendingAcceptanceSnapshot.collection_owner)) == u)

            return {
                'collection_owners': [current_username] if restrict_to_user else [r[0] for r in base_q.with_entities(PendingAcceptanceSnapshot.collection_owner).distinct().order_by(PendingAcceptanceSnapshot.collection_owner).all()],
                'make_owners': [r[0] for r in base_q.with_entities(PendingAcceptanceSnapshot.make_owner).distinct().order_by(PendingAcceptanceSnapshot.make_owner).all()],
                'suppliers': [r[0] for r in base_q.with_entities(PendingAcceptanceSnapshot.supplier).distinct().order_by(PendingAcceptanceSnapshot.supplier).all()],
                'collections': [r[0] for r in base_q.with_entities(PendingAcceptanceSnapshot.collection).distinct().order_by(PendingAcceptanceSnapshot.collection).all()],
                'classifications': [r[0] for r in base_q.with_entities(PendingAcceptanceSnapshot.classification).distinct().order_by(PendingAcceptanceSnapshot.classification).all()],
                'order_types': [r[0] for r in base_q.with_entities(PendingAcceptanceSnapshot.order_type).distinct().order_by(PendingAcceptanceSnapshot.order_type).all()],
                'order_request_types': [r[0] for r in base_q.with_entities(PendingAcceptanceSnapshot.order_request_type).distinct().order_by(PendingAcceptanceSnapshot.order_request_type).all()],
            }

        filter_options = fetch_filter_options()

        return render_template('pending_acceptance.html', 
                             unread_count=unread_count, 
                             sync_time=sync_time, 
                             stats=None,
                             current_username=current_username,
                             filter_options=filter_options,
                             initial_load=True)
                             
    except Exception as e:
        logger.error(f"Error in pending_acceptance: {str(e)}")
        return f"Error: {str(e)}", 500

@dashboard_bp.route('/partial/pending-acceptance-feedback')
@jwt_required()
def get_pending_acceptance_partial():
    try:
        latest_date_query = db.session.query(func.max(PendingAcceptanceSnapshot.snapshot_date)).scalar()
        
        search = request.args.get('search', '').strip()
        f_collection_owner = request.args.get('collection_owner', '')
        f_make_owner = request.args.get('make_owner', '')
        f_supplier = request.args.get('supplier', '')
        f_collection = request.args.get('collection', '')
        f_classification = request.args.get('classification', '')
        f_order_type = request.args.get('order_type', '')
        f_order_request_type = request.args.get('order_request_type', '')
        f_feedback_status = request.args.get('feedback_status', '')
        f_delay = request.args.get('delay')
        
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)
        
        # 1. Role-based bypass logic
        roles = [r.upper() for r in session.get('roles', [])]
        is_manager_2 = 'MANAGER_2' in roles
        is_admin = session.get('is_admin', False)
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
                                     delay=f_delay,
                                     page=page, per_page=per_page)
        
        cached_data = redis_client.get(cache_key)
        if cached_data:
            data = json.loads(cached_data)
            pagination = CachedPagination(data['rows'], page, per_page, data['total'])
            return render_template('partials/_view_pending_acceptance.html', 
                                 rows=data['rows'], 
                                 pagination=pagination,
                                 stats=data.get('stats', {}),
                                 current_username=current_username)

        # 3. Filter function to apply to base snapshot query before aggregation
        def filter_func(q):
            if restrict_to_user:
                u = current_username.lower()
                q = q.filter((func.lower(func.trim(PendingAcceptanceSnapshot.collection_owner)) == u) | 
                             (func.lower(func.trim(PendingAcceptanceSnapshot.make_owner)) == u))
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
                delay=f_delay
            )

        query = get_base_query(query_filter_func=filter_func, feedback_status=f_feedback_status)
        
        # Calculate Stats (now passing the formulated query)
        stats = calculate_stats(query)
        
        

        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        
        processed_rows = []
        for r in pagination.items:
            row_dict = {
                'id': f"{r.collection_owner}_{r.make_owner}_{r.supplier}_{r.collection}",
                'collection_owner': r.collection_owner or '',
                'make_owner': r.make_owner or '',
                'supplier': r.supplier or '',
                'collection': r.collection or '',
                'classification': r.classification or '',
                'order_type': '', 
                'order_request_type': '',
                'order_wt': float(r.sum_order_wt or 0),
                'accepted_wt': float(r.sum_accepted_wt or 0),
                'pending_to_accepted_wt': float(r.sum_pending_to_accepted_wt or 0),
                'feedback_text': r.feedback_text or '',
                'feedback_category': r.feedback_category or '',
                'feedback_username': r.username or '',
                'feedback_date': (r.created_at + timedelta(hours=5, minutes=30)).strftime('%Y-%m-%d %H:%M') if r.created_at else ''
            }
            processed_rows.append(row_dict)
            
        cache_payload = {
            'rows': processed_rows,
            'total': pagination.total,
            'stats': stats
        }
        redis_client.setex(cache_key, 3600, json.dumps(cache_payload))
        
        return render_template('partials/_view_pending_acceptance.html', 
                             rows=processed_rows, 
                             pagination=pagination,
                             stats=stats,
                             current_username=current_username)
                             
    except Exception as e:
        logger.error(f"Error in pending_acceptance_partial: {str(e)}")
        return f'<div class="p-8 text-center text-red-500 font-bold">Backend Error: {str(e)}</div>', 200

@dashboard_bp.route('/api/pending-acceptance-feedback/po-details')
@jwt_required()
def get_pending_acceptance_po_details():
    try:
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
        
        query = db.session.query(
            PendingAcceptanceSnapshot.po_number,
            PendingAcceptanceSnapshot.po_date,
            PendingAcceptanceSnapshot.total_weight,
            PendingAcceptanceSnapshot.order_piece,
            func.sum(PendingAcceptanceSnapshot.order_wt).label('sum_order_wt'),
            func.sum(PendingAcceptanceSnapshot.accepted_wt).label('sum_accepted_wt'),
            func.sum(PendingAcceptanceSnapshot.pending_to_accepted_wt).label('sum_pending_to_accepted_wt')
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
        
        if f_order_type:
            query = query.filter(PendingAcceptanceSnapshot.order_type == f_order_type)
        if f_order_request_type:
            query = query.filter(PendingAcceptanceSnapshot.order_request_type == f_order_request_type)
            
        if f_delay is not None:
            try:
                delay_val = int(f_delay)
                query = query.filter(PendingAcceptanceSnapshot.order_date <= func.current_date() - delay_val)
            except (ValueError, TypeError):
                pass
                
        query = query.group_by(
            PendingAcceptanceSnapshot.po_number,
            PendingAcceptanceSnapshot.po_date,
            PendingAcceptanceSnapshot.total_weight,
            PendingAcceptanceSnapshot.order_piece
        )
        
        records = query.all()
        
        details = []
        totals = {'po_pieces': 0, 'po_weight': 0, 'order_wt': 0, 'accepted_wt': 0, 'pending_to_accepted_wt': 0}
        
        for r in records:
            po_w = float(r.total_weight or 0)
            po_p = float(r.order_piece or 0)
            o_w = float(r.sum_order_wt or 0)
            a_w = float(r.sum_accepted_wt or 0)
            p_a_w = float(r.sum_pending_to_accepted_wt or 0)
            
            totals['po_pieces'] += po_p
            totals['po_weight'] += po_w
            totals['order_wt'] += o_w
            totals['accepted_wt'] += a_w
            totals['pending_to_accepted_wt'] += p_a_w
            
            details.append({
                'po_number': r.po_number or 'N/A',
                'po_date': r.po_date.strftime('%Y-%m-%d') if r.po_date else '',
                'total_weight': po_w,
                'order_piece': po_p,
                'order_wt': o_w,
                'accepted_wt': a_w,
                'pending_to_accepted_wt': p_a_w
            })
            
        return render_template('partials/_po_details_modal.html', details=details, totals=totals)
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
            
        new_feedback = PendingAcceptanceFeedback(
            collection_owner=collection_owner,
            make_owner=make_owner,
            supplier=supplier,
            collection=collection,
            feedback_text=feedback_text,
            feedback_category=feedback_category,
            username=current_username,
            page_code='PA',
            created_at=datetime.utcnow()
        )
        db.session.add(new_feedback)
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
