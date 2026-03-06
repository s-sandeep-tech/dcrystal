from flask import render_template, request, jsonify
from flask_jwt_extended import jwt_required
from app.dashboard import dashboard_bp
from app.models import Notification
from app.models.snapshots import OrderDelayTrackingSnapshot
from app.extensions import db
from sqlalchemy import func, cast, Numeric
from datetime import datetime
import logging
import json
from app.extensions import redis_client

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

@dashboard_bp.route('/orderdelaytracking')
@jwt_required()
def order_delay_tracking():
    try:
        unread_count = Notification.query.filter_by(is_read=False).count()
        sync_time = datetime.now().strftime("%H:%M")

        # Fetch latest snapshot date
        latest_date_query = db.session.query(func.max(OrderDelayTrackingSnapshot.snapshot_date)).scalar()
        
        has_any_data = db.session.query(OrderDelayTrackingSnapshot.id).first()
        if not has_any_data:
            empty_totals = {
                'delay_1_2_days': 0, 'delay_3_4_days': 0,
                'delay_5_10_days': 0, 'delay_more_than_10_days': 0
            }
            return render_template('order_delay_tracking.html', 
                                 unread_count=unread_count, 
                                 sync_time=sync_time, 
                                 rows=[], 
                                 pagination=None, 
                                 footer_totals=empty_totals)

        # Filters
        classification_owner = request.args.get('classification_owner', '')
        make_owner = request.args.get('make_owner', '')
        collection_owner = request.args.get('collection_owner', '')
        supplier = request.args.get('supplier', '')
        make = request.args.get('make', '')
        collection = request.args.get('collection', '')
        search = request.args.get('search', '').strip()
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)

        def apply_filters(query):
            if supplier:
                query = query.filter(OrderDelayTrackingSnapshot.supplier == supplier)
            if classification_owner:
                query = query.filter(OrderDelayTrackingSnapshot.classification_owner == classification_owner)
            if make_owner:
                query = query.filter(OrderDelayTrackingSnapshot.make_owner == make_owner)
            if collection_owner:
                query = query.filter(OrderDelayTrackingSnapshot.collection_owner == collection_owner)
            if make:
                query = query.filter(OrderDelayTrackingSnapshot.make == make)
            if collection:
                query = query.filter(OrderDelayTrackingSnapshot.collection == collection)
            if search:
                query = query.filter(
                    OrderDelayTrackingSnapshot.classification_owner.ilike(f"%{search}%") |
                    OrderDelayTrackingSnapshot.make_owner.ilike(f"%{search}%") |
                    OrderDelayTrackingSnapshot.collection_owner.ilike(f"%{search}%") |
                    OrderDelayTrackingSnapshot.supplier.ilike(f"%{search}%") |
                    OrderDelayTrackingSnapshot.make.ilike(f"%{search}%") |
                    OrderDelayTrackingSnapshot.collection.ilike(f"%{search}%")
                )
            
            if latest_date_query:
                query = query.filter(OrderDelayTrackingSnapshot.snapshot_date == latest_date_query)
            return query

        # Aggregation
        agg_cols = [
            func.sum(OrderDelayTrackingSnapshot.delay_1_2_days).label('delay_1_2_days'),
            func.sum(OrderDelayTrackingSnapshot.delay_3_4_days).label('delay_3_4_days'),
            func.sum(OrderDelayTrackingSnapshot.delay_5_10_days).label('delay_5_10_days'),
            func.sum(OrderDelayTrackingSnapshot.delay_more_than_10_days).label('delay_more_than_10_days')
        ]
        
        group_cols = [
            OrderDelayTrackingSnapshot.classification_owner,
            OrderDelayTrackingSnapshot.make_owner,
            OrderDelayTrackingSnapshot.collection_owner
        ]

        main_q = db.session.query(*(group_cols + agg_cols))
        main_q = apply_filters(main_q)
        main_q = main_q.group_by(*group_cols).order_by(*group_cols)
        
        pagination = main_q.paginate(page=page, per_page=per_page, error_out=False)
        
        processed_rows = []
        for r in pagination.items:
            processed_rows.append({
                'classification_owner': r[0] or 'Unknown',
                'make_owner': r[1] or 'Unknown',
                'collection_owner': r[2] or 'Unknown',
                'delay_1_2_days': int(r.delay_1_2_days or 0),
                'delay_3_4_days': int(r.delay_3_4_days or 0),
                'delay_5_10_days': int(r.delay_5_10_days or 0),
                'delay_more_than_10_days': int(r.delay_more_than_10_days or 0)
            })

        # Totals for footer
        total_q = db.session.query(*agg_cols)
        total_q = apply_filters(total_q)
        totals = total_q.first()
        footer_totals = {
            'delay_1_2_days': int(totals.delay_1_2_days or 0) if totals else 0,
            'delay_3_4_days': int(totals.delay_3_4_days or 0) if totals else 0,
            'delay_5_10_days': int(totals.delay_5_10_days or 0) if totals else 0,
            'delay_more_than_10_days': int(totals.delay_more_than_10_days or 0) if totals else 0
        }

        return render_template('order_delay_tracking.html', 
                             unread_count=unread_count, 
                             sync_time=sync_time,
                             rows=processed_rows,
                             pagination=pagination,
                             footer_totals=footer_totals)
    except Exception as e:
        logger.error(f"Error in order_delay_tracking: {str(e)}")
        return f"Error: {str(e)}", 500

@dashboard_bp.route('/api/orderdelaytracking/options')
@jwt_required()
def order_delay_tracking_options():
    try:
        options = {
            'suppliers': [r[0] for r in db.session.query(OrderDelayTrackingSnapshot.supplier.distinct()).order_by(OrderDelayTrackingSnapshot.supplier).all() if r[0]],
            'classification_owners': [r[0] for r in db.session.query(OrderDelayTrackingSnapshot.classification_owner.distinct()).order_by(OrderDelayTrackingSnapshot.classification_owner).all() if r[0]],
            'make_owners': [r[0] for r in db.session.query(OrderDelayTrackingSnapshot.make_owner.distinct()).order_by(OrderDelayTrackingSnapshot.make_owner).all() if r[0]],
            'collection_owners': [r[0] for r in db.session.query(OrderDelayTrackingSnapshot.collection_owner.distinct()).order_by(OrderDelayTrackingSnapshot.collection_owner).all() if r[0]],
            'makes': [r[0] for r in db.session.query(OrderDelayTrackingSnapshot.make.distinct()).order_by(OrderDelayTrackingSnapshot.make).all() if r[0]],
            'collections': [r[0] for r in db.session.query(OrderDelayTrackingSnapshot.collection.distinct()).order_by(OrderDelayTrackingSnapshot.collection).all() if r[0]]
        }
        return jsonify(options)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@dashboard_bp.route('/partial/orderdelaytracking')
@jwt_required()
def get_order_delay_tracking_partial():
    try:
        latest_date_query = db.session.query(func.max(OrderDelayTrackingSnapshot.snapshot_date)).scalar()
        
        # Filters from Sidebar
        f_supplier = request.args.get('supplier', '')
        f_classification_owner = request.args.get('classification_owner', '')
        f_make_owner = request.args.get('make_owner', '')
        f_collection_owner = request.args.get('collection_owner', '')
        f_make = request.args.get('make', '')
        f_collection = request.args.get('collection', '')
        f_search = request.args.get('search', '').strip()
        
        # Breadcrumb / Level tracking
        parent_level = request.args.get('parent_level', '')
        parent_value = request.args.get('parent_value', '')
        grandparent_value = request.args.get('grandparent_value', '')
        
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)
        
        def apply_filters(query):
            if f_supplier:
                query = query.filter(OrderDelayTrackingSnapshot.supplier == f_supplier)
            if f_classification_owner:
                query = query.filter(OrderDelayTrackingSnapshot.classification_owner == f_classification_owner)
            if f_make_owner:
                query = query.filter(OrderDelayTrackingSnapshot.make_owner == f_make_owner)
            if f_collection_owner:
                query = query.filter(OrderDelayTrackingSnapshot.collection_owner == f_collection_owner)
            if f_make:
                query = query.filter(OrderDelayTrackingSnapshot.make == f_make)
            if f_collection:
                query = query.filter(OrderDelayTrackingSnapshot.collection == f_collection)
            if f_search:
                query = query.filter(
                    OrderDelayTrackingSnapshot.classification_owner.ilike(f"%{f_search}%") |
                    OrderDelayTrackingSnapshot.make_owner.ilike(f"%{f_search}%") |
                    OrderDelayTrackingSnapshot.collection_owner.ilike(f"%{f_search}%") |
                    OrderDelayTrackingSnapshot.supplier.ilike(f"%{f_search}%") |
                    OrderDelayTrackingSnapshot.make.ilike(f"%{f_search}%") |
                    OrderDelayTrackingSnapshot.collection.ilike(f"%{f_search}%")
                )
            
            if latest_date_query:
                query = query.filter(OrderDelayTrackingSnapshot.snapshot_date == latest_date_query)
            return query

        # Aggregation columns
        agg_cols = [
            func.sum(OrderDelayTrackingSnapshot.delay_1_2_days).label('delay_1_2_days'),
            func.sum(OrderDelayTrackingSnapshot.delay_3_4_days).label('delay_3_4_days'),
            func.sum(OrderDelayTrackingSnapshot.delay_5_10_days).label('delay_5_10_days'),
            func.sum(OrderDelayTrackingSnapshot.delay_more_than_10_days).label('delay_more_than_10_days')
        ]
        
        group_cols = []
        base_query = db.session.query(OrderDelayTrackingSnapshot)
        
        if not parent_level:
            level = 'classification_owner'
            group_cols = [OrderDelayTrackingSnapshot.classification_owner]
        elif parent_level == 'classification_owner':
            level = 'make_owner'
            group_cols = [OrderDelayTrackingSnapshot.classification_owner, OrderDelayTrackingSnapshot.make_owner]
            base_query = base_query.filter(OrderDelayTrackingSnapshot.classification_owner == parent_value)
        elif parent_level == 'make_owner':
            level = 'collection_owner'
            group_cols = [OrderDelayTrackingSnapshot.classification_owner, OrderDelayTrackingSnapshot.make_owner, OrderDelayTrackingSnapshot.collection_owner]
            base_query = base_query.filter(OrderDelayTrackingSnapshot.make_owner == parent_value)
            if grandparent_value:
                base_query = base_query.filter(OrderDelayTrackingSnapshot.classification_owner == grandparent_value)
        else:
            level = 'unknown'

        # Totals for footer (only for root level)
        footer_totals = {}
        if not parent_level:
            total_q = db.session.query(*agg_cols)
            total_q = apply_filters(total_q)
            totals = total_q.first()
            footer_totals = {
                'delay_1_2_days': int(totals.delay_1_2_days or 0) if totals else 0,
                'delay_3_4_days': int(totals.delay_3_4_days or 0) if totals else 0,
                'delay_5_10_days': int(totals.delay_5_10_days or 0) if totals else 0,
                'delay_more_than_10_days': int(totals.delay_more_than_10_days or 0) if totals else 0
            }

        # Main query for rows
        main_q = base_query.with_entities(*(group_cols + agg_cols))
        main_q = apply_filters(main_q)
        main_q = main_q.group_by(*group_cols).order_by(*group_cols)
        
        pagination = main_q.paginate(page=page, per_page=per_page, error_out=False)
        
        processed_rows = []
        for r in pagination.items:
            row_dict = {
                'delay_1_2_days': int(r.delay_1_2_days or 0),
                'delay_3_4_days': int(r.delay_3_4_days or 0),
                'delay_5_10_days': int(r.delay_5_10_days or 0),
                'delay_more_than_10_days': int(r.delay_more_than_10_days or 0),
                'level': level
            }
            
            if level == 'classification_owner':
                row_dict.update({
                    'classification_owner': r[0] or 'Unknown',
                    'make_owner': '',
                    'collection_owner': '',
                    'display_value': r[0] or 'Unknown'
                })
            elif level == 'make_owner':
                row_dict.update({
                    'classification_owner': r[0],
                    'make_owner': r[1] or 'Unknown',
                    'collection_owner': '',
                    'display_value': r[1] or 'Unknown'
                })
            elif level == 'collection_owner':
                row_dict.update({
                    'classification_owner': r[0],
                    'make_owner': r[1],
                    'collection_owner': r[2] or 'Unknown',
                    'display_value': r[2] or 'Unknown'
                })
            
            processed_rows.append(row_dict)

        is_child_rows = bool(parent_level)
        return render_template('partials/_view_order_delay_tracking.html', 
                             rows=processed_rows, 
                             pagination=pagination if not is_child_rows else None, 
                             footer_totals=footer_totals,
                             current_level=level,
                             is_child_rows=is_child_rows,
                             parent_level=parent_level,
                             parent_value=parent_value,
                             grandparent_value=grandparent_value)
    except Exception as e:
        logger.error(f"Error in get_order_delay_tracking_partial: {str(e)}")
        return f'<div class="p-8 text-center text-red-500 font-bold">Backend Error: {str(e)}</div>', 200

@dashboard_bp.route('/api/orderdelaytracking/details')
@jwt_required()
def get_order_delay_tracking_details():
    try:
        classification_owner = request.args.get('classification_owner')
        make_owner = request.args.get('make_owner')
        collection_owner = request.args.get('collection_owner')
        
        # Parent Filters (Global)
        supplier = request.args.get('supplier', '')
        make_filter = request.args.get('make', '')
        collection_filter = request.args.get('collection', '')
        search = request.args.get('search', '').strip()
        
        # Modal-specific drill-down params
        parent_level = request.args.get('modal_parent_level')
        parent_value = request.args.get('modal_parent_value')
        
        latest_date_query = db.session.query(func.max(OrderDelayTrackingSnapshot.snapshot_date)).scalar()
        
        # Base filters from the main report's leaf node
        base_filters = []
        if latest_date_query:
            base_filters.append(OrderDelayTrackingSnapshot.snapshot_date == latest_date_query)
        if classification_owner:
            base_filters.append(OrderDelayTrackingSnapshot.classification_owner == classification_owner)
        if make_owner:
            base_filters.append(OrderDelayTrackingSnapshot.make_owner == make_owner)
        if collection_owner:
            base_filters.append(OrderDelayTrackingSnapshot.collection_owner == collection_owner)

        # Apply Global Filters
        if supplier:
            base_filters.append(OrderDelayTrackingSnapshot.supplier == supplier)
        if make_filter:
            base_filters.append(OrderDelayTrackingSnapshot.make == make_filter)
        if collection_filter:
            base_filters.append(OrderDelayTrackingSnapshot.collection == collection_filter)
        if search:
            base_filters.append(
                db.or_(
                    OrderDelayTrackingSnapshot.classification_owner.ilike(f"%{search}%"),
                    OrderDelayTrackingSnapshot.make_owner.ilike(f"%{search}%"),
                    OrderDelayTrackingSnapshot.collection_owner.ilike(f"%{search}%"),
                    OrderDelayTrackingSnapshot.supplier.ilike(f"%{search}%"),
                    OrderDelayTrackingSnapshot.make.ilike(f"%{search}%"),
                    OrderDelayTrackingSnapshot.collection.ilike(f"%{search}%")
                )
            )

        # Determine current modal level
        level = 'party'  # Start with Party (Supplier)
        group_cols = [OrderDelayTrackingSnapshot.supplier]
        
        if parent_level == 'party':
            level = 'make'
            group_cols = [OrderDelayTrackingSnapshot.make]
            base_filters.append(OrderDelayTrackingSnapshot.supplier == parent_value)
        elif parent_level == 'make':
            level = 'collection'
            group_cols = [OrderDelayTrackingSnapshot.collection]
            # When drilling down to collection, we need to know the make AND the party
            # But for simplicity, we'll assume the parent_value is the Make
            # and we might need the grandparent value (Party)
            grandparent_value = request.args.get('modal_grandparent_value')
            if grandparent_value:
                base_filters.append(OrderDelayTrackingSnapshot.supplier == grandparent_value)
            base_filters.append(OrderDelayTrackingSnapshot.make == parent_value)

        agg_cols = [
            func.sum(OrderDelayTrackingSnapshot.delay_1_2_days).label('delay_1_2_days'),
            func.sum(OrderDelayTrackingSnapshot.delay_3_4_days).label('delay_3_4_days'),
            func.sum(OrderDelayTrackingSnapshot.delay_5_10_days).label('delay_5_10_days'),
            func.sum(OrderDelayTrackingSnapshot.delay_more_than_10_days).label('delay_more_than_10_days')
        ]
        
        if level == 'collection':
            agg_cols.append(
                func.json_agg(
                    func.json_build_object(
                        'order_number', OrderDelayTrackingSnapshot.po_number,
                        'order_date', OrderDelayTrackingSnapshot.po_date,
                        'production_date', OrderDelayTrackingSnapshot.hm_out_date,
                        'delivery_date', OrderDelayTrackingSnapshot.delivery_target_date
                    )
                ).label('orders')
            )
        
        query = db.session.query(*(group_cols + agg_cols))
        for f in base_filters:
            query = query.filter(f)
            
        results = query.group_by(*group_cols).order_by(*group_cols).all()
        
        processed_details = []
        for r in results:
            row = {
                'level': level,
                'display_value': r[0],
                'delay_1_2_days': int(r.delay_1_2_days or 0),
                'delay_3_4_days': int(r.delay_3_4_days or 0),
                'delay_5_10_days': int(r.delay_5_10_days or 0),
                'delay_more_than_10_days': int(r.delay_more_than_10_days or 0)
            }
            if level == 'make':
                row['party'] = parent_value
            elif level == 'collection':
                row['party'] = request.args.get('modal_grandparent_value')
                row['make'] = parent_value
                # If aggregation orders exist, load them safely and unique them
                orders_list = getattr(r, 'orders', []) or []
                unique_orders = []
                seen_po = set()
                for o in orders_list:
                    if o.get('order_number') and o['order_number'] not in seen_po:
                        seen_po.add(o['order_number'])
                        unique_orders.append(o)
                # Parse to simpler date format strings if full ISO string is there
                row['orders'] = unique_orders
            processed_details.append(row)
            
        return render_template('partials/_view_order_delay_tracking_details.html', 
                               details=processed_details, 
                               is_child_rows=bool(parent_level))
    except Exception as e:
        logger.error(f"Error in get_order_delay_tracking_details: {str(e)}")
        return f'<div class="p-4 text-red-500 font-bold">Error: {str(e)}</div>', 200
