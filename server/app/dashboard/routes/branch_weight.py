from flask import render_template, request, jsonify
from flask_jwt_extended import jwt_required
from app.dashboard import dashboard_bp
from app.models import Notification, LocationWiseStockSnapshot
from app.extensions import db
from sqlalchemy import func
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

def safe_float(val):
    try:
        return float(val or 0)
    except:
        return 0.0

@dashboard_bp.route('/branchweight')
def branch_weight_allocation():
    try:
        unread_count = Notification.query.filter_by(is_read=False).count()
        sync_time = datetime.now().strftime("%H:%M")

        # Fetch latest snapshot date (handle Nulls by using COALESCE or just checking if any data exists)
        has_any_data = db.session.query(LocationWiseStockSnapshot).first()
        if not has_any_data:
            return render_template('branch_weight_allocation.html', 
                                 unread_count=unread_count, 
                                 sync_time=sync_time, 
                                 stats={}, 
                                 rows=[], 
                                 pagination=None, 
                                 footer_totals={},
                                 current_level='zone')

        latest_date_query = db.session.query(func.max(LocationWiseStockSnapshot.snapshot_date)).scalar()
        
        # Filters
        search = request.args.get('search', '').strip()
        zone = request.args.get('zone', '')
        state = request.args.get('state', '')
        location = request.args.get('location', '')
        business_head = request.args.get('business_head', '')

        def apply_filters(query):
            if search:
                query = query.filter(LocationWiseStockSnapshot.location.ilike(f"%{search}%") | 
                                     LocationWiseStockSnapshot.zone.ilike(f"%{search}%") |
                                     LocationWiseStockSnapshot.state.ilike(f"%{search}%"))
            if zone:
                query = query.filter(LocationWiseStockSnapshot.zone == zone)
            if state:
                query = query.filter(LocationWiseStockSnapshot.state == state)
            if location:
                query = query.filter(LocationWiseStockSnapshot.location == location)
            if business_head:
                query = query.filter(LocationWiseStockSnapshot.business_head == business_head)
            
            # If latest_date_query is None, it means all rows are NULL date. 
            # If not None, we filter by it.
            if latest_date_query:
                query = query.filter(LocationWiseStockSnapshot.snapshot_date == latest_date_query)
            else:
                query = query.filter(LocationWiseStockSnapshot.snapshot_date.is_(None))
                
            return query

        # Global Stats
        agg_cols = [
            func.sum(LocationWiseStockSnapshot.provision_pieces).label('provision_pieces'),
            func.sum(LocationWiseStockSnapshot.provision_weight).label('provision_weight'),
            func.sum(LocationWiseStockSnapshot.stock_pieces).label('stock_pieces'),
            func.sum(LocationWiseStockSnapshot.stock_weight).label('stock_weight'),
            func.sum(LocationWiseStockSnapshot.short_pieces).label('short_pieces'),
            func.sum(LocationWiseStockSnapshot.short_weight).label('short_weight'),
            func.sum(LocationWiseStockSnapshot.max_weight_allocate_other_branches).label('max_allocate'),
            func.sum(LocationWiseStockSnapshot.max_refill_qty_other_branches).label('max_refill')
        ]
        
        agg_q = db.session.query(*agg_cols)
        agg_q = apply_filters(agg_q)
        aggs = agg_q.first()

        stats = {
            'provision_pieces': int(aggs.provision_pieces or 0),
            'provision_weight': safe_float(aggs.provision_weight),
            'stock_pieces': int(aggs.stock_pieces or 0),
            'stock_weight': safe_float(aggs.stock_weight),
            'short_pieces': int(aggs.short_pieces or 0),
            'short_weight': safe_float(aggs.short_weight),
            'max_allocate': safe_float(aggs.max_allocate),
            'max_refill': safe_float(aggs.max_refill)
        }

        footer_totals = stats
        
        # Drill-down level
        if not zone:
            group_cols = [LocationWiseStockSnapshot.zone]
            level = 'zone'
        elif zone and not state:
            group_cols = [LocationWiseStockSnapshot.zone, LocationWiseStockSnapshot.state]
            level = 'state'
        else:
            group_cols = [LocationWiseStockSnapshot.zone, LocationWiseStockSnapshot.state, LocationWiseStockSnapshot.location]
            level = 'location'

        main_q = db.session.query(*(group_cols + agg_cols))
        main_q = apply_filters(main_q)
        main_q = main_q.group_by(*group_cols).order_by(*group_cols)
        
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)
        pagination = main_q.paginate(page=page, per_page=per_page, error_out=False)
        
        processed_rows = []
        for r in pagination.items:
            row_dict = {
                'zone': r[0] or 'Unknown',
                'state': r[1] if level in ['state', 'location'] else '',
                'location': r[2] if level == 'location' else '',
                'provision_pieces': int(r.provision_pieces or 0),
                'provision_weight': safe_float(r.provision_weight),
                'stock_pieces': int(r.stock_pieces or 0),
                'stock_weight': safe_float(r.stock_weight),
                'short_pieces': int(r.short_pieces or 0),
                'short_weight': safe_float(r.short_weight),
                'max_allocate': safe_float(r.max_allocate),
                'max_refill': safe_float(r.max_refill),
                'level': level
            }
            if row_dict['state'] is None: row_dict['state'] = 'Unknown'
            if row_dict['location'] is None: row_dict['location'] = 'Unknown'
            processed_rows.append(row_dict)

        return render_template('branch_weight_allocation.html', 
                             unread_count=unread_count, 
                             sync_time=sync_time, 
                             stats=stats, 
                             rows=processed_rows, 
                             pagination=pagination, 
                             footer_totals=footer_totals,
                             current_level=level)
    except Exception as e:
        logger.error(f"Error in branch_weight_allocation: {str(e)}")
        return f"Error: {str(e)}", 500

@dashboard_bp.route('/api/branchweight/options')
@jwt_required()
def branch_weight_options():
    try:
        zone = request.args.get('zone')
        state = request.args.get('state')
        
        options = {
            'zones': [r[0] for r in db.session.query(LocationWiseStockSnapshot.zone.distinct()).order_by(LocationWiseStockSnapshot.zone).all() if r[0]],
            'states': [],
            'locations': [],
            'business_heads': [r[0] for r in db.session.query(LocationWiseStockSnapshot.business_head.distinct()).order_by(LocationWiseStockSnapshot.business_head).all() if r[0]]
        }
        
        if zone:
            options['states'] = [r[0] for r in db.session.query(LocationWiseStockSnapshot.state.distinct()).filter(LocationWiseStockSnapshot.zone == zone).order_by(LocationWiseStockSnapshot.state).all() if r[0]]
        else:
            options['states'] = [r[0] for r in db.session.query(LocationWiseStockSnapshot.state.distinct()).order_by(LocationWiseStockSnapshot.state).all() if r[0]]
            
        if state:
            options['locations'] = [r[0] for r in db.session.query(LocationWiseStockSnapshot.location.distinct()).filter(LocationWiseStockSnapshot.state == state).order_by(LocationWiseStockSnapshot.location).all() if r[0]]
        elif zone:
             options['locations'] = [r[0] for r in db.session.query(LocationWiseStockSnapshot.location.distinct()).filter(LocationWiseStockSnapshot.zone == zone).order_by(LocationWiseStockSnapshot.location).all() if r[0]]
        else:
            options['locations'] = [r[0] for r in db.session.query(LocationWiseStockSnapshot.location.distinct()).order_by(LocationWiseStockSnapshot.location).all() if r[0]]

        return jsonify(options)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@dashboard_bp.route('/partial/branch')
@jwt_required()
def get_branch_partial():
    try:
        latest_date_query = db.session.query(func.max(LocationWiseStockSnapshot.snapshot_date)).scalar()
        
        # If no data at all, return an empty template with 200
        has_any_data = db.session.query(LocationWiseStockSnapshot).first()
        if not has_any_data:
            return render_template('partials/_view_branch_weight.html', 
                                 rows=[], 
                                 pagination=None, 
                                 footer_totals={},
                                 stats={},
                                 current_level='zone')

        # Filters and Parent Info for Drill-down
        search = request.args.get('search', '').strip()
        zone = request.args.get('zone', '')
        state = request.args.get('state', '')
        location = request.args.get('location', '')
        business_head = request.args.get('business_head', '')
        
        # Tree-grid specific params
        parent_level = request.args.get('parent_level')
        parent_value = request.args.get('parent_value')
        grandparent_value = request.args.get('grandparent_value') # For state level, we might need zone

        def apply_filters(query):
            if search:
                query = query.filter(LocationWiseStockSnapshot.location.ilike(f"%{search}%") | 
                                     LocationWiseStockSnapshot.zone.ilike(f"%{search}%") |
                                     LocationWiseStockSnapshot.state.ilike(f"%{search}%"))
            if zone:
                query = query.filter(LocationWiseStockSnapshot.zone == zone)
            if state:
                query = query.filter(LocationWiseStockSnapshot.state == state)
            if location:
                query = query.filter(LocationWiseStockSnapshot.location == location)
            if business_head:
                query = query.filter(LocationWiseStockSnapshot.business_head == business_head)
            
            if latest_date_query:
                query = query.filter(LocationWiseStockSnapshot.snapshot_date == latest_date_query)
            else:
                query = query.filter(LocationWiseStockSnapshot.snapshot_date.is_(None))
                
            return query

        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)
        
        # Determine Grouping and Filtering based on Parent
        if parent_level == 'zone':
            # Expanding a Zone -> Show States
            group_cols = [LocationWiseStockSnapshot.zone, LocationWiseStockSnapshot.state]
            level = 'state'
            # Filter by the parent zone
            base_query = db.session.query(LocationWiseStockSnapshot).filter(LocationWiseStockSnapshot.zone == parent_value)
        elif parent_level == 'state':
            # Expanding a State -> Show Locations
            group_cols = [LocationWiseStockSnapshot.zone, LocationWiseStockSnapshot.state, LocationWiseStockSnapshot.location]
            level = 'location'
            # Filter by the parent state (and zone if provided for uniqueness)
            base_query = db.session.query(LocationWiseStockSnapshot).filter(LocationWiseStockSnapshot.state == parent_value)
            if grandparent_value:
                 base_query = base_query.filter(LocationWiseStockSnapshot.zone == grandparent_value)
        else:
            # Default Root Level (Zone Summary) unless filters dictate otherwise
            # Note: The original filter logic (zone/state/location args) still applies if used via sidebar
            base_query = db.session.query(LocationWiseStockSnapshot)
            if not zone:
                group_cols = [LocationWiseStockSnapshot.zone]
                level = 'zone'
            elif zone and not state:
                group_cols = [LocationWiseStockSnapshot.zone, LocationWiseStockSnapshot.state]
                level = 'state'
            else:
                group_cols = [LocationWiseStockSnapshot.zone, LocationWiseStockSnapshot.state, LocationWiseStockSnapshot.location]
                level = 'location'

        # Global Stats (Updated for filters - only relevant for full view, not child rows)
        agg_cols = [
            func.sum(LocationWiseStockSnapshot.provision_pieces).label('provision_pieces'),
            func.sum(LocationWiseStockSnapshot.provision_weight).label('provision_weight'),
            func.sum(LocationWiseStockSnapshot.stock_pieces).label('stock_pieces'),
            func.sum(LocationWiseStockSnapshot.stock_weight).label('stock_weight'),
            func.sum(LocationWiseStockSnapshot.short_pieces).label('short_pieces'),
            func.sum(LocationWiseStockSnapshot.short_weight).label('short_weight'),
            func.sum(LocationWiseStockSnapshot.max_weight_allocate_other_branches).label('max_allocate'),
            func.sum(LocationWiseStockSnapshot.max_refill_qty_other_branches).label('max_refill')
        ]
        
        # Calculate stats only if it's the main view (not child rows)
        stats = {}
        footer_totals = {}
        if not parent_level:
            agg_q = db.session.query(*agg_cols)
            agg_q = apply_filters(agg_q)
            aggs = agg_q.first()

            stats = {
                'provision_pieces': int(aggs.provision_pieces or 0),
                'provision_weight': safe_float(aggs.provision_weight),
                'stock_pieces': int(aggs.stock_pieces or 0),
                'stock_weight': safe_float(aggs.stock_weight),
                'short_pieces': int(aggs.short_pieces or 0),
                'short_weight': safe_float(aggs.short_weight),
                'max_allocate': safe_float(aggs.max_allocate),
                'max_refill': safe_float(aggs.max_refill)
            }
            footer_totals = stats

        # Main Query for Rows
        main_q = base_query.with_entities(*(group_cols + agg_cols))
        main_q = apply_filters(main_q)
        main_q = main_q.group_by(*group_cols).order_by(*group_cols)
        
        # Pagination (only for root level or if needed, but tree grid usually just shows all children or paginates them)
        # For simplicity, we'll paginate root, but maybe return all children? 
        # Let's keep pagination for now.
        pagination = main_q.paginate(page=page, per_page=per_page, error_out=False)

        processed_rows = []
        for r in pagination.items:
            row_dict = {
                'zone': r[0] or 'Unknown',
                'state': r[1] if level in ['state', 'location'] else '',
                'location': r[2] if level == 'location' else '',
                'provision_pieces': int(r.provision_pieces or 0),
                'provision_weight': safe_float(r.provision_weight),
                'stock_pieces': int(r.stock_pieces or 0),
                'stock_weight': safe_float(r.stock_weight),
                'short_pieces': int(r.short_pieces or 0),
                'short_weight': safe_float(r.short_weight),
                'max_allocate': safe_float(r.max_allocate),
                'max_refill': safe_float(r.max_refill),
                'level': level
            }
            if row_dict['state'] is None: row_dict['state'] = 'Unknown'
            if row_dict['location'] is None: row_dict['location'] = 'Unknown'
            processed_rows.append(row_dict)

        # If parent_level is set, we are returning child rows to be appended, not the full table.
        # We can use a special flag or a different template. 
        # Using the same template but passing is_child_rows=True to skip header/footer/table wrapper.
        is_child_rows = bool(parent_level)

        return render_template('partials/_view_branch_weight.html', 
                             rows=processed_rows, 
                             pagination=pagination if not is_child_rows else None, 
                             footer_totals=footer_totals,
                             stats=stats,
                             current_level=level,
                             is_child_rows=is_child_rows,
                             parent_level=parent_level,
                             parent_value=parent_value)
    except Exception as e:
        logger.error(f"Error in get_branch_partial: {str(e)}")
        return f'<div class="p-8 text-center text-red-500 font-bold">Backend Error: {str(e)}</div>', 200
