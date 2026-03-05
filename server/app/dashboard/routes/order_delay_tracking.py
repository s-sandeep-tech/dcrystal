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
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)

        def apply_filters(query):
            if classification_owner:
                query = query.filter(OrderDelayTrackingSnapshot.classification_owner == classification_owner)
            if make_owner:
                query = query.filter(OrderDelayTrackingSnapshot.make_owner == make_owner)
            if collection_owner:
                query = query.filter(OrderDelayTrackingSnapshot.collection_owner == collection_owner)
            
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
            'classification_owners': [r[0] for r in db.session.query(OrderDelayTrackingSnapshot.classification_owner.distinct()).order_by(OrderDelayTrackingSnapshot.classification_owner).all() if r[0]],
            'make_owners': [r[0] for r in db.session.query(OrderDelayTrackingSnapshot.make_owner.distinct()).order_by(OrderDelayTrackingSnapshot.make_owner).all() if r[0]],
            'collection_owners': [r[0] for r in db.session.query(OrderDelayTrackingSnapshot.collection_owner.distinct()).order_by(OrderDelayTrackingSnapshot.collection_owner).all() if r[0]]
        }
        return jsonify(options)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@dashboard_bp.route('/partial/orderdelaytracking')
@jwt_required()
def get_order_delay_tracking_partial():
    try:
        latest_date_query = db.session.query(func.max(OrderDelayTrackingSnapshot.snapshot_date)).scalar()
        
        # Filters
        classification_owner = request.args.get('classification_owner', '')
        make_owner = request.args.get('make_owner', '')
        collection_owner = request.args.get('collection_owner', '')
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)
        
        def apply_filters(query):
            if classification_owner:
                query = query.filter(OrderDelayTrackingSnapshot.classification_owner == classification_owner)
            if make_owner:
                query = query.filter(OrderDelayTrackingSnapshot.make_owner == make_owner)
            if collection_owner:
                query = query.filter(OrderDelayTrackingSnapshot.collection_owner == collection_owner)
            
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

        return render_template('partials/_view_order_delay_tracking.html', 
                             rows=processed_rows, 
                             pagination=pagination, 
                             footer_totals=footer_totals)
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
        delay_bucket = request.args.get('delay_bucket') # 1-2, 3-4, 5-10, 10+
        
        query = OrderDelayTrackingSnapshot.query
        if classification_owner:
            query = query.filter_by(classification_owner=classification_owner)
        if make_owner:
            query = query.filter_by(make_owner=make_owner)
        if collection_owner:
            query = query.filter_by(collection_owner=collection_owner)
            
        if delay_bucket == '1-2':
            query = query.filter(OrderDelayTrackingSnapshot.delay_1_2_days > 0)
        elif delay_bucket == '3-4':
            query = query.filter(OrderDelayTrackingSnapshot.delay_3_4_days > 0)
        elif delay_bucket == '5-10':
            query = query.filter(OrderDelayTrackingSnapshot.delay_5_10_days > 0)
        elif delay_bucket == '10+':
            query = query.filter(OrderDelayTrackingSnapshot.delay_more_than_10_days > 0)
            
        details = query.all()
        
        return render_template('partials/_view_order_delay_tracking_details.html', details=details)
    except Exception as e:
        logger.error(f"Error in get_order_delay_tracking_details: {str(e)}")
        return f'Error: {str(e)}', 500
