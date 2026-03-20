from flask import render_template, request, jsonify, session
from flask_jwt_extended import jwt_required
from app.dashboard import dashboard_bp
from app.models import Notification, ShowroomWiseOrderSummarySnapshot
from app.extensions import db
from sqlalchemy import func, cast, Numeric
from datetime import datetime
from zoneinfo import ZoneInfo
import logging
import json
from app.extensions import redis_client
from app.utils.sync_manager import sync_showroom_wise_order_summary_data

logger = logging.getLogger(__name__)

# Helper class to mimic Flask-SQLAlchemy Pagination for templates
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

def safe_float(val):
    try:
        return float(val or 0)
    except:
        return 0.0

def get_showroom_aggs(latest_date_query, search=None, business_head=None, classification_owner=None, 
                    make_owner=None, collection_owner=None, party=None, location=None, 
                    purchase_ro=None, order_type=None, order_request_type=None, 
                    division=None, group_name=None, purity=None, classification=None,
                    make=None, collection=None):
    
    def apply_filters(query):
        if search:
            query = query.filter(ShowroomWiseOrderSummarySnapshot.business_head.ilike(f"%{search}%") | 
                                 ShowroomWiseOrderSummarySnapshot.party.ilike(f"%{search}%") |
                                 ShowroomWiseOrderSummarySnapshot.location.ilike(f"%{search}%"))
        if business_head: query = query.filter(ShowroomWiseOrderSummarySnapshot.business_head == business_head)
        if classification_owner: query = query.filter(ShowroomWiseOrderSummarySnapshot.classification_owner == classification_owner)
        if make_owner: query = query.filter(ShowroomWiseOrderSummarySnapshot.make_owner == make_owner)
        if collection_owner: query = query.filter(ShowroomWiseOrderSummarySnapshot.collection_owner == collection_owner)
        if party: query = query.filter(ShowroomWiseOrderSummarySnapshot.party == party)
        if location: query = query.filter(ShowroomWiseOrderSummarySnapshot.location == location)
        if purchase_ro: query = query.filter(ShowroomWiseOrderSummarySnapshot.purchase_ro == purchase_ro)
        if order_type: query = query.filter(ShowroomWiseOrderSummarySnapshot.order_type == order_type)
        if order_request_type: query = query.filter(ShowroomWiseOrderSummarySnapshot.order_request_type == order_request_type)
        if division: query = query.filter(ShowroomWiseOrderSummarySnapshot.division == division)
        if group_name: query = query.filter(ShowroomWiseOrderSummarySnapshot.group_name == group_name)
        if purity: query = query.filter(ShowroomWiseOrderSummarySnapshot.purity == purity)
        if classification: query = query.filter(ShowroomWiseOrderSummarySnapshot.classification == classification)
        if make: query = query.filter(ShowroomWiseOrderSummarySnapshot.make == make)
        if collection: query = query.filter(ShowroomWiseOrderSummarySnapshot.collection == collection)
        
        if latest_date_query:
            query = query.filter(ShowroomWiseOrderSummarySnapshot.snapshot_date == latest_date_query)

        # User-based filtering: Restrict to any owner = username if not admin or MANAGER_2
        is_admin = session.get('is_admin', False)
        username = session.get('username')
        roles = [r.upper() for r in session.get('roles', [])]
        is_manager_2 = 'MANAGER_2' in roles
        if not is_admin and not is_manager_2 and username:
            u = username.strip().lower()
            query = query.filter(
                (func.lower(func.trim(ShowroomWiseOrderSummarySnapshot.make_owner)) == u) |
                (func.lower(func.trim(ShowroomWiseOrderSummarySnapshot.collection_owner)) == u) |
                (func.lower(func.trim(ShowroomWiseOrderSummarySnapshot.classification_owner)) == u)
            )

        return query

    agg_cols = [
        func.sum(cast(ShowroomWiseOrderSummarySnapshot.order_wt, Numeric)).label('total_order_wt'),
        func.sum(cast(ShowroomWiseOrderSummarySnapshot.accepted_wt, Numeric)).label('accepted_wt'),
        func.sum(cast(ShowroomWiseOrderSummarySnapshot.rejected_wt, Numeric)).label('rejected_wt'),
        func.sum(cast(ShowroomWiseOrderSummarySnapshot.barcoded_wt, Numeric)).label('barcoded_wt'),
        func.sum(cast(ShowroomWiseOrderSummarySnapshot.hm_passed_wt, Numeric)).label('hm_passed_wt'),
        func.sum(cast(ShowroomWiseOrderSummarySnapshot.qc_passed_wt, Numeric)).label('qc_passed_wt'),
        func.sum(cast(ShowroomWiseOrderSummarySnapshot.invoiced_wt, Numeric)).label('invoiced_wt'),
        func.sum(cast(ShowroomWiseOrderSummarySnapshot.delivered_wt, Numeric)).label('delivered_wt'),
        func.sum(cast(ShowroomWiseOrderSummarySnapshot.pending_to_deliver_wt, Numeric)).label('pending_to_deliver_wt'),
        func.sum(cast(ShowroomWiseOrderSummarySnapshot.cancelled_wt, Numeric)).label('cancelled_wt'),
        func.sum(cast(ShowroomWiseOrderSummarySnapshot.pending_to_accepted_wt, Numeric)).label('pending_to_accepted_wt')
    ]
    
    agg_q = db.session.query(*agg_cols)
    agg_q = apply_filters(agg_q)
    aggs = agg_q.first()

    return {
        'total_order_wt': safe_float(aggs.total_order_wt),
        'accepted_wt': safe_float(aggs.accepted_wt),
        'rejected_wt': safe_float(aggs.rejected_wt),
        'barcoded_wt': safe_float(aggs.barcoded_wt),
        'hm_passed_wt': safe_float(aggs.hm_passed_wt),
        'qc_passed_wt': safe_float(aggs.qc_passed_wt),
        'invoiced_wt': safe_float(aggs.invoiced_wt),
        'delivered_wt': safe_float(aggs.delivered_wt),
        'pending_to_deliver_wt': safe_float(aggs.pending_to_deliver_wt),
        'cancelled_wt': safe_float(aggs.cancelled_wt),
        'pending_to_accepted_wt': safe_float(aggs.pending_to_accepted_wt)
    }

@dashboard_bp.route('/showroom_wise_order_summary')
def showroom_wise_order_summary():
    try:
        unread_count = Notification.query.filter_by(is_read=False).count()
        sync_time = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%I:%M %p")

        # Just return the empty template shell, it will be populated via AJAX
        return render_template('showroom_wise_order_summary.html', 
                             unread_count=unread_count, 
                             sync_time=sync_time, 
                             stats=None, 
                             rows=None, 
                             pagination=None, 
                             footer_totals=None,
                             current_level='business_head')
    except Exception as e:
        logger.error(f"Error in showroom_wise_order_summary: {str(e)}")
        return f"Error: {str(e)}", 500

@dashboard_bp.route('/sync/showroom_wise_order_summary', methods=['POST'])
@jwt_required()
def sync_showroom_wise_order_summary():
    return jsonify(sync_showroom_wise_order_summary_data())

@dashboard_bp.route('/api/showroom/options')
@jwt_required()
def showroom_options():
    try:
        is_admin = session.get('is_admin', False)
        username = session.get('username')
        
        def apply_options_filter(q):
            roles = [r.upper() for r in session.get('roles', [])]
            is_manager_2 = 'MANAGER_2' in roles
            if not is_admin and not is_manager_2 and username:
                u = username.strip().lower()
                return q.filter(
                    (func.lower(func.trim(ShowroomWiseOrderSummarySnapshot.make_owner)) == u) |
                    (func.lower(func.trim(ShowroomWiseOrderSummarySnapshot.collection_owner)) == u) |
                    (func.lower(func.trim(ShowroomWiseOrderSummarySnapshot.classification_owner)) == u)
                )
            return q

        options = {
            'business_heads': [r[0] for r in apply_options_filter(db.session.query(ShowroomWiseOrderSummarySnapshot.business_head.distinct())).order_by(ShowroomWiseOrderSummarySnapshot.business_head).all() if r[0]],
            'classification_owners': [r[0] for r in apply_options_filter(db.session.query(ShowroomWiseOrderSummarySnapshot.classification_owner.distinct())).order_by(ShowroomWiseOrderSummarySnapshot.classification_owner).all() if r[0]],
            'make_owners': [r[0] for r in apply_options_filter(db.session.query(ShowroomWiseOrderSummarySnapshot.make_owner.distinct())).order_by(ShowroomWiseOrderSummarySnapshot.make_owner).all() if r[0]],
            'collection_owners': [r[0] for r in apply_options_filter(db.session.query(ShowroomWiseOrderSummarySnapshot.collection_owner.distinct())).order_by(ShowroomWiseOrderSummarySnapshot.collection_owner).all() if r[0]],
            'parties': [r[0] for r in apply_options_filter(db.session.query(ShowroomWiseOrderSummarySnapshot.party.distinct())).order_by(ShowroomWiseOrderSummarySnapshot.party).all() if r[0]],
            'locations': [r[0] for r in apply_options_filter(db.session.query(ShowroomWiseOrderSummarySnapshot.location.distinct())).order_by(ShowroomWiseOrderSummarySnapshot.location).all() if r[0]],
            'purchase_ros': [r[0] for r in apply_options_filter(db.session.query(ShowroomWiseOrderSummarySnapshot.purchase_ro.distinct())).order_by(ShowroomWiseOrderSummarySnapshot.purchase_ro).all() if r[0]],
            'order_types': [r[0] for r in apply_options_filter(db.session.query(ShowroomWiseOrderSummarySnapshot.order_type.distinct())).order_by(ShowroomWiseOrderSummarySnapshot.order_type).all() if r[0]],
            'order_request_types': [r[0] for r in apply_options_filter(db.session.query(ShowroomWiseOrderSummarySnapshot.order_request_type.distinct())).order_by(ShowroomWiseOrderSummarySnapshot.order_request_type).all() if r[0]],
            'divisions': [r[0] for r in apply_options_filter(db.session.query(ShowroomWiseOrderSummarySnapshot.division.distinct())).order_by(ShowroomWiseOrderSummarySnapshot.division).all() if r[0]],
            'groups': [r[0] for r in apply_options_filter(db.session.query(ShowroomWiseOrderSummarySnapshot.group_name.distinct())).order_by(ShowroomWiseOrderSummarySnapshot.group_name).all() if r[0]],
            'purities': [r[0] for r in apply_options_filter(db.session.query(ShowroomWiseOrderSummarySnapshot.purity.distinct())).order_by(ShowroomWiseOrderSummarySnapshot.purity).all() if r[0]],
            'classifications': [r[0] for r in apply_options_filter(db.session.query(ShowroomWiseOrderSummarySnapshot.classification.distinct())).order_by(ShowroomWiseOrderSummarySnapshot.classification).all() if r[0]],
            'makes': [r[0] for r in apply_options_filter(db.session.query(ShowroomWiseOrderSummarySnapshot.make.distinct())).order_by(ShowroomWiseOrderSummarySnapshot.make).all() if r[0]],
            'collections': [r[0] for r in apply_options_filter(db.session.query(ShowroomWiseOrderSummarySnapshot.collection.distinct())).order_by(ShowroomWiseOrderSummarySnapshot.collection).all() if r[0]]
        }
        return jsonify(options)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@dashboard_bp.route('/partial/showroom')
@jwt_required()
def get_showroom_partial():
    try:
        latest_date_query = db.session.query(func.max(ShowroomWiseOrderSummarySnapshot.snapshot_date)).scalar()
        
        search = request.args.get('search', '').strip()
        business_head = request.args.get('business_head', '')
        classification_owner = request.args.get('classification_owner', '')
        make_owner = request.args.get('make_owner', '')
        collection_owner = request.args.get('collection_owner', '')
        party = request.args.get('party', '')
        location = request.args.get('location', '')
        purchase_ro = request.args.get('purchase_ro', '')
        order_type = request.args.get('order_type', '')
        order_request_type = request.args.get('order_request_type', '')
        division = request.args.get('division', '')
        group_name = request.args.get('group_name', '')
        purity = request.args.get('purity', '')
        classification = request.args.get('classification', '')
        make = request.args.get('make', '')
        collection = request.args.get('collection', '')

        parent_level = request.args.get('parent_level')
        parent_value = request.args.get('parent_value')
        
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)
        
        is_child_rows = bool(parent_level)
        
        def apply_filters(query):
            if search:
                query = query.filter(ShowroomWiseOrderSummarySnapshot.business_head.ilike(f"%{search}%") | 
                                     ShowroomWiseOrderSummarySnapshot.party.ilike(f"%{search}%") |
                                     ShowroomWiseOrderSummarySnapshot.location.ilike(f"%{search}%"))
            if business_head:
                if business_head == 'Unknown':
                    query = query.filter(
                        (ShowroomWiseOrderSummarySnapshot.business_head == None) |
                        (ShowroomWiseOrderSummarySnapshot.business_head == '') |
                        (ShowroomWiseOrderSummarySnapshot.business_head == 'NULL')
                    )
                else:
                    query = query.filter(ShowroomWiseOrderSummarySnapshot.business_head == business_head)
            if classification_owner: query = query.filter(ShowroomWiseOrderSummarySnapshot.classification_owner == classification_owner)
            if make_owner: query = query.filter(ShowroomWiseOrderSummarySnapshot.make_owner == make_owner)
            if collection_owner: query = query.filter(ShowroomWiseOrderSummarySnapshot.collection_owner == collection_owner)
            if party: query = query.filter(ShowroomWiseOrderSummarySnapshot.party == party)
            if location: query = query.filter(ShowroomWiseOrderSummarySnapshot.location == location)
            if purchase_ro: query = query.filter(ShowroomWiseOrderSummarySnapshot.purchase_ro == purchase_ro)
            if order_type: query = query.filter(ShowroomWiseOrderSummarySnapshot.order_type == order_type)
            if order_request_type: query = query.filter(ShowroomWiseOrderSummarySnapshot.order_request_type == order_request_type)
            if division: query = query.filter(ShowroomWiseOrderSummarySnapshot.division == division)
            if group_name: query = query.filter(ShowroomWiseOrderSummarySnapshot.group_name == group_name)
            if purity: query = query.filter(ShowroomWiseOrderSummarySnapshot.purity == purity)
            if classification: query = query.filter(ShowroomWiseOrderSummarySnapshot.classification == classification)
            if make: query = query.filter(ShowroomWiseOrderSummarySnapshot.make == make)
            if collection: query = query.filter(ShowroomWiseOrderSummarySnapshot.collection == collection)
            
            if latest_date_query:
                query = query.filter(ShowroomWiseOrderSummarySnapshot.snapshot_date == latest_date_query)

            # User-based filtering: Restrict to any owner = username if not admin or MANAGER_2
            is_admin = session.get('is_admin', False)
            username = session.get('username')
            roles = [r.upper() for r in session.get('roles', [])]
            is_manager_2 = 'MANAGER_2' in roles
            if not is_admin and not is_manager_2 and username:
                u = username.strip().lower()
                query = query.filter(
                    (func.lower(func.trim(ShowroomWiseOrderSummarySnapshot.make_owner)) == u) |
                    (func.lower(func.trim(ShowroomWiseOrderSummarySnapshot.collection_owner)) == u) |
                    (func.lower(func.trim(ShowroomWiseOrderSummarySnapshot.classification_owner)) == u)
                )

            return query

        agg_cols = [
            func.sum(cast(ShowroomWiseOrderSummarySnapshot.order_wt, Numeric)).label('total_order_wt'),
            func.sum(cast(ShowroomWiseOrderSummarySnapshot.accepted_wt, Numeric)).label('accepted_wt'),
            func.sum(cast(ShowroomWiseOrderSummarySnapshot.rejected_wt, Numeric)).label('rejected_wt'),
            func.sum(cast(ShowroomWiseOrderSummarySnapshot.barcoded_wt, Numeric)).label('barcoded_wt'),
            func.sum(cast(ShowroomWiseOrderSummarySnapshot.hm_passed_wt, Numeric)).label('hm_passed_wt'),
            func.sum(cast(ShowroomWiseOrderSummarySnapshot.qc_passed_wt, Numeric)).label('qc_passed_wt'),
            func.sum(cast(ShowroomWiseOrderSummarySnapshot.invoiced_wt, Numeric)).label('invoiced_wt'),
            func.sum(cast(ShowroomWiseOrderSummarySnapshot.delivered_wt, Numeric)).label('delivered_wt'),
            func.sum(cast(ShowroomWiseOrderSummarySnapshot.pending_to_deliver_wt, Numeric)).label('pending_to_deliver_wt'),
            func.sum(cast(ShowroomWiseOrderSummarySnapshot.cancelled_wt, Numeric)).label('cancelled_wt'),
            func.sum(cast(ShowroomWiseOrderSummarySnapshot.pending_to_accepted_wt, Numeric)).label('pending_to_accepted_wt')
        ]
        
        if parent_level == 'business_head':
            group_cols = [ShowroomWiseOrderSummarySnapshot.business_head, ShowroomWiseOrderSummarySnapshot.location]
            level = 'location'
            if parent_level and parent_value:
                if parent_value == 'Unknown':
                    # Handle all cases that result in 'Unknown' as the parent value
                    base_query = db.session.query(ShowroomWiseOrderSummarySnapshot).filter(
                        (ShowroomWiseOrderSummarySnapshot.business_head == None) |
                        (ShowroomWiseOrderSummarySnapshot.business_head == '') |
                        (ShowroomWiseOrderSummarySnapshot.business_head == 'NULL')
                    )
                else:
                    base_query = db.session.query(ShowroomWiseOrderSummarySnapshot).filter(ShowroomWiseOrderSummarySnapshot.business_head == parent_value)
        elif parent_level == 'location':
            group_cols = [ShowroomWiseOrderSummarySnapshot.business_head, ShowroomWiseOrderSummarySnapshot.location, ShowroomWiseOrderSummarySnapshot.classification_owner]
            level = 'classification_owner'
            base_query = db.session.query(ShowroomWiseOrderSummarySnapshot).filter(ShowroomWiseOrderSummarySnapshot.location == parent_value)
            if business_head:
                if business_head == 'Unknown':
                    base_query = base_query.filter(
                        (ShowroomWiseOrderSummarySnapshot.business_head == None) |
                        (ShowroomWiseOrderSummarySnapshot.business_head == '') |
                        (ShowroomWiseOrderSummarySnapshot.business_head == 'NULL')
                    )
                else:
                    base_query = base_query.filter(ShowroomWiseOrderSummarySnapshot.business_head == business_head)
        elif parent_level == 'classification_owner':
            group_cols = [ShowroomWiseOrderSummarySnapshot.business_head, ShowroomWiseOrderSummarySnapshot.location, ShowroomWiseOrderSummarySnapshot.classification_owner, ShowroomWiseOrderSummarySnapshot.make_owner]
            level = 'make_owner'
            base_query = db.session.query(ShowroomWiseOrderSummarySnapshot).filter(ShowroomWiseOrderSummarySnapshot.classification_owner == parent_value)
            if business_head:
                if business_head == 'Unknown':
                    base_query = base_query.filter(
                        (ShowroomWiseOrderSummarySnapshot.business_head == None) |
                        (ShowroomWiseOrderSummarySnapshot.business_head == '') |
                        (ShowroomWiseOrderSummarySnapshot.business_head == 'NULL')
                    )
                else:
                    base_query = base_query.filter(ShowroomWiseOrderSummarySnapshot.business_head == business_head)
            if location:
                base_query = base_query.filter(ShowroomWiseOrderSummarySnapshot.location == location)
        elif parent_level == 'make_owner':
            group_cols = [ShowroomWiseOrderSummarySnapshot.business_head, ShowroomWiseOrderSummarySnapshot.location, ShowroomWiseOrderSummarySnapshot.classification_owner, ShowroomWiseOrderSummarySnapshot.make_owner, ShowroomWiseOrderSummarySnapshot.collection_owner]
            level = 'collection_owner'
            base_query = db.session.query(ShowroomWiseOrderSummarySnapshot).filter(ShowroomWiseOrderSummarySnapshot.make_owner == parent_value)
            if business_head:
                if business_head == 'Unknown':
                    base_query = base_query.filter(
                        (ShowroomWiseOrderSummarySnapshot.business_head == None) |
                        (ShowroomWiseOrderSummarySnapshot.business_head == '') |
                        (ShowroomWiseOrderSummarySnapshot.business_head == 'NULL')
                    )
                else:
                    base_query = base_query.filter(ShowroomWiseOrderSummarySnapshot.business_head == business_head)
            if location:
                base_query = base_query.filter(ShowroomWiseOrderSummarySnapshot.location == location)
            if classification_owner:
                base_query = base_query.filter(ShowroomWiseOrderSummarySnapshot.classification_owner == classification_owner)
        else:
            base_query = db.session.query(ShowroomWiseOrderSummarySnapshot)
            if not business_head:
                group_cols = [ShowroomWiseOrderSummarySnapshot.business_head]
                level = 'business_head'
            elif not location:
                group_cols = [ShowroomWiseOrderSummarySnapshot.business_head, ShowroomWiseOrderSummarySnapshot.location]
                level = 'location'
            elif not classification_owner:
                group_cols = [ShowroomWiseOrderSummarySnapshot.business_head, ShowroomWiseOrderSummarySnapshot.location, ShowroomWiseOrderSummarySnapshot.classification_owner]
                level = 'classification_owner'
            elif not make_owner:
                group_cols = [ShowroomWiseOrderSummarySnapshot.business_head, ShowroomWiseOrderSummarySnapshot.location, ShowroomWiseOrderSummarySnapshot.classification_owner, ShowroomWiseOrderSummarySnapshot.make_owner]
                level = 'make_owner'
            else:
                group_cols = [ShowroomWiseOrderSummarySnapshot.business_head, ShowroomWiseOrderSummarySnapshot.location, ShowroomWiseOrderSummarySnapshot.classification_owner, ShowroomWiseOrderSummarySnapshot.make_owner, ShowroomWiseOrderSummarySnapshot.collection_owner]
                level = 'collection_owner'

        main_q = base_query.with_entities(*(group_cols + agg_cols))
        main_q = apply_filters(main_q)
        main_q = main_q.group_by(*group_cols).order_by(*group_cols)
        
        pagination = main_q.paginate(page=page, per_page=per_page, error_out=False)

        processed_rows = []
        for r in pagination.items:
            row_dict = {
                'business_head': r[0] if (r[0] and r[0] != 'NULL') else 'Unknown',
                'location': r[1] if level in ['location', 'classification_owner', 'make_owner', 'collection_owner'] else '',
                'classification_owner': r[2] if level in ['classification_owner', 'make_owner', 'collection_owner'] else '',
                'make_owner': r[3] if level in ['make_owner', 'collection_owner'] else '',
                'collection_owner': r[4] if level == 'collection_owner' else '',
                'total_order_wt': safe_float(r.total_order_wt),
                'accepted_wt': safe_float(r.accepted_wt),
                'rejected_wt': safe_float(r.rejected_wt),
                'barcoded_wt': safe_float(r.barcoded_wt),
                'hm_passed_wt': safe_float(r.hm_passed_wt),
                'qc_passed_wt': safe_float(r.qc_passed_wt),
                'invoiced_wt': safe_float(r.invoiced_wt),
                'delivered_wt': safe_float(r.delivered_wt),
                'pending_to_deliver_wt': safe_float(r.pending_to_deliver_wt),
                'cancelled_wt': safe_float(r.cancelled_wt),
                'pending_to_accepted_wt': safe_float(r.pending_to_accepted_wt),
                'level': level
            }
            processed_rows.append(row_dict)

        # Get stats for main view update
        stats = {}
        footer_totals = {}
        if not is_child_rows:
            stats = get_showroom_aggs(latest_date_query, search, business_head, classification_owner, 
                                    make_owner, collection_owner, party, location, 
                                    purchase_ro, order_type, order_request_type, 
                                    division, group_name, purity, classification, make, collection)
            footer_totals = stats

        return render_template('partials/_view_showroom_wise_order.html', 
                             rows=processed_rows, 
                             pagination=pagination if not is_child_rows else None, 
                             current_level=level,
                             is_child_rows=is_child_rows,
                             parent_level=parent_level,
                             parent_value=parent_value,
                             stats=stats,
                             footer_totals=footer_totals)
    except Exception as e:
        logger.error(f"Error in get_showroom_partial: {str(e)}")
        return f'<div class="p-8 text-center text-red-500 font-bold">Backend Error: {str(e)}</div>', 200

@dashboard_bp.route('/api/showroom/details')
@jwt_required()
def get_showroom_details():
    try:
        # Hierarchy constraints to inherit from main page view
        business_head = request.args.get('business_head')
        classification_owner = request.args.get('classification_owner')
        make_owner = request.args.get('make_owner')
        collection_owner = request.args.get('collection_owner')
        
        latest_date_query = db.session.query(func.max(ShowroomWiseOrderSummarySnapshot.snapshot_date)).scalar()
        
        # Base filters
        search = request.args.get('search', '').strip()
        location_filter = request.args.get('location', '') 
        party_filter = request.args.get('party', '')
        purchase_ro = request.args.get('purchase_ro', '')
        order_type = request.args.get('order_type', '')
        order_request_type = request.args.get('order_request_type', '')
        
        division = request.args.get('division', '')
        group_name = request.args.get('group_name', '')
        purity = request.args.get('purity', '')
        classification = request.args.get('classification', '')
        make = request.args.get('make', '')
        collection = request.args.get('collection', '')

        print(f"DEBUG modal API: level={request.args.get('modal_level')}, is_child={request.args.get('is_modal_child')}, location={location_filter}")

        # Modal specific logic for nested tree
        modal_level = request.args.get('modal_level', 'location')
        modal_type = request.args.get('modal_type', 'drilldown')
        is_modal_child = request.args.get('is_modal_child') == 'true'

        query = ShowroomWiseOrderSummarySnapshot.query
        
        # Apply hierarchy filters
        if business_head: query = query.filter(ShowroomWiseOrderSummarySnapshot.business_head == business_head)
        if classification_owner: query = query.filter(ShowroomWiseOrderSummarySnapshot.classification_owner == classification_owner)
        if make_owner: query = query.filter(ShowroomWiseOrderSummarySnapshot.make_owner == make_owner)
        if collection_owner: query = query.filter(ShowroomWiseOrderSummarySnapshot.collection_owner == collection_owner)
        
        # Apply global filters
        if search:
            query = query.filter(ShowroomWiseOrderSummarySnapshot.business_head.ilike(f"%{search}%") | 
                                 ShowroomWiseOrderSummarySnapshot.party.ilike(f"%{search}%") |
                                 ShowroomWiseOrderSummarySnapshot.location.ilike(f"%{search}%"))
        
        if party_filter: query = query.filter(ShowroomWiseOrderSummarySnapshot.party == party_filter)
        if location_filter: query = query.filter(ShowroomWiseOrderSummarySnapshot.location == location_filter)
        if purchase_ro: query = query.filter(ShowroomWiseOrderSummarySnapshot.purchase_ro == purchase_ro)
        if order_type: query = query.filter(ShowroomWiseOrderSummarySnapshot.order_type == order_type)
        if order_request_type: query = query.filter(ShowroomWiseOrderSummarySnapshot.order_request_type == order_request_type)
        if division: query = query.filter(ShowroomWiseOrderSummarySnapshot.division == division)
        if group_name: query = query.filter(ShowroomWiseOrderSummarySnapshot.group_name == group_name)
        if purity: query = query.filter(ShowroomWiseOrderSummarySnapshot.purity == purity)
        if classification: query = query.filter(ShowroomWiseOrderSummarySnapshot.classification == classification)
        if make: query = query.filter(ShowroomWiseOrderSummarySnapshot.make == make)
        if collection: query = query.filter(ShowroomWiseOrderSummarySnapshot.collection == collection)

        if latest_date_query:
            query = query.filter(ShowroomWiseOrderSummarySnapshot.snapshot_date == latest_date_query)

        # User-based filtering: Restrict to any owner = username if not admin or MANAGER_2
        is_admin = session.get('is_admin', False)
        username = session.get('username')
        roles = [r.upper() for r in session.get('roles', [])]
        is_manager_2 = 'MANAGER_2' in roles
        if not is_admin and not is_manager_2 and username:
            u = username.strip().lower()
            query = query.filter(
                (func.lower(func.trim(ShowroomWiseOrderSummarySnapshot.make_owner)) == u) |
                (func.lower(func.trim(ShowroomWiseOrderSummarySnapshot.collection_owner)) == u) |
                (func.lower(func.trim(ShowroomWiseOrderSummarySnapshot.classification_owner)) == u)
            )
        
        hierarchy = ['location', 'division', 'group_name', 'purity', 'classification', 'make', 'collection', 'party']
        col_map = {
            'location': ShowroomWiseOrderSummarySnapshot.location,
            'division': ShowroomWiseOrderSummarySnapshot.division,
            'group_name': ShowroomWiseOrderSummarySnapshot.group_name,
            'purity': ShowroomWiseOrderSummarySnapshot.purity,
            'classification': ShowroomWiseOrderSummarySnapshot.classification,
            'make': ShowroomWiseOrderSummarySnapshot.make,
            'collection': ShowroomWiseOrderSummarySnapshot.collection,
            'party': ShowroomWiseOrderSummarySnapshot.party
        }
        
        agg_cols = [
            func.sum(cast(ShowroomWiseOrderSummarySnapshot.order_wt, Numeric)).label('order_wt'),
            func.sum(cast(ShowroomWiseOrderSummarySnapshot.accepted_wt, Numeric)).label('accepted_wt'),
            func.sum(cast(ShowroomWiseOrderSummarySnapshot.rejected_wt, Numeric)).label('rejected_wt'),
            func.sum(cast(ShowroomWiseOrderSummarySnapshot.barcoded_wt, Numeric)).label('barcoded_wt'),
            func.sum(cast(ShowroomWiseOrderSummarySnapshot.hm_passed_wt, Numeric)).label('hm_passed_wt'),
            func.sum(cast(ShowroomWiseOrderSummarySnapshot.qc_passed_wt, Numeric)).label('qc_passed_wt'),
            func.sum(cast(ShowroomWiseOrderSummarySnapshot.invoiced_wt, Numeric)).label('invoiced_wt'),
            func.sum(cast(ShowroomWiseOrderSummarySnapshot.delivered_wt, Numeric)).label('delivered_wt'),
            func.sum(cast(ShowroomWiseOrderSummarySnapshot.pending_to_deliver_wt, Numeric)).label('pending_to_deliver_wt'),
            func.sum(cast(ShowroomWiseOrderSummarySnapshot.cancelled_wt, Numeric)).label('cancelled_wt'),
            func.sum(cast(ShowroomWiseOrderSummarySnapshot.pending_to_accepted_wt, Numeric)).label('pending_to_accepted_wt')
        ]

        def safe_float(val):
            return float(val) if val is not None else 0.0

        if modal_level == 'orders':
            # Base leaf view - show actual order rows
            processed_rows = query.limit(1000).all()
            for r in processed_rows:
                r.is_leaf = True
                r.level = 'orders'
        else:
            # Aggregation view
            if modal_level not in hierarchy:
                modal_level = 'location'
            
            idx = hierarchy.index(modal_level)
            group_cols = [col_map[hierarchy[i]] for i in range(idx + 1)]
            
            agg_query = query.with_entities(*(group_cols + agg_cols))
            agg_query = agg_query.group_by(*group_cols).order_by(*group_cols)
            
            raw_rows = agg_query.all()
            print(f"DEBUG modal API: agg_query returned {len(raw_rows)} rows. SQL: {agg_query.statement.compile(compile_kwargs={'literal_binds': True})}")
            processed_rows = []

            for r in raw_rows:
                # Create a dict-like object (or dictionary) that template can use
                row_dict = {
                    'is_leaf': False,
                    'level': modal_level,
                    'order_wt': safe_float(r.order_wt),
                    'accepted_wt': safe_float(r.accepted_wt),
                    'rejected_wt': safe_float(r.rejected_wt),
                    'barcoded_wt': safe_float(r.barcoded_wt),
                    'hm_passed_wt': safe_float(r.hm_passed_wt),
                    'qc_passed_wt': safe_float(r.qc_passed_wt),
                    'invoiced_wt': safe_float(r.invoiced_wt),
                    'delivered_wt': safe_float(r.delivered_wt),
                    'pending_to_deliver_wt': safe_float(r.pending_to_deliver_wt),
                    'cancelled_wt': safe_float(r.cancelled_wt),
                    'pending_to_accepted_wt': safe_float(r.pending_to_accepted_wt),
                    'po_number': '-',
                    'order_date': None
                }
                # Backfill hierarchy values for attributes
                for col in hierarchy:
                    row_dict[col] = ''
                for i in range(idx + 1):
                    row_dict[hierarchy[i]] = getattr(r, hierarchy[i], '') or ''
                
                # Create a simple class to allow dot-notation access in Jinja template
                class DotDict(dict):
                    __getattr__ = dict.get
                    __setattr__ = dict.__setitem__
                    __delattr__ = dict.__delitem__
                    
                processed_rows.append(DotDict(row_dict))
                
        # Calculate Grand Totals for modal (only for top level modal call)
        modal_totals = {}
        if not is_modal_child:
            modal_agg_query = query.with_entities(*agg_cols)
            modal_aggs = modal_agg_query.first()
            modal_totals = {
                'order_wt': safe_float(modal_aggs.order_wt),
                'accepted_wt': safe_float(modal_aggs.accepted_wt),
                'rejected_wt': safe_float(modal_aggs.rejected_wt),
                'barcoded_wt': safe_float(modal_aggs.barcoded_wt),
                'hm_passed_wt': safe_float(modal_aggs.hm_passed_wt),
                'qc_passed_wt': safe_float(modal_aggs.qc_passed_wt),
                'invoiced_wt': safe_float(modal_aggs.invoiced_wt),
                'delivered_wt': safe_float(modal_aggs.delivered_wt),
                'pending_to_deliver_wt': safe_float(modal_aggs.pending_to_deliver_wt),
                'cancelled_wt': safe_float(modal_aggs.cancelled_wt),
                'pending_to_accepted_wt': safe_float(modal_aggs.pending_to_accepted_wt)
            }

        return render_template('partials/_view_showroom_drilldown.html', 
                             details=processed_rows, 
                             is_modal_child=is_modal_child,
                             modal_level=modal_level,
                             modal_type=modal_type,
                             modal_totals=modal_totals,
                             location_name=location_filter)
    except Exception as e:
        import traceback
        with open('/tmp/modal_error.log', 'w') as f:
            f.write(traceback.format_exc())
        logger.error(f"Error in get_showroom_details: {str(e)}")
        return f'<div class="p-4 text-center text-red-500">Error: {str(e)}</div>', 400
