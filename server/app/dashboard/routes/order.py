from flask import render_template, request, jsonify
from flask_jwt_extended import jwt_required
from app.dashboard import dashboard_bp
from app.models import Notification, OrderStatusReportSnapshot
from app.extensions import db
from sqlalchemy import func
from datetime import datetime

@dashboard_bp.route('/orderstatus')
def order_status():
    unread_count = Notification.query.filter_by(is_read=False).count()
    sync_time = datetime.now().strftime("%H:%M")

    # Fetch latest snapshot date
    latest_date_query = db.session.query(func.max(OrderStatusReportSnapshot.snapshot_date)).scalar()
    
    if not latest_date_query:
        return render_template('order_status.html', 
                             unread_count=unread_count, 
                             sync_time=sync_time, 
                             stats={}, 
                             rows=[], 
                             pagination=None, 
                             footer_totals={})

    # Filters
    search = request.args.get('search', '').strip()
    division = request.args.get('division', '')
    group = request.args.get('group', '')
    purity = request.args.get('purity', '')
    classification = request.args.get('classification', '')
    make = request.args.get('make', '')
    collection = request.args.get('collection', '')
    party = request.args.get('party', '')
    
    # New Owner Filters
    make_owner = request.args.get('make_owner', '')
    collection_owner = request.args.get('collection_owner', '')
    classification_owner = request.args.get('classification_owner', '')
    business_head = request.args.get('business_head', '')

    def apply_filters(query):
        if search:
            query = query.filter(OrderStatusReportSnapshot.hierarchy_key.ilike(f"%{search}%"))
        if division:
            query = query.filter(OrderStatusReportSnapshot.division == division)
        if group:
            query = query.filter(OrderStatusReportSnapshot.group_name == group)
        if purity:
            query = query.filter(OrderStatusReportSnapshot.purity == purity)
        if classification:
            query = query.filter(OrderStatusReportSnapshot.classification == classification)
        if make:
            query = query.filter(OrderStatusReportSnapshot.make_location == make)
        if collection:
            query = query.filter(OrderStatusReportSnapshot.collection == collection)
        if party:
            query = query.filter(OrderStatusReportSnapshot.party_name == party)
            
        # Apply New Owner Filters
        if make_owner:
            query = query.filter(OrderStatusReportSnapshot.make_owner == make_owner)
        if collection_owner:
            query = query.filter(OrderStatusReportSnapshot.collection_owner == collection_owner)
        if classification_owner:
            query = query.filter(OrderStatusReportSnapshot.classification_owner == classification_owner)
        if business_head:
            query = query.filter(OrderStatusReportSnapshot.business_head == business_head)
            
        return query

    # Global Stats
    agg_q = db.session.query(
        func.sum(OrderStatusReportSnapshot.total_count).label('total_orders'),
        func.sum(OrderStatusReportSnapshot.dispatched_count).label('dispatched'),
        func.sum(OrderStatusReportSnapshot.in_process_count).label('in_process'),
        func.sum(OrderStatusReportSnapshot.delayed_count).label('delayed'),
        func.sum(OrderStatusReportSnapshot.active_slots).label('active_slots'),
        func.avg(OrderStatusReportSnapshot.sla_index_pct).label('sla_index'),
        func.avg(OrderStatusReportSnapshot.avg_quality_score).label('quality_score'),
        func.avg(OrderStatusReportSnapshot.fulfillment_pct).label('fulfillment')
    ).filter(OrderStatusReportSnapshot.snapshot_date == latest_date_query)
    
    agg_q = apply_filters(agg_q)
    aggs = agg_q.first()

    stats = {
        'total_orders': f"{aggs.total_orders or 0:,}",
        'dispatched': f"{aggs.dispatched or 0:,}",
        'in_process': f"{aggs.in_process or 0:,}",
        'delayed': f"{aggs.delayed or 0:,}",
        'active_slots': f"{aggs.active_slots or 0:,}",
        'sla_index': f"{round(aggs.sla_index or 0, 1)}%",
        'quality_score': f"{round(aggs.quality_score or 0, 1)}/5",
        'fulfillment': f"{int(aggs.fulfillment or 0)}%"
    }

    # Footer Totals
    footer_q = db.session.query(
        func.sum(OrderStatusReportSnapshot.a_completed_count + OrderStatusReportSnapshot.a_pending_count).label('a'),
        func.sum(OrderStatusReportSnapshot.b_completed_count + OrderStatusReportSnapshot.b_pending_count).label('b'),
        func.sum(OrderStatusReportSnapshot.c_completed_count + OrderStatusReportSnapshot.c_pending_count).label('c'),
        func.sum(OrderStatusReportSnapshot.d_completed_count + OrderStatusReportSnapshot.d_pending_count).label('d'),
        func.sum(OrderStatusReportSnapshot.e_completed_count + OrderStatusReportSnapshot.e_pending_count).label('e'),
        func.sum(OrderStatusReportSnapshot.f_completed_count + OrderStatusReportSnapshot.f_pending_count).label('f'),
        func.sum(OrderStatusReportSnapshot.g_completed_count + OrderStatusReportSnapshot.g_pending_count).label('g'),
        func.sum(OrderStatusReportSnapshot.total_count).label('total')
    ).filter(OrderStatusReportSnapshot.snapshot_date == latest_date_query)
    
    footer_q = apply_filters(footer_q)
    footer_aggs = footer_q.first()

    footer_totals = {
        'a': f"{footer_aggs.a or 0:,}", 'b': f"{footer_aggs.b or 0:,}", 'c': f"{footer_aggs.c or 0:,}",
        'd': f"{footer_aggs.d or 0:,}", 'e': f"{footer_aggs.e or 0:,}", 'f': f"{footer_aggs.f or 0:,}",
        'g': f"{footer_aggs.g or 0:,}", 'total': f"{footer_aggs.total or 0:,}"
    }
    
    # Pagination
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    
    main_q = OrderStatusReportSnapshot.query.filter_by(snapshot_date=latest_date_query)
    main_q = apply_filters(main_q)
    
    pagination = main_q.paginate(page=page, per_page=per_page, error_out=False)
    
    return render_template('order_status.html', unread_count=unread_count, sync_time=sync_time, stats=stats, rows=pagination.items, pagination=pagination, footer_totals=footer_totals)

@dashboard_bp.route('/api/orderstatus/options')
@jwt_required()
def order_status_options():
    options = {
        'divisions': [r[0] for r in db.session.query(OrderStatusReportSnapshot.division.distinct()).order_by(OrderStatusReportSnapshot.division).all() if r[0]],
        'groups': [r[0] for r in db.session.query(OrderStatusReportSnapshot.group_name.distinct()).order_by(OrderStatusReportSnapshot.group_name).all() if r[0]],
        'purities': [r[0] for r in db.session.query(OrderStatusReportSnapshot.purity.distinct()).order_by(OrderStatusReportSnapshot.purity).all() if r[0]],
        'classifications': [r[0] for r in db.session.query(OrderStatusReportSnapshot.classification.distinct()).order_by(OrderStatusReportSnapshot.classification).all() if r[0]],
        'makes': [r[0] for r in db.session.query(OrderStatusReportSnapshot.make_location.distinct()).order_by(OrderStatusReportSnapshot.make_location).all() if r[0]],
        'collections': [r[0] for r in db.session.query(OrderStatusReportSnapshot.collection.distinct()).order_by(OrderStatusReportSnapshot.collection).all() if r[0]],
        'parties': [r[0] for r in db.session.query(OrderStatusReportSnapshot.party_name.distinct()).order_by(OrderStatusReportSnapshot.party_name).all() if r[0]],
        'make_owners': [r[0] for r in db.session.query(OrderStatusReportSnapshot.make_owner.distinct()).order_by(OrderStatusReportSnapshot.make_owner).all() if r[0]],
        'collection_owners': [r[0] for r in db.session.query(OrderStatusReportSnapshot.collection_owner.distinct()).order_by(OrderStatusReportSnapshot.collection_owner).all() if r[0]],
        'classification_owners': [r[0] for r in db.session.query(OrderStatusReportSnapshot.classification_owner.distinct()).order_by(OrderStatusReportSnapshot.classification_owner).all() if r[0]],
        'business_heads': [r[0] for r in db.session.query(OrderStatusReportSnapshot.business_head.distinct()).order_by(OrderStatusReportSnapshot.business_head).all() if r[0]]
    }
    return jsonify(options)

@dashboard_bp.route('/partial/<view_type>')
@jwt_required()
def get_dashboard_partial(view_type):
    if view_type not in ['make', 'collection', 'party']:
        return "Invalid view type", 400
        
    latest_date_query = db.session.query(func.max(OrderStatusReportSnapshot.snapshot_date)).scalar()
    
    # Filters
    search = request.args.get('search', '').strip()
    division = request.args.get('division', '')
    group = request.args.get('group', '')
    purity = request.args.get('purity', '')
    classification = request.args.get('classification', '')
    make = request.args.get('make', '')
    collection = request.args.get('collection', '')
    party = request.args.get('party', '')
    
    # New Owner Filters
    make_owner = request.args.get('make_owner', '')
    collection_owner = request.args.get('collection_owner', '')
    classification_owner = request.args.get('classification_owner', '')
    business_head = request.args.get('business_head', '')

    def apply_filters(query):
        if search:
            query = query.filter(OrderStatusReportSnapshot.hierarchy_key.ilike(f"%{search}%"))
        if division:
            query = query.filter(OrderStatusReportSnapshot.division == division)
        if group:
            query = query.filter(OrderStatusReportSnapshot.group_name == group)
        if purity:
            query = query.filter(OrderStatusReportSnapshot.purity == purity)
        if classification:
            query = query.filter(OrderStatusReportSnapshot.classification == classification)
        if make:
            query = query.filter(OrderStatusReportSnapshot.make_location == make)
        if collection:
            query = query.filter(OrderStatusReportSnapshot.collection == collection)
        if party:
            query = query.filter(OrderStatusReportSnapshot.party_name == party)
            
        # Apply New Owner Filters
        if make_owner:
            query = query.filter(OrderStatusReportSnapshot.make_owner == make_owner)
        if collection_owner:
            query = query.filter(OrderStatusReportSnapshot.collection_owner == collection_owner)
        if classification_owner:
            query = query.filter(OrderStatusReportSnapshot.classification_owner == classification_owner)
        if business_head:
            query = query.filter(OrderStatusReportSnapshot.business_head == business_head)
            
        return query

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    
    # Re-using stat queries could be refactored but copying for now
    if latest_date_query:
        # Global Stats (Updated for filters)
        agg_q = db.session.query(
            func.sum(OrderStatusReportSnapshot.total_count).label('total_orders'),
            func.sum(OrderStatusReportSnapshot.dispatched_count).label('dispatched'),
            func.sum(OrderStatusReportSnapshot.in_process_count).label('in_process'),
            func.sum(OrderStatusReportSnapshot.delayed_count).label('delayed'),
            func.sum(OrderStatusReportSnapshot.active_slots).label('active_slots'),
            func.avg(OrderStatusReportSnapshot.sla_index_pct).label('sla_index'),
            func.avg(OrderStatusReportSnapshot.avg_quality_score).label('quality_score'),
            func.avg(OrderStatusReportSnapshot.fulfillment_pct).label('fulfillment')
        ).filter(OrderStatusReportSnapshot.snapshot_date == latest_date_query)
        agg_q = apply_filters(agg_q)
        aggs = agg_q.first()

        stats = {
            'total_orders': f"{aggs.total_orders or 0:,}",
            'dispatched': f"{aggs.dispatched or 0:,}",
            'in_process': f"{aggs.in_process or 0:,}",
            'delayed': f"{aggs.delayed or 0:,}",
            'active_slots': f"{aggs.active_slots or 0:,}",
            'sla_index': f"{round(aggs.sla_index or 0, 1)}%",
            'quality_score': f"{round(aggs.quality_score or 0, 1)}/5",
            'fulfillment': f"{int(aggs.fulfillment or 0)}%"
        }

        # Footer Totals
        f_agg_q = db.session.query(
            func.sum(OrderStatusReportSnapshot.a_completed_count + OrderStatusReportSnapshot.a_pending_count).label('a'),
            func.sum(OrderStatusReportSnapshot.b_completed_count + OrderStatusReportSnapshot.b_pending_count).label('b'),
            func.sum(OrderStatusReportSnapshot.c_completed_count + OrderStatusReportSnapshot.c_pending_count).label('c'),
            func.sum(OrderStatusReportSnapshot.d_completed_count + OrderStatusReportSnapshot.d_pending_count).label('d'),
            func.sum(OrderStatusReportSnapshot.e_completed_count + OrderStatusReportSnapshot.e_pending_count).label('e'),
            func.sum(OrderStatusReportSnapshot.f_completed_count + OrderStatusReportSnapshot.f_pending_count).label('f'),
            func.sum(OrderStatusReportSnapshot.g_completed_count + OrderStatusReportSnapshot.g_pending_count).label('g'),
            func.sum(OrderStatusReportSnapshot.total_count).label('total')
        ).filter(OrderStatusReportSnapshot.snapshot_date == latest_date_query)
        f_agg_q = apply_filters(f_agg_q)
        f_agg = f_agg_q.first()

        footer_totals = {
            'a': f"{f_agg.a or 0:,}", 'b': f"{f_agg.b or 0:,}", 'c': f"{f_agg.c or 0:,}",
            'd': f"{f_agg.d or 0:,}", 'e': f"{f_agg.e or 0:,}", 'f': f"{f_agg.f or 0:,}",
            'g': f"{f_agg.g or 0:,}", 'total': f"{f_agg.total or 0:,}"
        }

        # Paginate
        main_q = OrderStatusReportSnapshot.query.filter_by(snapshot_date=latest_date_query)
        main_q = apply_filters(main_q)
        pagination = main_q.paginate(page=page, per_page=per_page, error_out=False)

        return render_template(f'partials/_view_{view_type}.html', 
                             rows=pagination.items if pagination else [], 
                             pagination=pagination, 
                             footer_totals=footer_totals,
                             stats=stats)
    else:
        return "No data", 404
