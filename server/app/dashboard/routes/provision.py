from flask import render_template, request, jsonify
from app.dashboard import dashboard_bp
from app.models import Notification, OrderProvisionSummaryReport
from app.extensions import db
from sqlalchemy import func, cast, Numeric
from datetime import datetime

@dashboard_bp.route('/provisionstatus')
def provision_status():
    unread_count = Notification.query.filter_by(is_read=False).count()
    sync_time = datetime.now().strftime("%H:%M")

    # Filters
    search = request.args.get('search', '').strip()
    division = request.args.get('division', '')
    group = request.args.get('group', '')
    purity = request.args.get('purity', '')
    classification = request.args.get('classification', '')
    make = request.args.get('make', '')
    collection = request.args.get('collection', '')
    section = request.args.get('section', '')
    product_type = request.args.get('product_type', '')
    business_head = request.args.get('business_head', '')

    def apply_filters(query):
        if search:
            query = query.filter(OrderProvisionSummaryReport.division.ilike(f"%{search}%") | 
                                 OrderProvisionSummaryReport.group_name.ilike(f"%{search}%") |
                                 OrderProvisionSummaryReport.classification.ilike(f"%{search}%") |
                                 OrderProvisionSummaryReport.party.ilike(f"%{search}%"))
        if division:
            query = query.filter(OrderProvisionSummaryReport.division == division)
        if group:
            query = query.filter(OrderProvisionSummaryReport.group_name == group)
        if purity:
            query = query.filter(OrderProvisionSummaryReport.purity == purity)
        if classification:
            query = query.filter(OrderProvisionSummaryReport.classification == classification)
        if make:
            query = query.filter(OrderProvisionSummaryReport.make == make)
        if collection:
            query = query.filter(OrderProvisionSummaryReport.collection == collection)
        if section:
            query = query.filter(OrderProvisionSummaryReport.section == section)
        if product_type:
            query = query.filter(OrderProvisionSummaryReport.master_collection == product_type)
        if business_head:
            query = query.filter(OrderProvisionSummaryReport.business_head == business_head)
        return query

    # Global Stats
    agg_q = db.session.query(
        func.sum(cast(OrderProvisionSummaryReport.pieces, Numeric)).label('total_items'),
        func.sum(cast(OrderProvisionSummaryReport.gr_wt, Numeric)).label('total_weight'),
        func.count(OrderProvisionSummaryReport.master_collection.distinct()).label('unique_products'),
        func.avg(cast(OrderProvisionSummaryReport.gr_wt, Numeric)).label('avg_weight')
    )
    agg_q = apply_filters(agg_q)
    aggs = agg_q.first()

    stats = {
        'total_items': f"{int(aggs.total_items or 0):,}",
        'total_weight': f"{round(aggs.total_weight or 0, 3)}",
        'unique_products': f"{aggs.unique_products or 0:,}",
        'avg_weight': f"{round(aggs.avg_weight or 0, 3)}"
    }

    # Footer Totals
    footer_q = db.session.query(func.sum(cast(OrderProvisionSummaryReport.pieces, Numeric)).label('total'))
    footer_q = apply_filters(footer_q)
    footer_aggs = footer_q.first()
    footer_totals = {'total': f"{int(footer_aggs.total or 0):,}"}
    
    # Pagination
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    main_q = OrderProvisionSummaryReport.query
    main_q = apply_filters(main_q)
    pagination = main_q.paginate(page=page, per_page=per_page, error_out=False)

    return render_template('provision_status.html', unread_count=unread_count, sync_time=sync_time, stats=stats, 
                         rows=pagination.items if pagination else [], pagination=pagination, footer_totals=footer_totals,
                         active_filters={'division': division, 'group': group, 'purity': purity,
                         'classification': classification, 'make': make, 'collection': collection, 'section': section,
                         'product_type': product_type, 'search': search, 'business_head': business_head})

@dashboard_bp.route('/api/provisionstatus/options')
def provision_status_options():
    options = {
        'divisions': [r[0] for r in db.session.query(OrderProvisionSummaryReport.division.distinct()).order_by(OrderProvisionSummaryReport.division).all() if r[0]],
        'groups': [r[0] for r in db.session.query(OrderProvisionSummaryReport.group_name.distinct()).order_by(OrderProvisionSummaryReport.group_name).all() if r[0]],
        'purities': [r[0] for r in db.session.query(OrderProvisionSummaryReport.purity.distinct()).order_by(OrderProvisionSummaryReport.purity).all() if r[0]],
        'classifications': [r[0] for r in db.session.query(OrderProvisionSummaryReport.classification.distinct()).order_by(OrderProvisionSummaryReport.classification).all() if r[0]],
        'makes': [r[0] for r in db.session.query(OrderProvisionSummaryReport.make.distinct()).order_by(OrderProvisionSummaryReport.make).all() if r[0]],
        'collections': [r[0] for r in db.session.query(OrderProvisionSummaryReport.collection.distinct()).order_by(OrderProvisionSummaryReport.collection).all() if r[0]],
        'parties': [r[0] for r in db.session.query(OrderProvisionSummaryReport.party.distinct()).order_by(OrderProvisionSummaryReport.party).all() if r[0]],
        'sections': [r[0] for r in db.session.query(OrderProvisionSummaryReport.section.distinct()).order_by(OrderProvisionSummaryReport.section).all() if r[0]],
        'product_types': [r[0] for r in db.session.query(OrderProvisionSummaryReport.master_collection.distinct()).order_by(OrderProvisionSummaryReport.master_collection).all() if r[0]],
        'business_heads': [r[0] for r in db.session.query(OrderProvisionSummaryReport.business_head.distinct()).order_by(OrderProvisionSummaryReport.business_head).all() if r[0]]
    }
    return jsonify(options)

@dashboard_bp.route('/provisionstatus/partial')
def provision_status_partial():
    # Filters
    search = request.args.get('search', '').strip()
    division = request.args.get('division', '')
    group = request.args.get('group', '')
    purity = request.args.get('purity', '')
    classification = request.args.get('classification', '')
    make = request.args.get('make', '')
    collection = request.args.get('collection', '')
    section = request.args.get('section', '')
    product_type = request.args.get('product_type', '')
    business_head = request.args.get('business_head', '')

    def apply_filters(query):
        if search:
            query = query.filter(OrderProvisionSummaryReport.division.ilike(f"%{search}%") | 
                                 OrderProvisionSummaryReport.group_name.ilike(f"%{search}%") |
                                 OrderProvisionSummaryReport.classification.ilike(f"%{search}%") |
                                 OrderProvisionSummaryReport.party.ilike(f"%{search}%"))
        if division: query = query.filter(OrderProvisionSummaryReport.division == division)
        if group: query = query.filter(OrderProvisionSummaryReport.group_name == group)
        if purity: query = query.filter(OrderProvisionSummaryReport.purity == purity)
        if classification: query = query.filter(OrderProvisionSummaryReport.classification == classification)
        if make: query = query.filter(OrderProvisionSummaryReport.make == make)
        if collection: query = query.filter(OrderProvisionSummaryReport.collection == collection)
        if section: query = query.filter(OrderProvisionSummaryReport.section == section)
        if product_type: query = query.filter(OrderProvisionSummaryReport.master_collection == product_type)
        if business_head: query = query.filter(OrderProvisionSummaryReport.business_head == business_head)
        return query

    # Global Stats
    agg_q = db.session.query(
        func.sum(cast(OrderProvisionSummaryReport.pieces, Numeric)).label('total_items'),
        func.sum(cast(OrderProvisionSummaryReport.gr_wt, Numeric)).label('total_weight'),
        func.count(OrderProvisionSummaryReport.master_collection.distinct()).label('unique_products'),
        func.avg(cast(OrderProvisionSummaryReport.gr_wt, Numeric)).label('avg_weight')
    )
    agg_q = apply_filters(agg_q)
    aggs = agg_q.first()
    stats = {
        'total_items': f"{int(aggs.total_items or 0):,}",
        'total_weight': f"{round(aggs.total_weight or 0, 3)}",
        'unique_products': f"{aggs.unique_products or 0:,}",
        'avg_weight': f"{round(aggs.avg_weight or 0, 3)}"
    }

    # Footer Totals
    footer_q = db.session.query(func.sum(cast(OrderProvisionSummaryReport.pieces, Numeric)).label('total'))
    footer_q = apply_filters(footer_q)
    footer_aggs = footer_q.first()
    footer_totals = {'total': f"{int(footer_aggs.total or 0):,}"}
    
    # Pagination
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    main_q = OrderProvisionSummaryReport.query
    main_q = apply_filters(main_q)
    pagination = main_q.paginate(page=page, per_page=per_page, error_out=False)

    return render_template('partials/_view_provision_status.html', rows=pagination.items if pagination else [], 
                         pagination=pagination, footer_totals=footer_totals, stats=stats)
