from flask import render_template, request, jsonify, session
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.dashboard import dashboard_bp
from app.models.snapshots import PendingAcceptanceSnapshot, PendingAcceptanceFeedback
from app.models.auth import User
from app.extensions import db, redis_client
from sqlalchemy import func
from datetime import datetime
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
    ).group_by(
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
    ).subquery()

def apply_filters(query, search, latest_date_query, collection_owner=None, make_owner=None, supplier=None, collection=None, feedback_status=None):
    if latest_date_query:
        query = query.filter(PendingAcceptanceSnapshot.snapshot_date == latest_date_query)
        
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
        
    if feedback_status:
        has_feedback = db.session.query(PendingAcceptanceFeedback.id).filter(
            func.coalesce(PendingAcceptanceFeedback.collection_owner, '') == func.coalesce(PendingAcceptanceSnapshot.collection_owner, ''),
            func.coalesce(PendingAcceptanceFeedback.make_owner, '') == func.coalesce(PendingAcceptanceSnapshot.make_owner, ''),
            func.coalesce(PendingAcceptanceFeedback.supplier, '') == func.coalesce(PendingAcceptanceSnapshot.supplier, ''),
            func.coalesce(PendingAcceptanceFeedback.collection, '') == func.coalesce(PendingAcceptanceSnapshot.collection, '')
        ).exists()
        
        if feedback_status == 'with':
            query = query.filter(has_feedback)
        elif feedback_status == 'without':
            query = query.filter(~has_feedback)
            
    return query

def get_base_query():
    latest_feedback = get_latest_feedback_subquery()
    
    query = db.session.query(
        PendingAcceptanceSnapshot,
        latest_feedback.c.feedback_text,
        latest_feedback.c.username,
        latest_feedback.c.created_at
    ).outerjoin(
        latest_feedback,
        db.and_(
            func.coalesce(PendingAcceptanceSnapshot.collection_owner, '') == func.coalesce(latest_feedback.c.collection_owner, ''),
            func.coalesce(PendingAcceptanceSnapshot.make_owner, '') == func.coalesce(latest_feedback.c.make_owner, ''),
            func.coalesce(PendingAcceptanceSnapshot.supplier, '') == func.coalesce(latest_feedback.c.supplier, ''),
            func.coalesce(PendingAcceptanceSnapshot.collection, '') == func.coalesce(latest_feedback.c.collection, '')
        )
    )
    return query

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
        f_feedback_status = request.args.get('feedback_status', '')
        
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
                                     collection=f_collection, page=page, per_page=per_page)
        
        # 3. Helper to fetch filter lists
        def fetch_filter_options():
            base_q = db.session.query(PendingAcceptanceSnapshot).filter(
                PendingAcceptanceSnapshot.snapshot_date == latest_date_query
            )
            if restrict_to_user:
                u = current_username.lower()
                base_q = base_q.filter(func.lower(func.trim(PendingAcceptanceSnapshot.collection_owner)) == u)

            return {
                'collection_owners': [current_username] if restrict_to_user else [r[0] for r in base_q.with_entities(PendingAcceptanceSnapshot.collection_owner).distinct().order_by(PendingAcceptanceSnapshot.collection_owner).all() if r[0]],
                'make_owners': [r[0] for r in base_q.with_entities(PendingAcceptanceSnapshot.make_owner).distinct().order_by(PendingAcceptanceSnapshot.make_owner).all() if r[0]],
                'suppliers': [r[0] for r in base_q.with_entities(PendingAcceptanceSnapshot.supplier).distinct().order_by(PendingAcceptanceSnapshot.supplier).all() if r[0]],
                'collections': [r[0] for r in base_q.with_entities(PendingAcceptanceSnapshot.collection).distinct().order_by(PendingAcceptanceSnapshot.collection).all() if r[0]],
            }

        filter_options = fetch_filter_options()

        cached_data = redis_client.get(cache_key)
        if cached_data:
            data = json.loads(cached_data)
            pagination = CachedPagination(data['rows'], page, per_page, data['total'])
            return render_template('pending_acceptance.html', 
                                 unread_count=unread_count, 
                                 sync_time=sync_time, 
                                 rows=data['rows'], 
                                 pagination=pagination,
                                 current_username=current_username,
                                 filter_options=filter_options)

        query = get_base_query()
        
        # 4. Enforce user restrictions if not admin/manager
        if restrict_to_user:
            u = current_username.lower()
            query = query.filter(func.lower(func.trim(PendingAcceptanceSnapshot.collection_owner)) == u)
        elif not is_admin and not is_manager_2 and not current_username:
            # Fallback for unexpected session state
            query = query.filter(False)
        
        query = apply_filters(query, search, latest_date_query, 
                            collection_owner=f_collection_owner, make_owner=f_make_owner,
                            supplier=f_supplier, collection=f_collection,
                            feedback_status=f_feedback_status)
        query = query.order_by(PendingAcceptanceSnapshot.pending_to_accepted_wt.desc())
        
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        
        processed_rows = []
        for r in pagination.items:
            snap = r[0]
            fb_text = r[1]
            fb_user = r[2]
            fb_date = r[3]
            
            row_dict = {
                'id': snap.id,
                'collection_owner': snap.collection_owner or '',
                'make_owner': snap.make_owner or '',
                'supplier': snap.supplier or '',
                'collection': snap.collection or '',
                'order_wt': float(snap.order_wt or 0),
                'pending_to_accepted_wt': float(snap.pending_to_accepted_wt or 0),
                'feedback_text': fb_text or '',
                'feedback_username': fb_user or '',
                'feedback_date': fb_date.strftime('%Y-%m-%d %H:%M') if fb_date else ''
            }
            processed_rows.append(row_dict)
            
        cache_payload = {
            'rows': processed_rows,
            'total': pagination.total
        }
        redis_client.setex(cache_key, 3600, json.dumps(cache_payload))
        
        return render_template('pending_acceptance.html', 
                             unread_count=unread_count, 
                             sync_time=sync_time, 
                             rows=processed_rows, 
                             pagination=pagination,
                             current_username=current_username,
                             filter_options=filter_options)
                             
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
        f_feedback_status = request.args.get('feedback_status', '')
        
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)
        
        # 1. Role-based bypass logic
        roles = [r.upper() for r in session.get('roles', [])]
        is_manager_2 = 'MANAGER_2' in roles
        is_admin = session.get('is_admin', False)
        current_username = session.get('username', '').strip()
        
        restrict_to_user = not is_admin and not is_manager_2 and current_username
        
        # 2. Update cache key to be user/role specific
        cache_key = generate_cache_key('pending_acc_partial', latest_date_query, 
                                     username=current_username if restrict_to_user else 'admin',
                                     search=search, feedback_status=f_feedback_status,
                                     collection_owner=f_collection_owner,
                                     make_owner=f_make_owner, supplier=f_supplier, 
                                     collection=f_collection, page=page, per_page=per_page)
        
        cached_data = redis_client.get(cache_key)
        if cached_data:
            data = json.loads(cached_data)
            pagination = CachedPagination(data['rows'], page, per_page, data['total'])
            return render_template('partials/_view_pending_acceptance.html', 
                             rows=data['rows'], 
                             pagination=pagination,
                             current_username=current_username)

        query = get_base_query()
        # 3. Enforce user restrictions if not admin/manager
        if restrict_to_user:
            u = current_username.lower()
            query = query.filter(func.lower(func.trim(PendingAcceptanceSnapshot.collection_owner)) == u)
        elif not is_admin and not is_manager_2 and not current_username:
            query = query.filter(False)
        
        query = apply_filters(query, search, latest_date_query,
                            collection_owner=f_collection_owner, make_owner=f_make_owner,
                            supplier=f_supplier, collection=f_collection,
                            feedback_status=f_feedback_status)
        query = query.order_by(PendingAcceptanceSnapshot.pending_to_accepted_wt.desc())
        
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        
        processed_rows = []
        for r in pagination.items:
            snap = r[0]
            fb_text = r[1]
            fb_user = r[2]
            fb_date = r[3]
            
            row_dict = {
                'id': snap.id,
                'collection_owner': snap.collection_owner or '',
                'make_owner': snap.make_owner or '',
                'supplier': snap.supplier or '',
                'collection': snap.collection or '',
                'order_wt': float(snap.order_wt or 0),
                'pending_to_accepted_wt': float(snap.pending_to_accepted_wt or 0),
                'feedback_text': fb_text or '',
                'feedback_username': fb_user or '',
                'feedback_date': fb_date.strftime('%Y-%m-%d %H:%M') if fb_date else ''
            }
            processed_rows.append(row_dict)
            
        cache_payload = {
            'rows': processed_rows,
            'total': pagination.total
        }
        redis_client.setex(cache_key, 3600, json.dumps(cache_payload))
        
        return render_template('partials/_view_pending_acceptance.html', 
                             rows=processed_rows, 
                             pagination=pagination,
                             current_username=current_username)
                             
    except Exception as e:
        logger.error(f"Error in pending_acceptance_partial: {str(e)}")
        return f'<div class="p-8 text-center text-red-500 font-bold">Backend Error: {str(e)}</div>', 200

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
        
        if not current_username:
            return jsonify({"status": "error", "message": "User session expired. Please login again."}), 401

        if not collection_owner or not feedback_text:
            return jsonify({"status": "error", "message": "Missing required fields"}), 400

        # Check: only the collector owner can save feedback
        if current_username.lower() != collection_owner.lower():
            return jsonify({
                "status": "error", 
                "message": f"Unauthorized. Only {collection_owner} can save feedback for this record."
            }), 403
            
        new_feedback = PendingAcceptanceFeedback(
            collection_owner=collection_owner,
            make_owner=make_owner,
            supplier=supplier,
            collection=collection,
            feedback_text=feedback_text,
            username=current_username,
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
