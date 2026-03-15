from flask import render_template, request, jsonify
from flask_jwt_extended import jwt_required
from app.dashboard import dashboard_bp
from app.models import Notification, LocationWiseStockSnapshot
from app.extensions import db
from sqlalchemy import func
from datetime import datetime
from zoneinfo import ZoneInfo

@dashboard_bp.route('/branchstockprovision')
def branch_stock_provision():
    unread_count = Notification.query.filter_by(is_read=False).count()
    sync_time = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%I:%M %p")

    return render_template('branch_stock_provision.html', 
                         unread_count=unread_count, 
                         sync_time=sync_time)

@dashboard_bp.route('/api/branchstockprovision/options')
def branch_stock_provision_options():
    # Helper to get distinct values efficiently
    def get_distinct(column):
        return [r[0] for r in db.session.query(column.distinct()).order_by(column).all() if r[0]]

    options = {
        'location': get_distinct(LocationWiseStockSnapshot.location),
        'zone': get_distinct(LocationWiseStockSnapshot.zone),
        'state': get_distinct(LocationWiseStockSnapshot.state),
        'business_head': get_distinct(LocationWiseStockSnapshot.business_head)
    }
    return jsonify(options)

@dashboard_bp.route('/partial/allocated_barcodes')
def get_allocated_barcodes_partial():
    # Filters
    search = request.args.get('search', '').strip()
    location = request.args.get('location', '')
    zone = request.args.get('zone', '')
    state = request.args.get('state', '')
    business_head = request.args.get('business_head', '')

    filters = []
    if search:
        filters.append(LocationWiseStockSnapshot.location.ilike(f"%{search}%") | 
                      LocationWiseStockSnapshot.zone.ilike(f"%{search}%") |
                      LocationWiseStockSnapshot.state.ilike(f"%{search}%"))
        
    if location:
        filters.append(LocationWiseStockSnapshot.location == location)
    if zone:
        filters.append(LocationWiseStockSnapshot.zone == zone)
    if state:
        filters.append(LocationWiseStockSnapshot.state == state)
    if business_head:
        filters.append(LocationWiseStockSnapshot.business_head == business_head)

    query = LocationWiseStockSnapshot.query.filter(*filters)

    # Sort by location
    query = query.order_by(LocationWiseStockSnapshot.location)

    # Aggregations for summary stats
    agg_cols = [
        func.sum(LocationWiseStockSnapshot.provision_pieces).label('provision_pieces'),
        func.sum(LocationWiseStockSnapshot.provision_weight).label('provision_weight'),
        func.sum(LocationWiseStockSnapshot.stock_pieces).label('stock_pieces'),
        func.sum(LocationWiseStockSnapshot.stock_weight).label('stock_weight'),
        func.sum(LocationWiseStockSnapshot.short_pieces).label('short_pieces'),
        func.sum(LocationWiseStockSnapshot.short_weight).label('short_weight'),
        func.sum(LocationWiseStockSnapshot.excess_not_in_provision_pieces).label('excess_pieces'),
        func.sum(LocationWiseStockSnapshot.excess_not_in_provision_weight).label('excess_weight'),
        func.count(db.distinct(LocationWiseStockSnapshot.location)).label('total_locations')
    ]
    
    aggs = db.session.query(*agg_cols).filter(*filters).first()
    
    total_items = (aggs.provision_pieces or 0) if aggs else 0
    total_weight = (aggs.provision_weight or 0) if aggs else 0
    stock_items = (aggs.stock_pieces or 0) if aggs else 0
    stock_weight = (aggs.stock_weight or 0) if aggs else 0
    short_items = (aggs.short_pieces or 0) if aggs else 0
    short_weight = (aggs.short_weight or 0) if aggs else 0
    excess_items = (aggs.excess_pieces or 0) if aggs else 0
    excess_weight = (aggs.excess_weight or 0) if aggs else 0
    total_locations = (aggs.total_locations or 0) if aggs else 0
    
    # Calculate derived metrics
    fulfillment_rate = (stock_items / total_items * 100) if total_items > 0 else 0
    avg_provision_weight = (total_weight / total_items) if total_items > 0 else 0
    avg_stock_weight = (stock_weight / stock_items) if stock_items > 0 else 0
    short_percentage = (short_items / total_items * 100) if total_items > 0 else 0
    
    # Calculate coverage score (locations with stock / total locations)
    locations_with_stock = db.session.query(
        func.count(db.distinct(LocationWiseStockSnapshot.location))
    ).filter(
        *filters,
        LocationWiseStockSnapshot.stock_pieces > 0
    ).scalar() or 0
    
    coverage_score = (locations_with_stock / total_locations * 100) if total_locations > 0 else 0
    
    stats = {
        # Primary metrics
        'provision_pieces': f"{total_items:,}",
        'provision_weight': f"{float(total_weight):.3f}",
        'stock_pieces': f"{stock_items:,}",
        'stock_weight': f"{float(stock_weight):.3f}",
        'short_pieces': f"{short_items:,}",
        'short_weight': f"{float(short_weight):.3f}",
        'excess_pieces': f"{excess_items:,}",
        'excess_weight': f"{float(excess_weight):.3f}",
        'total_locations': total_locations,
        
        # Calculated metrics
        'fulfillment_rate': f"{fulfillment_rate:.1f}",
        'avg_provision_weight': f"{avg_provision_weight:.3f}",
        'avg_stock_weight': f"{avg_stock_weight:.3f}",
        'short_percentage': f"{short_percentage:.1f}",
        'coverage_score': f"{coverage_score:.1f}",
        
        # Mapping for summary updates
        'total_items': f"{total_items:,}",
        'total_weight': f"{float(total_weight):.3f}",
        'unique_types': f"{total_locations:,}",
        'avg_weight': f"{avg_provision_weight:.3f}",
        'source_branches': f"{stock_items:,}",
        'target_branches': f"{float(stock_weight):.3f}",
        'health_index': f"{min(100, fulfillment_rate):.0f}%"
    }

    # Pagination
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return render_template('partials/_view_branch_stock_all_columns.html', 
                         rows=pagination.items, 
                         pagination=pagination,
                         stats=stats)
