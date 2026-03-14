from flask import render_template, request, jsonify, send_file, abort, session
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.dashboard import dashboard_bp
from app.models import Notification, OutstandingPurchaseOrderStatusSnapshot, ExportDownloadLog
from app.extensions import db
from sqlalchemy import func, cast, Numeric
from datetime import datetime
import logging
from decimal import Decimal
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
    # Sort keys to ensure consistent order
    sorted_kwargs = dict(sorted(kwargs.items()))
    # Create a string representation of the arguments
    args_str = ":".join(f"{k}={v}" for k, v in sorted_kwargs.items() if v)
    
    # Format date string for the key
    date_str = snapshot_date.strftime("%Y%m%d%H%M%S") if snapshot_date else "latest"
    
    return f"{prefix}:{date_str}:{args_str}"

def safe_float(val):
    try:
        return float(val or 0)
    except:
        return 0.0

@dashboard_bp.route('/outstanding_purchase_orders')
def outstanding_purchase_order():
    try:
        unread_count = Notification.query.filter_by(is_read=False).count()
        sync_time = datetime.now().strftime("%H:%M")

        has_any_data = db.session.query(OutstandingPurchaseOrderStatusSnapshot.id).first()
        if not has_any_data:
            empty_stats = {
                'order_pieces': 0, 'order_weight': 0.0,
                'accepted_pieces': 0, 'accepted_weight': 0.0
            }
            return render_template('outstanding_purchase_order.html', 
                                 unread_count=unread_count, 
                                 sync_time=sync_time, 
                                 stats=empty_stats, 
                                 rows=[], 
                                 pagination=None, 
                                 footer_totals=empty_stats,
                                 current_level='classification_owner')

        latest_date_query = db.session.query(func.max(OutstandingPurchaseOrderStatusSnapshot.updated_at)).scalar()
        
        # Filters
        search = request.args.get('search', '').strip()
        classification_owner = request.args.get('classification_owner', '')
        make_owner = request.args.get('make_owner', '')
        collection_owner = request.args.get('collection_owner', '')
        purchase_ro = request.args.get('purchase_ro', '')
        party = request.args.get('party', '')
        classification = request.args.get('classification', '')
        make = request.args.get('make', '')
        collection = request.args.get('collection', '')
        section = request.args.get('section', '')
        division = request.args.get('division', '')
        group = request.args.get('group', '')
        purity = request.args.get('purity', '')
        age_min = request.args.get('age_min', type=int)
        age_max = request.args.get('age_max', type=int)
        exclude_receipt = request.args.get('exclude_receipt', 'false') == 'true'
        
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)

        cache_key = generate_cache_key('opo_main', latest_date_query, 
                                     search=search, classification_owner=classification_owner, make_owner=make_owner, collection_owner=collection_owner, 
                                     purchase_ro=purchase_ro, party=party, classification=classification, make=make, collection=collection, section=section,
                                     division=division, group=group, purity=purity, age_min=age_min, age_max=age_max,
                                     exclude_receipt=exclude_receipt,
                                     page=page, per_page=per_page)
        
        cached_data = redis_client.get(cache_key)
        if cached_data:
            logger.info(f"Cache HIT for {cache_key}")
            data = json.loads(cached_data)
            stats = data['stats']
            rows = data['rows']
            total = data['total']
            current_level = data['current_level']
            footer_totals = data['footer_totals']
            
            pagination = CachedPagination(rows, page, per_page, total)
            
            return render_template('outstanding_purchase_order.html', 
                                 unread_count=unread_count, 
                                 sync_time=sync_time, 
                                 stats=stats, 
                                 rows=rows, 
                                 pagination=pagination, 
                                 footer_totals=footer_totals,
                                 current_level=current_level)

        logger.info(f"Cache MISS for {cache_key}")

        def apply_filters(query):
            if search:
                query = query.filter(OutstandingPurchaseOrderStatusSnapshot.classification_owner.ilike(f"%{search}%") | 
                                     OutstandingPurchaseOrderStatusSnapshot.make_owner.ilike(f"%{search}%") |
                                     OutstandingPurchaseOrderStatusSnapshot.collection_owner.ilike(f"%{search}%") |
                                     OutstandingPurchaseOrderStatusSnapshot.party.ilike(f"%{search}%") |
                                     OutstandingPurchaseOrderStatusSnapshot.order_number.ilike(f"%{search}%"))
            if classification_owner:
                query = query.filter(OutstandingPurchaseOrderStatusSnapshot.classification_owner == classification_owner)
            if make_owner:
                query = query.filter(OutstandingPurchaseOrderStatusSnapshot.make_owner == make_owner)
            if collection_owner:
                query = query.filter(OutstandingPurchaseOrderStatusSnapshot.collection_owner == collection_owner)
            if purchase_ro:
                query = query.filter(OutstandingPurchaseOrderStatusSnapshot.purchase_ro == purchase_ro)
            if party:
                query = query.filter(OutstandingPurchaseOrderStatusSnapshot.party == party)
            if classification:
                query = query.filter(OutstandingPurchaseOrderStatusSnapshot.classification == classification)
            if make:
                query = query.filter(OutstandingPurchaseOrderStatusSnapshot.make == make)
            if collection:
                query = query.filter(OutstandingPurchaseOrderStatusSnapshot.collection == collection)
            if section:
                query = query.filter(OutstandingPurchaseOrderStatusSnapshot.section == section)
            if division:
                query = query.filter(OutstandingPurchaseOrderStatusSnapshot.division == division)
            if group:
                query = query.filter(OutstandingPurchaseOrderStatusSnapshot.group == group)
            if purity:
                query = query.filter(OutstandingPurchaseOrderStatusSnapshot.purity == purity)
            if age_min is not None:
                query = query.filter(func.current_date() - OutstandingPurchaseOrderStatusSnapshot.order_date >= age_min)
            if age_max is not None:
                query = query.filter(func.current_date() - OutstandingPurchaseOrderStatusSnapshot.order_date <= age_max)
            if exclude_receipt:
                query = query.filter(OutstandingPurchaseOrderStatusSnapshot.receipt_present != 'Y')
                
            return query

        # Global Stats
        agg_cols = [
            func.sum(cast(OutstandingPurchaseOrderStatusSnapshot.order_pieces, Numeric)).label('order_pieces'),
            func.sum(cast(OutstandingPurchaseOrderStatusSnapshot.order_weight, Numeric)).label('order_weight'),
            func.sum(cast(OutstandingPurchaseOrderStatusSnapshot.accepted_pieces, Numeric)).label('accepted_pieces'),
            func.sum(cast(OutstandingPurchaseOrderStatusSnapshot.accepted_weight, Numeric)).label('accepted_weight')
        ]
        
        agg_q = db.session.query(*agg_cols)
        agg_q = apply_filters(agg_q)
        aggs = agg_q.first()

        if not aggs or aggs.order_pieces is None:
             stats = {
                'order_pieces': 0, 'order_weight': 0.0,
                'accepted_pieces': 0, 'accepted_weight': 0.0
            }
        else:
            stats = {
                'order_pieces': int(aggs.order_pieces or 0),
                'order_weight': safe_float(aggs.order_weight),
                'accepted_pieces': int(aggs.accepted_pieces or 0),
                'accepted_weight': safe_float(aggs.accepted_weight)
            }

        footer_totals = stats
        
        # Drill-down level
        if not classification_owner:
            group_cols = [OutstandingPurchaseOrderStatusSnapshot.classification_owner]
            level = 'classification_owner'
        elif classification_owner and not make_owner:
            group_cols = [OutstandingPurchaseOrderStatusSnapshot.classification_owner, OutstandingPurchaseOrderStatusSnapshot.make_owner]
            level = 'make_owner'
        else:
            group_cols = [OutstandingPurchaseOrderStatusSnapshot.classification_owner, OutstandingPurchaseOrderStatusSnapshot.make_owner, OutstandingPurchaseOrderStatusSnapshot.collection_owner]
            level = 'collection_owner'

        main_q = db.session.query(*(group_cols + agg_cols))
        main_q = apply_filters(main_q)
        main_q = main_q.group_by(*group_cols).order_by(*group_cols)
        
        pagination = main_q.paginate(page=page, per_page=per_page, error_out=False)
        
        processed_rows = []
        for r in pagination.items:
            row_dict = {
                'classification_owner': r[0] or 'Unknown',
                'make_owner': r[1] if level in ['make_owner', 'collection_owner'] else '',
                'collection_owner': r[2] if level == 'collection_owner' else '',
                'order_pieces': int(r.order_pieces or 0),
                'order_weight': safe_float(r.order_weight),
                'accepted_pieces': int(r.accepted_pieces or 0),
                'accepted_weight': safe_float(r.accepted_weight),
                'level': level
            }
            if row_dict['make_owner'] is None: row_dict['make_owner'] = 'Unknown'
            if row_dict['collection_owner'] is None: row_dict['collection_owner'] = 'Unknown'
            processed_rows.append(row_dict)

        cache_payload = {
            'stats': stats,
            'rows': processed_rows,
            'total': pagination.total,
            'current_level': level,
            'footer_totals': footer_totals
        }
        redis_client.setex(cache_key, 3600, json.dumps(cache_payload))

        return render_template('outstanding_purchase_order.html', 
                             unread_count=unread_count, 
                             sync_time=sync_time, 
                             stats=stats, 
                             rows=processed_rows, 
                             pagination=pagination, 
                             footer_totals=footer_totals,
                             current_level=level)
    except Exception as e:
        logger.error(f"Error in outstanding_purchase_order: {str(e)}")
        return f"Error: {str(e)}", 500

@dashboard_bp.route('/api/outstanding_orders/options')
@jwt_required()
def outstanding_orders_options():
    try:
        classification_owner = request.args.get('classification_owner')
        make_owner = request.args.get('make_owner')
        
        options = {
            'purchase_ros': [r[0] for r in db.session.query(OutstandingPurchaseOrderStatusSnapshot.purchase_ro.distinct()).order_by(OutstandingPurchaseOrderStatusSnapshot.purchase_ro).all() if r[0]],
            'parties': [r[0] for r in db.session.query(OutstandingPurchaseOrderStatusSnapshot.party.distinct()).order_by(OutstandingPurchaseOrderStatusSnapshot.party).all() if r[0]],
            'classifications': [r[0] for r in db.session.query(OutstandingPurchaseOrderStatusSnapshot.classification.distinct()).order_by(OutstandingPurchaseOrderStatusSnapshot.classification).all() if r[0]],
            'makes': [r[0] for r in db.session.query(OutstandingPurchaseOrderStatusSnapshot.make.distinct()).order_by(OutstandingPurchaseOrderStatusSnapshot.make).all() if r[0]],
            'collections': [r[0] for r in db.session.query(OutstandingPurchaseOrderStatusSnapshot.collection.distinct()).order_by(OutstandingPurchaseOrderStatusSnapshot.collection).all() if r[0]],
            'sections': [r[0] for r in db.session.query(OutstandingPurchaseOrderStatusSnapshot.section.distinct()).order_by(OutstandingPurchaseOrderStatusSnapshot.section).all() if r[0]],
            'divisions': [r[0] for r in db.session.query(OutstandingPurchaseOrderStatusSnapshot.division.distinct()).order_by(OutstandingPurchaseOrderStatusSnapshot.division).all() if r[0]],
            'groups': [r[0] for r in db.session.query(OutstandingPurchaseOrderStatusSnapshot.group.distinct()).order_by(OutstandingPurchaseOrderStatusSnapshot.group).all() if r[0]],
            'purities': [r[0] for r in db.session.query(OutstandingPurchaseOrderStatusSnapshot.purity.distinct()).order_by(OutstandingPurchaseOrderStatusSnapshot.purity).all() if r[0]],
            
            'classification_owners': [r[0] for r in db.session.query(OutstandingPurchaseOrderStatusSnapshot.classification_owner.distinct()).order_by(OutstandingPurchaseOrderStatusSnapshot.classification_owner).all() if r[0]],
            'make_owners': [],
            'collection_owners': []
        }
        
        if classification_owner:
            options['make_owners'] = [r[0] for r in db.session.query(OutstandingPurchaseOrderStatusSnapshot.make_owner.distinct()).filter(OutstandingPurchaseOrderStatusSnapshot.classification_owner == classification_owner).order_by(OutstandingPurchaseOrderStatusSnapshot.make_owner).all() if r[0]]
        else:
            options['make_owners'] = [r[0] for r in db.session.query(OutstandingPurchaseOrderStatusSnapshot.make_owner.distinct()).order_by(OutstandingPurchaseOrderStatusSnapshot.make_owner).all() if r[0]]

            
        if make_owner:
            options['collection_owners'] = [r[0] for r in db.session.query(OutstandingPurchaseOrderStatusSnapshot.collection_owner.distinct()).filter(OutstandingPurchaseOrderStatusSnapshot.make_owner == make_owner).order_by(OutstandingPurchaseOrderStatusSnapshot.collection_owner).all() if r[0]]
        elif classification_owner:
             options['collection_owners'] = [r[0] for r in db.session.query(OutstandingPurchaseOrderStatusSnapshot.collection_owner.distinct()).filter(OutstandingPurchaseOrderStatusSnapshot.classification_owner == classification_owner).order_by(OutstandingPurchaseOrderStatusSnapshot.collection_owner).all() if r[0]]
        else:
            options['collection_owners'] = [r[0] for r in db.session.query(OutstandingPurchaseOrderStatusSnapshot.collection_owner.distinct()).order_by(OutstandingPurchaseOrderStatusSnapshot.collection_owner).all() if r[0]]

        return jsonify(options)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@dashboard_bp.route('/partial/outstanding_orders')
@jwt_required()
def get_outstanding_orders_partial():
    try:
        latest_date_query = db.session.query(func.max(OutstandingPurchaseOrderStatusSnapshot.updated_at)).scalar()
        
        has_any_data = db.session.query(OutstandingPurchaseOrderStatusSnapshot.id).first()
        if not has_any_data:
            empty_stats = {
                'order_pieces': 0, 'order_weight': 0.0,
                'accepted_pieces': 0, 'accepted_weight': 0.0
            }
            return render_template('partials/_view_outstanding_purchase_order.html', 
                                 rows=[], 
                                 pagination=None, 
                                 footer_totals=empty_stats,
                                 stats=empty_stats,
                                 current_level='classification_owner')

        search = request.args.get('search', '').strip()
        classification_owner = request.args.get('classification_owner', '')
        make_owner = request.args.get('make_owner', '')
        collection_owner = request.args.get('collection_owner', '')
        purchase_ro = request.args.get('purchase_ro', '')
        party = request.args.get('party', '')
        classification = request.args.get('classification', '')
        make = request.args.get('make', '')
        collection = request.args.get('collection', '')
        section = request.args.get('section', '')
        division = request.args.get('division', '')
        group = request.args.get('group', '')
        purity = request.args.get('purity', '')
        age_min = request.args.get('age_min', type=int)
        age_max = request.args.get('age_max', type=int)
        exclude_receipt = request.args.get('exclude_receipt', 'false') == 'true'
        
        parent_level = request.args.get('parent_level')

        parent_value = request.args.get('parent_value')
        grandparent_value = request.args.get('grandparent_value')

        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)
        
        cache_key = generate_cache_key('opo_partial', latest_date_query, 
                                     search=search, classification_owner=classification_owner, make_owner=make_owner, collection_owner=collection_owner, 
                                     purchase_ro=purchase_ro, party=party, classification=classification, make=make, collection=collection, section=section,
                                     division=division, group=group, purity=purity, age_min=age_min, age_max=age_max,
                                     exclude_receipt=exclude_receipt,
                                     parent_level=parent_level, 
                                     parent_value=parent_value, grandparent_value=grandparent_value,
                                     page=page, per_page=per_page)
        
        is_child_rows = bool(parent_level)
        
        cached_data = redis_client.get(cache_key)
        if cached_data:
             logger.info(f"Cache HIT for {cache_key}")
             data = json.loads(cached_data)
             
             if not is_child_rows:
                 pagination = CachedPagination(data['rows'], page, per_page, data['total'])
             else:
                 pagination = None
             
             return render_template('partials/_view_outstanding_purchase_order.html', 
                              rows=data['rows'], 
                              pagination=pagination, 
                              footer_totals=data['footer_totals'],
                              stats=data['stats'],
                              current_level=data['current_level'],
                              is_child_rows=is_child_rows,
                              parent_level=parent_level,
                              parent_value=parent_value)

        logger.info(f"Cache MISS for {cache_key}")

        def apply_filters(query):
            if search:
                query = query.filter(OutstandingPurchaseOrderStatusSnapshot.classification_owner.ilike(f"%{search}%") | 
                                     OutstandingPurchaseOrderStatusSnapshot.make_owner.ilike(f"%{search}%") |
                                     OutstandingPurchaseOrderStatusSnapshot.collection_owner.ilike(f"%{search}%") |
                                     OutstandingPurchaseOrderStatusSnapshot.party.ilike(f"%{search}%") |
                                     OutstandingPurchaseOrderStatusSnapshot.order_number.ilike(f"%{search}%"))
            if classification_owner:
                query = query.filter(OutstandingPurchaseOrderStatusSnapshot.classification_owner == classification_owner)
            if make_owner:
                query = query.filter(OutstandingPurchaseOrderStatusSnapshot.make_owner == make_owner)
            if collection_owner:
                query = query.filter(OutstandingPurchaseOrderStatusSnapshot.collection_owner == collection_owner)
            if purchase_ro:
                query = query.filter(OutstandingPurchaseOrderStatusSnapshot.purchase_ro == purchase_ro)
            if party:
                query = query.filter(OutstandingPurchaseOrderStatusSnapshot.party == party)
            if classification:
                query = query.filter(OutstandingPurchaseOrderStatusSnapshot.classification == classification)
            if make:
                query = query.filter(OutstandingPurchaseOrderStatusSnapshot.make == make)
            if collection:
                query = query.filter(OutstandingPurchaseOrderStatusSnapshot.collection == collection)
            if section:
                query = query.filter(OutstandingPurchaseOrderStatusSnapshot.section == section)
            if division:
                query = query.filter(OutstandingPurchaseOrderStatusSnapshot.division == division)
            if group:
                query = query.filter(OutstandingPurchaseOrderStatusSnapshot.group == group)
            if purity:
                query = query.filter(OutstandingPurchaseOrderStatusSnapshot.purity == purity)
            if age_min is not None:
                query = query.filter(func.current_date() - OutstandingPurchaseOrderStatusSnapshot.order_date >= age_min)
            if age_max is not None:
                query = query.filter(func.current_date() - OutstandingPurchaseOrderStatusSnapshot.order_date <= age_max)
            if exclude_receipt:
                query = query.filter(OutstandingPurchaseOrderStatusSnapshot.receipt_present != 'Y')
                
            return query

        if parent_level == 'classification_owner':
            group_cols = [OutstandingPurchaseOrderStatusSnapshot.classification_owner, OutstandingPurchaseOrderStatusSnapshot.make_owner]
            level = 'make_owner'
            base_query = db.session.query(OutstandingPurchaseOrderStatusSnapshot).filter(OutstandingPurchaseOrderStatusSnapshot.classification_owner == parent_value)
        elif parent_level == 'make_owner':
            group_cols = [OutstandingPurchaseOrderStatusSnapshot.classification_owner, OutstandingPurchaseOrderStatusSnapshot.make_owner, OutstandingPurchaseOrderStatusSnapshot.collection_owner]
            level = 'collection_owner'
            base_query = db.session.query(OutstandingPurchaseOrderStatusSnapshot).filter(OutstandingPurchaseOrderStatusSnapshot.make_owner == parent_value)
            if grandparent_value:
                 base_query = base_query.filter(OutstandingPurchaseOrderStatusSnapshot.classification_owner == grandparent_value)
        else:
            base_query = db.session.query(OutstandingPurchaseOrderStatusSnapshot)
            if not classification_owner:
                group_cols = [OutstandingPurchaseOrderStatusSnapshot.classification_owner]
                level = 'classification_owner'
            elif classification_owner and not make_owner:
                group_cols = [OutstandingPurchaseOrderStatusSnapshot.classification_owner, OutstandingPurchaseOrderStatusSnapshot.make_owner]
                level = 'make_owner'
            else:
                group_cols = [OutstandingPurchaseOrderStatusSnapshot.classification_owner, OutstandingPurchaseOrderStatusSnapshot.make_owner, OutstandingPurchaseOrderStatusSnapshot.collection_owner]
                level = 'collection_owner'

        agg_cols = [
            func.sum(cast(OutstandingPurchaseOrderStatusSnapshot.order_pieces, Numeric)).label('order_pieces'),
            func.sum(cast(OutstandingPurchaseOrderStatusSnapshot.order_weight, Numeric)).label('order_weight'),
            func.sum(cast(OutstandingPurchaseOrderStatusSnapshot.accepted_pieces, Numeric)).label('accepted_pieces'),
            func.sum(cast(OutstandingPurchaseOrderStatusSnapshot.accepted_weight, Numeric)).label('accepted_weight')
        ]
        
        stats = {}
        footer_totals = {}
        if not parent_level:
            agg_q = db.session.query(*agg_cols)
            agg_q = apply_filters(agg_q)
            aggs = agg_q.first()

            if not aggs or aggs.order_pieces is None:
                stats = {
                    'order_pieces': 0, 'order_weight': 0.0,
                    'accepted_pieces': 0, 'accepted_weight': 0.0
                }
            else:
                stats = {
                    'order_pieces': int(aggs.order_pieces or 0),
                    'order_weight': safe_float(aggs.order_weight),
                    'accepted_pieces': int(aggs.accepted_pieces or 0),
                    'accepted_weight': safe_float(aggs.accepted_weight)
                }
            footer_totals = stats

        main_q = base_query.with_entities(*(group_cols + agg_cols))
        main_q = apply_filters(main_q)
        main_q = main_q.group_by(*group_cols).order_by(*group_cols)
        
        pagination = main_q.paginate(page=page, per_page=per_page, error_out=False)

        processed_rows = []
        for r in pagination.items:
            row_dict = {
                'classification_owner': r[0] or 'Unknown',
                'make_owner': r[1] if level in ['make_owner', 'collection_owner'] else '',
                'collection_owner': r[2] if level == 'collection_owner' else '',
                'order_pieces': int(r.order_pieces or 0),
                'order_weight': safe_float(r.order_weight),
                'accepted_pieces': int(r.accepted_pieces or 0),
                'accepted_weight': safe_float(r.accepted_weight),
                'level': level
            }
            if row_dict['make_owner'] is None: row_dict['make_owner'] = 'Unknown'
            if row_dict['collection_owner'] is None: row_dict['collection_owner'] = 'Unknown'
            processed_rows.append(row_dict)

        cache_payload = {
            'rows': processed_rows,
            'total': pagination.total,
            'footer_totals': footer_totals,
            'stats': stats,
            'current_level': level
        }
        redis_client.setex(cache_key, 3600, json.dumps(cache_payload))

        return render_template('partials/_view_outstanding_purchase_order.html', 
                             rows=processed_rows, 
                             pagination=pagination if not is_child_rows else None, 
                             footer_totals=footer_totals,
                             stats=stats,
                             current_level=level,
                             is_child_rows=is_child_rows,
                             parent_level=parent_level,
                             parent_value=parent_value)
    except Exception as e:
        logger.error(f"Error in get_outstanding_orders_partial: {str(e)}")
        return f'<div class="p-8 text-center text-red-500 font-bold">Backend Error: {str(e)}</div>', 200

@dashboard_bp.route('/api/outstanding_orders/details')
@jwt_required()
def get_outstanding_orders_details():
    try:
        classification_owner = request.args.get('classification_owner')
        make_owner = request.args.get('make_owner')
        collection_owner = request.args.get('collection_owner')
        
        # Core Filters
        search = request.args.get('search', '').strip()
        purchase_ro = request.args.get('purchase_ro', '')
        party = request.args.get('party', '')
        classification = request.args.get('classification', '')
        make = request.args.get('make', '')
        collection = request.args.get('collection', '')
        section = request.args.get('section', '')
        division = request.args.get('division', '')
        group = request.args.get('group', '')
        purity = request.args.get('purity', '')
        age_min = request.args.get('age_min', type=int)
        age_max = request.args.get('age_max', type=int)
        exclude_receipt = request.args.get('exclude_receipt', 'false') == 'true'

        def apply_filters(query):
            if search:
                query = query.filter(OutstandingPurchaseOrderStatusSnapshot.classification_owner.ilike(f"%{search}%") | 
                                     OutstandingPurchaseOrderStatusSnapshot.make_owner.ilike(f"%{search}%") |
                                     OutstandingPurchaseOrderStatusSnapshot.collection_owner.ilike(f"%{search}%") |
                                     OutstandingPurchaseOrderStatusSnapshot.party.ilike(f"%{search}%") |
                                     OutstandingPurchaseOrderStatusSnapshot.order_number.ilike(f"%{search}%"))
            if purchase_ro:
                query = query.filter(OutstandingPurchaseOrderStatusSnapshot.purchase_ro == purchase_ro)
            if party:
                query = query.filter(OutstandingPurchaseOrderStatusSnapshot.party == party)
            if classification:
                query = query.filter(OutstandingPurchaseOrderStatusSnapshot.classification == classification)
            if make:
                query = query.filter(OutstandingPurchaseOrderStatusSnapshot.make == make)
            if collection:
                query = query.filter(OutstandingPurchaseOrderStatusSnapshot.collection == collection)
            if section:
                query = query.filter(OutstandingPurchaseOrderStatusSnapshot.section == section)
            if division:
                query = query.filter(OutstandingPurchaseOrderStatusSnapshot.division == division)
            if group:
                query = query.filter(OutstandingPurchaseOrderStatusSnapshot.group == group)
            if purity:
                query = query.filter(OutstandingPurchaseOrderStatusSnapshot.purity == purity)
            if age_min is not None:
                query = query.filter(func.current_date() - OutstandingPurchaseOrderStatusSnapshot.order_date >= age_min)
            if age_max is not None:
                query = query.filter(func.current_date() - OutstandingPurchaseOrderStatusSnapshot.order_date <= age_max)
            if exclude_receipt:
                query = query.filter(OutstandingPurchaseOrderStatusSnapshot.receipt_present != 'Y')
            return query

        if not classification_owner or not make_owner or not collection_owner:
            return '<div class="p-4 text-center text-red-500">Missing grouping parameters</div>', 400
            
        q = OutstandingPurchaseOrderStatusSnapshot.query.filter_by(
            classification_owner=classification_owner,
            make_owner=make_owner,
            collection_owner=collection_owner
        )
        q = apply_filters(q)
        details = q.all()
        
        return render_template('partials/_view_outstanding_order_details.html', 
                               details=details, 
                               classification_owner=classification_owner,
                               make_owner=make_owner,
                               collection_owner=collection_owner)
    except Exception as e:
        logger.error(f"Error in get_outstanding_orders_details: {str(e)}")
        return f'<div class="p-4 text-center text-red-500">Error: {str(e)}</div>', 200


@dashboard_bp.route('/api/outstanding_orders/export', methods=['POST'])
@jwt_required()
def queue_outstanding_orders_export():
    """Enqueue a background Excel export job for the current filter state."""
    try:
        data = request.get_json(force=True) or {}
        filters = data.get('filters', {})

        socket_id = data.get('socket_id')
        user_id = get_jwt_identity()
        job_payload = json.dumps({
            'type': 'export_opo',
            'filters': filters,
            'socket_id': socket_id,
            'user_id': user_id
        })
        redis_client.rpush('export_queue', job_payload)

        logger.info(f"Queued export_opo job with filters: {filters}")
        return jsonify({
            'status': 'queued',
            'message': 'Export job enqueued. You will be notified when the file is ready.'
        }), 202
    except Exception as e:
        logger.error(f"Error queuing export: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@dashboard_bp.route('/exports/download/<path:filename>')
def download_export_file(filename):
    """Serve a generated export file for download with logging."""
    import os
    from datetime import datetime
    
    # Consistent path to exports directory
    if os.path.isdir('/app/uploads'):
        exports_dir = '/app/uploads/exports'
    else:
        exports_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
            'uploads', 'exports'
        )
    filepath = os.path.join(exports_dir, filename)

    # 1. Existence Check
    if not os.path.exists(filepath) or not os.path.isfile(filepath):
        logger.warning(f"Download attempt for non-existent file: {filename}")
        abort(404)

    # 2. Logging
    try:
        log_entry = ExportDownloadLog(
            filename=filename,
            username=session.get('username'),
            user_id=session.get('user_id'),
            ip_address=request.remote_addr,
            user_agent=request.user_agent.string,
            downloaded_at=datetime.utcnow()
        )
        db.session.add(log_entry)
        db.session.commit()
        logger.info(f"Download logged: {filename} by user {session.get('username')}")
    except Exception as e:
        db.session.rollback()
        logger.error(f"Failed to log download for {filename}: {str(e)}")
        # We still serve the file even if logging fails, but we've recorded the error

    # 3. Deliver File
    return send_file(
        filepath,
        as_attachment=True,
        download_name=filename,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
