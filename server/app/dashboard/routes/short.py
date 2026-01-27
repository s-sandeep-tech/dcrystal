from flask import render_template, request, jsonify
from flask_jwt_extended import jwt_required
from app.dashboard import dashboard_bp
from app.models import Notification, ShortStatusReportSnapshot
from app.extensions import db
from sqlalchemy import func
from datetime import datetime

@dashboard_bp.route('/shortstatus')
def short_status():
    unread_count = Notification.query.filter_by(is_read=False).count()
    sync_time = datetime.now().strftime("%H:%M")

    # Fetch latest snapshot date
    latest_date_query = db.session.query(func.max(ShortStatusReportSnapshot.snapshot_date)).scalar()
    
    if not latest_date_query:
        return render_template('short_status.html', 
                             unread_count=unread_count, 
                             sync_time=sync_time, 
                             stats={}, 
                             rows=[], 
                             pagination=None,
                             footer_totals={})

    return render_template('short_status.html',
                         unread_count=unread_count,
                         sync_time=sync_time,
                         stats={}, 
                         rows=[],
                         pagination=None,
                         footer_totals={})

@dashboard_bp.route('/shortstatus/partial')
@jwt_required()
def get_short_status_partial():
    latest_date_query = db.session.query(func.max(ShortStatusReportSnapshot.snapshot_date)).scalar()
    
    # Filters (mapping requested names to model columns)
    search = request.args.get('search', '').strip()
    division = request.args.get('division', '')
    group = request.args.get('group', '')
    purity = request.args.get('purity', '')
    classification = request.args.get('classification', '')
    make = request.args.get('make', '')
    collection = request.args.get('collection', '')
    section = request.args.get('section', '')
    product_type = request.args.get('product_type', '')

    def apply_filters(query):
        if search:
            query = query.filter(ShortStatusReportSnapshot.division.ilike(f"%{search}%") | 
                                 ShortStatusReportSnapshot.group_name.ilike(f"%{search}%") |
                                 ShortStatusReportSnapshot.classification.ilike(f"%{search}%"))
        if division:
            query = query.filter(ShortStatusReportSnapshot.division == division)
        if group:
            query = query.filter(ShortStatusReportSnapshot.group_name == group)
        if purity:
            query = query.filter(ShortStatusReportSnapshot.purity == purity)
        if classification:
            query = query.filter(ShortStatusReportSnapshot.classification == classification)
        if make:
            query = query.filter(ShortStatusReportSnapshot.make_location == make)
        if collection:
            query = query.filter(ShortStatusReportSnapshot.collection == collection)
        if section:
            query = query.filter(ShortStatusReportSnapshot.section == section)
        if product_type:
            query = query.filter(ShortStatusReportSnapshot.product_type == product_type)
        return query

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    
    pagination = None
    footer_totals = {}
    stats = {}
    
    if latest_date_query:
        # Global Stats for Short Status
        agg_q = db.session.query(
            func.sum(ShortStatusReportSnapshot.total_count).label('total_items'),
            func.sum(ShortStatusReportSnapshot.weight).label('total_weight'),
            func.count(ShortStatusReportSnapshot.product_type.distinct()).label('unique_products'),
            func.avg(ShortStatusReportSnapshot.weight).label('avg_weight')
        ).filter(ShortStatusReportSnapshot.snapshot_date == latest_date_query)
        agg_q = apply_filters(agg_q)
        aggs = agg_q.first()

        stats = {
            'total_items': f"{aggs.total_items or 0:,}",
            'total_weight': f"{round(aggs.total_weight or 0, 3)}",
            'unique_products': f"{aggs.unique_products or 0:,}",
            'avg_weight': f"{round(aggs.avg_weight or 0, 3)}"
        }

        # Footer Totals
        f_agg_q = db.session.query(
            func.sum(ShortStatusReportSnapshot.a_completed_count + ShortStatusReportSnapshot.a_pending_count).label('a'),
            func.sum(ShortStatusReportSnapshot.b_completed_count + ShortStatusReportSnapshot.b_pending_count).label('b'),
            func.sum(ShortStatusReportSnapshot.c_completed_count + ShortStatusReportSnapshot.c_pending_count).label('c'),
            func.sum(ShortStatusReportSnapshot.d_completed_count + ShortStatusReportSnapshot.d_pending_count).label('d'),
            func.sum(ShortStatusReportSnapshot.e_completed_count + ShortStatusReportSnapshot.e_pending_count).label('e'),
            func.sum(ShortStatusReportSnapshot.f_completed_count + ShortStatusReportSnapshot.f_pending_count).label('f'),
            func.sum(ShortStatusReportSnapshot.g_completed_count + ShortStatusReportSnapshot.g_pending_count).label('g'),
            func.sum(ShortStatusReportSnapshot.total_count).label('total')
        ).filter(ShortStatusReportSnapshot.snapshot_date == latest_date_query)
        f_agg_q = apply_filters(f_agg_q)
        f_agg = f_agg_q.first()

        footer_totals = {
            'a': f"{f_agg.a or 0:,}", 'b': f"{f_agg.b or 0:,}", 'c': f"{f_agg.c or 0:,}",
            'd': f"{f_agg.d or 0:,}", 'e': f"{f_agg.e or 0:,}", 'f': f"{f_agg.f or 0:,}",
            'g': f"{f_agg.g or 0:,}", 'total': f"{f_agg.total or 0:,}"
        }

        # Paginate
        main_q = ShortStatusReportSnapshot.query.filter_by(snapshot_date=latest_date_query)
        main_q = apply_filters(main_q)
        pagination = main_q.paginate(page=page, per_page=per_page, error_out=False)

    return render_template('partials/_view_shortstatus.html', 
                         rows=pagination.items if pagination else [], 
                         pagination=pagination, 
                         footer_totals=footer_totals,
                         stats=stats)

@dashboard_bp.route('/api/shortstatus/options')
@jwt_required()
def short_status_options():
    options = {
        'divisions': [r[0] for r in db.session.query(ShortStatusReportSnapshot.division.distinct()).order_by(ShortStatusReportSnapshot.division).all() if r[0]],
        'groups': [r[0] for r in db.session.query(ShortStatusReportSnapshot.group_name.distinct()).order_by(ShortStatusReportSnapshot.group_name).all() if r[0]],
        'purities': [r[0] for r in db.session.query(ShortStatusReportSnapshot.purity.distinct()).order_by(ShortStatusReportSnapshot.purity).all() if r[0]],
        'classifications': [r[0] for r in db.session.query(ShortStatusReportSnapshot.classification.distinct()).order_by(ShortStatusReportSnapshot.classification).all() if r[0]],
        'makes': [r[0] for r in db.session.query(ShortStatusReportSnapshot.make_location.distinct()).order_by(ShortStatusReportSnapshot.make_location).all() if r[0]],
        'collections': [r[0] for r in db.session.query(ShortStatusReportSnapshot.collection.distinct()).order_by(ShortStatusReportSnapshot.collection).all() if r[0]],
        'sections': [r[0] for r in db.session.query(ShortStatusReportSnapshot.section.distinct()).order_by(ShortStatusReportSnapshot.section).all() if r[0]],
        'product_types': [r[0] for r in db.session.query(ShortStatusReportSnapshot.product_type.distinct()).order_by(ShortStatusReportSnapshot.product_type).all() if r[0]],
        'parties': [],
        'make_owners': [],
        'collection_owners': [],
        'classification_owners': [],
        'business_heads': []
    }
    return jsonify(options)
