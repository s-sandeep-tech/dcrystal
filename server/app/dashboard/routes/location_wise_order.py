from flask import render_template, request, jsonify
from flask_jwt_extended import jwt_required
from app.dashboard import dashboard_bp
from app.models import Notification, LocationWiseOrderSnapshot
from app.extensions import db
from sqlalchemy import func
from datetime import datetime

@dashboard_bp.route('/locationwiseorderstatus')
def location_wise_order_status():
    unread_count = Notification.query.filter_by(is_read=False).count()
    sync_time = datetime.now().strftime("%H:%M")

    latest_date_query = db.session.query(func.max(LocationWiseOrderSnapshot.snapshot_date)).scalar()
    
    if not latest_date_query:
        return render_template('location_wise_order_status.html', 
                             unread_count=unread_count, 
                             sync_time=sync_time, 
                             stats={}, 
                             rows=[], 
                             pagination=None, 
                             footer_totals={})

    return render_template('location_wise_order_status.html', 
                         unread_count=unread_count, 
                         sync_time=sync_time, 
                         stats={}, 
                         rows=[], 
                         pagination=None, 
                         footer_totals={})

@dashboard_bp.route('/locationwiseorderstatus/partial')
@jwt_required()
def get_location_wise_order_partial():
    latest_date_query = db.session.query(func.max(LocationWiseOrderSnapshot.snapshot_date)).scalar()
    
    # Filters
    search = request.args.get('search', '').strip()
    location = request.args.get('location', '')
    division = request.args.get('division', '')
    group = request.args.get('group', '')
    purity = request.args.get('purity', '')
    classification = request.args.get('classification', '')
    make = request.args.get('make', '')
    collection = request.args.get('collection', '')
    
    # Owner Filters
    make_owner = request.args.get('make_owner', '')
    collection_owner = request.args.get('collection_owner', '')
    classification_owner = request.args.get('classification_owner', '')
    business_head = request.args.get('business_head', '')

    def apply_filters(query):
        if search:
            query = query.filter(LocationWiseOrderSnapshot.division.ilike(f"%{search}%") | 
                                 LocationWiseOrderSnapshot.location.ilike(f"%{search}%"))
        if location:
            query = query.filter(LocationWiseOrderSnapshot.location == location)
        if division:
            query = query.filter(LocationWiseOrderSnapshot.division == division)
        if group:
            query = query.filter(LocationWiseOrderSnapshot.group_name == group)
        if purity:
            query = query.filter(LocationWiseOrderSnapshot.purity == purity)
        if classification:
            query = query.filter(LocationWiseOrderSnapshot.classification == classification)
        if make:
            query = query.filter(LocationWiseOrderSnapshot.make_location == make)
        if collection:
            query = query.filter(LocationWiseOrderSnapshot.collection == collection)
            
        if make_owner:
            query = query.filter(LocationWiseOrderSnapshot.make_owner == make_owner)
        if collection_owner:
            query = query.filter(LocationWiseOrderSnapshot.collection_owner == collection_owner)
        if classification_owner:
            query = query.filter(LocationWiseOrderSnapshot.classification_owner == classification_owner)
        if business_head:
            query = query.filter(LocationWiseOrderSnapshot.business_head == business_head)
            
        return query

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    
    pagination = None
    footer_totals = {}
    stats = {}
    
    if latest_date_query:
        # Global Stats
        agg_q = db.session.query(
            func.sum(LocationWiseOrderSnapshot.total_count).label('total_orders'),
            func.sum(LocationWiseOrderSnapshot.dispatched_count).label('dispatched'),
            func.sum(LocationWiseOrderSnapshot.in_process_count).label('in_process'),
            func.sum(LocationWiseOrderSnapshot.delayed_count).label('delayed'),
            func.avg(LocationWiseOrderSnapshot.sla_index_pct).label('sla_index'),
            func.avg(LocationWiseOrderSnapshot.fulfillment_pct).label('fulfillment')
        ).filter(LocationWiseOrderSnapshot.snapshot_date == latest_date_query)
        agg_q = apply_filters(agg_q)
        aggs = agg_q.first()

        stats = {
            'total_orders': f"{aggs.total_orders or 0:,}",
            'dispatched': f"{aggs.dispatched or 0:,}",
            'in_process': f"{aggs.in_process or 0:,}",
            'delayed': f"{aggs.delayed or 0:,}",
            'sla_index': f"{round(aggs.sla_index or 0, 1)}%",
            'fulfillment': f"{int(aggs.fulfillment or 0)}%"
        }

        # Footer Totals
        f_agg_q = db.session.query(
            func.sum(LocationWiseOrderSnapshot.a_completed_count + LocationWiseOrderSnapshot.a_pending_count).label('a'),
            func.sum(LocationWiseOrderSnapshot.b_completed_count + LocationWiseOrderSnapshot.b_pending_count).label('b'),
            func.sum(LocationWiseOrderSnapshot.c_completed_count + LocationWiseOrderSnapshot.c_pending_count).label('c'),
            func.sum(LocationWiseOrderSnapshot.d_completed_count + LocationWiseOrderSnapshot.d_pending_count).label('d'),
            func.sum(LocationWiseOrderSnapshot.e_completed_count + LocationWiseOrderSnapshot.e_pending_count).label('e'),
            func.sum(LocationWiseOrderSnapshot.f_completed_count + LocationWiseOrderSnapshot.f_pending_count).label('f'),
            func.sum(LocationWiseOrderSnapshot.g_completed_count + LocationWiseOrderSnapshot.g_pending_count).label('g'),
            func.sum(LocationWiseOrderSnapshot.total_count).label('total')
        ).filter(LocationWiseOrderSnapshot.snapshot_date == latest_date_query)
        f_agg_q = apply_filters(f_agg_q)
        f_agg = f_agg_q.first()

        footer_totals = {
            'a': f"{f_agg.a or 0:,}", 'b': f"{f_agg.b or 0:,}", 'c': f"{f_agg.c or 0:,}",
            'd': f"{f_agg.d or 0:,}", 'e': f"{f_agg.e or 0:,}", 'f': f"{f_agg.f or 0:,}",
            'g': f"{f_agg.g or 0:,}", 'total': f"{f_agg.total or 0:,}"
        }

        # Paginate
        main_q = LocationWiseOrderSnapshot.query.filter_by(snapshot_date=latest_date_query)
        main_q = apply_filters(main_q)
        pagination = main_q.paginate(page=page, per_page=per_page, error_out=False)

    return render_template('partials/_view_location_wise_order.html', 
                         rows=pagination.items if pagination else [], 
                         pagination=pagination, 
                         footer_totals=footer_totals,
                         stats=stats)

@dashboard_bp.route('/api/locationwiseorderstatus/options')
@jwt_required()
def location_wise_order_options():
    options = {
        'locations': [r[0] for r in db.session.query(LocationWiseOrderSnapshot.location.distinct()).order_by(LocationWiseOrderSnapshot.location).all() if r[0]],
        'divisions': [r[0] for r in db.session.query(LocationWiseOrderSnapshot.division.distinct()).order_by(LocationWiseOrderSnapshot.division).all() if r[0]],
        'groups': [r[0] for r in db.session.query(LocationWiseOrderSnapshot.group_name.distinct()).order_by(LocationWiseOrderSnapshot.group_name).all() if r[0]],
        'purities': [r[0] for r in db.session.query(LocationWiseOrderSnapshot.purity.distinct()).order_by(LocationWiseOrderSnapshot.purity).all() if r[0]],
        'classifications': [r[0] for r in db.session.query(LocationWiseOrderSnapshot.classification.distinct()).order_by(LocationWiseOrderSnapshot.classification).all() if r[0]],
        'makes': [r[0] for r in db.session.query(LocationWiseOrderSnapshot.make_location.distinct()).order_by(LocationWiseOrderSnapshot.make_location).all() if r[0]],
        'collections': [r[0] for r in db.session.query(LocationWiseOrderSnapshot.collection.distinct()).order_by(LocationWiseOrderSnapshot.collection).all() if r[0]],
        'make_owners': [r[0] for r in db.session.query(LocationWiseOrderSnapshot.make_owner.distinct()).order_by(LocationWiseOrderSnapshot.make_owner).all() if r[0]],
        'collection_owners': [r[0] for r in db.session.query(LocationWiseOrderSnapshot.collection_owner.distinct()).order_by(LocationWiseOrderSnapshot.collection_owner).all() if r[0]],
        'classification_owners': [r[0] for r in db.session.query(LocationWiseOrderSnapshot.classification_owner.distinct()).order_by(LocationWiseOrderSnapshot.classification_owner).all() if r[0]],
        'business_heads': [r[0] for r in db.session.query(LocationWiseOrderSnapshot.business_head.distinct()).order_by(LocationWiseOrderSnapshot.business_head).all() if r[0]]
    }
    return jsonify(options)
