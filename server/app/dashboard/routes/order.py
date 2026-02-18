from flask import render_template, request, jsonify
from flask_jwt_extended import jwt_required
from app.dashboard import dashboard_bp
from app.models import Notification, OwnerWiseOrderSummarySnapshot
from app.extensions import db
from sqlalchemy import func
from datetime import datetime

@dashboard_bp.route('/orderstatus')
def order_status():
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
    party = request.args.get('party', '')
    
    # New Owner Filters
    make_owner = request.args.get('make_owner', '')
    collection_owner = request.args.get('collection_owner', '')
    classification_owner = request.args.get('classification_owner', '')
    # business_head not in OwnerWiseOrderSummarySnapshot
    # business_head = request.args.get('business_head', '')

    def apply_filters(query):
        # OwnerWiseOrderSummarySnapshot does not have hierarchy_key, searching individual fields
        if search:
            query = query.filter(
                (OwnerWiseOrderSummarySnapshot.division.ilike(f"%{search}%")) |
                (OwnerWiseOrderSummarySnapshot.group_name.ilike(f"%{search}%")) |
                (OwnerWiseOrderSummarySnapshot.make.ilike(f"%{search}%")) |
                (OwnerWiseOrderSummarySnapshot.collection.ilike(f"%{search}%")) |
                (OwnerWiseOrderSummarySnapshot.supplier.ilike(f"%{search}%"))
            )
        if division:
            query = query.filter(OwnerWiseOrderSummarySnapshot.division == division)
        if group:
            query = query.filter(OwnerWiseOrderSummarySnapshot.group_name == group)
        if purity:
            query = query.filter(OwnerWiseOrderSummarySnapshot.purity == purity)
        if classification:
            query = query.filter(OwnerWiseOrderSummarySnapshot.classification == classification)
        if make:
            query = query.filter(OwnerWiseOrderSummarySnapshot.make == make)
        if collection:
            query = query.filter(OwnerWiseOrderSummarySnapshot.collection == collection)
        if party:
            query = query.filter(OwnerWiseOrderSummarySnapshot.supplier == party)
            
        # Apply New Owner Filters
        if make_owner:
            query = query.filter(OwnerWiseOrderSummarySnapshot.make_owner == make_owner)
        if collection_owner:
            query = query.filter(OwnerWiseOrderSummarySnapshot.collection_owner == collection_owner)
        if classification_owner:
            query = query.filter(OwnerWiseOrderSummarySnapshot.classification_owner == classification_owner)
            
        return query

    # Global Stats
    # Mapping:
    # total_orders -> ordered_pcs
    # dispatched -> delivered_pcs ?? dispatched often means delivered or close to it. 
    #              Original model had dispatched_count. 
    #              Let's use delivered_pcs for dispatched for now, or maybe invoiced_pcs? 
    #              Let's use delivered_pcs.
    # in_process -> ordered_pcs - delivered_pcs ? (Simple approximation)
    # delayed -> ?? (Not available in new model, set to 0)
    # active_slots -> ?? (Not available, set to 0)
    # sla_index -> ?? (Not available, set to 0)
    # quality_score -> ?? (Not available, set to 0)
    # fulfillment -> delivered_pcs / ordered_pcs %
    
    agg_q = db.session.query(
        func.sum(OwnerWiseOrderSummarySnapshot.ordered_pcs).label('total_orders'),
        func.sum(OwnerWiseOrderSummarySnapshot.delivered_pcs).label('dispatched'),
        func.sum(OwnerWiseOrderSummarySnapshot.ordered_pcs - OwnerWiseOrderSummarySnapshot.delivered_pcs).label('in_process'),
        # func.sum(OwnerWiseOrderSummarySnapshot.delayed_count).label('delayed'), # Not available
        # func.sum(OwnerWiseOrderSummarySnapshot.active_slots).label('active_slots'), # Not available
        # func.avg(OwnerWiseOrderSummarySnapshot.sla_index_pct).label('sla_index'), # Not available
        # func.avg(OwnerWiseOrderSummarySnapshot.avg_quality_score).label('quality_score'), # Not available
        # func.avg(OwnerWiseOrderSummarySnapshot.fulfillment_pct).label('fulfillment') # Not available
    )
    
    agg_q = apply_filters(agg_q)
    aggs = agg_q.first()

    total_orders = aggs.total_orders or 0
    dispatched = aggs.dispatched or 0
    in_process = aggs.in_process or 0
    fulfillment = 0
    if total_orders > 0:
        fulfillment = (dispatched / total_orders) * 100

    stats = {
        'total_orders': f"{total_orders:,.0f}",
        'dispatched': f"{dispatched:,.0f}",
        'in_process': f"{in_process:,.0f}",
        'delayed': "0",
        'active_slots': "0",
        'sla_index': "0%",
        'quality_score': "0/5",
        'fulfillment': f"{int(fulfillment)}%"
    }

    # Footer Totals
    # A = Ordered
    # B = Accepted
    # C = Barcoded
    # D = HM Passed
    # E = QC Passed
    # F = Invoiced
    # G = Delivered
    # Total = Ordered
    
    footer_q = db.session.query(
        func.sum(OwnerWiseOrderSummarySnapshot.ordered_pcs).label('a'),
        func.sum(OwnerWiseOrderSummarySnapshot.accepted_pcs).label('b'),
        func.sum(OwnerWiseOrderSummarySnapshot.barcoded_pcs).label('c'),
        func.sum(OwnerWiseOrderSummarySnapshot.hm_passed_pcs).label('d'),
        func.sum(OwnerWiseOrderSummarySnapshot.qc_passed_pcs).label('e'),
        func.sum(OwnerWiseOrderSummarySnapshot.invoiced_pcs).label('f'),
        func.sum(OwnerWiseOrderSummarySnapshot.delivered_pcs).label('g'),
        func.sum(OwnerWiseOrderSummarySnapshot.ordered_pcs).label('total')
    )
    
    footer_q = apply_filters(footer_q)
    footer_aggs = footer_q.first()

    footer_totals = {
        'a': f"{footer_aggs.a or 0:,.0f}", 'b': f"{footer_aggs.b or 0:,.0f}", 'c': f"{footer_aggs.c or 0:,.0f}",
        'd': f"{footer_aggs.d or 0:,.0f}", 'e': f"{footer_aggs.e or 0:,.0f}", 'f': f"{footer_aggs.f or 0:,.0f}",
        'g': f"{footer_aggs.g or 0:,.0f}", 'total': f"{footer_aggs.total or 0:,.0f}"
    }
    
    # Pagination
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    
    # Identifiers to group by for Make view
    group_cols_make = [
        OwnerWiseOrderSummarySnapshot.division,
        OwnerWiseOrderSummarySnapshot.group_name,
        OwnerWiseOrderSummarySnapshot.purity,
        OwnerWiseOrderSummarySnapshot.classification,
        OwnerWiseOrderSummarySnapshot.make
    ]
    
    # Aggregates
    # Mapping pending counts:
    # A Pending (Ordered - Accepted) ?? Or just 0? UI sums completed + pending for 'a'.
    # Actually ui view 'stage-cell' for 'A (Ord)' shows `r.a_completed_count`.
    # And 'Order Level Pending' row shows `r.a_pending_count`.
    # Let's map pending to 0 if we don't have them, or derive them.
    # Derived:
    # a_pending = ordered - accepted (assuming linear flow)
    # b_pending = accepted - barcoded
    # c_pending = barcoded - hm
    # d_pending = hm - qc
    # e_pending = qc - invoiced
    # f_pending = invoiced - delivered
    # BUT this assumes strict linear flow and no rejections.
    # The new table has some rejection columns but limited pending columns.
    # Let's try to pass 0s for pending to handle it safely first.
    # UPDATE: qc_pending_pcs and pending_to_be_delv_pcs EXIST.
    
    agg_cols = [
        func.sum(OwnerWiseOrderSummarySnapshot.ordered_pcs).label('a_completed_count'),
        func.sum(0).label('a_pending_count'), # No direct pending field
        func.sum(OwnerWiseOrderSummarySnapshot.accepted_pcs).label('b_completed_count'),
        func.sum(0).label('b_pending_count'),
        func.sum(OwnerWiseOrderSummarySnapshot.barcoded_pcs).label('c_completed_count'),
        func.sum(OwnerWiseOrderSummarySnapshot.not_barcoded_pcs).label('c_pending_count'), # not_barcoded as pending??
        func.sum(OwnerWiseOrderSummarySnapshot.hm_passed_pcs).label('d_completed_count'),
        func.sum(0).label('d_pending_count'),
        func.sum(OwnerWiseOrderSummarySnapshot.qc_passed_pcs).label('e_completed_count'),
        func.sum(OwnerWiseOrderSummarySnapshot.qc_pending_pcs).label('e_pending_count'), # Use qc_pending_pcs
        func.sum(OwnerWiseOrderSummarySnapshot.invoiced_pcs).label('f_completed_count'),
        func.sum(0).label('f_pending_count'),
        func.sum(OwnerWiseOrderSummarySnapshot.delivered_pcs).label('g_completed_count'),
        func.sum(OwnerWiseOrderSummarySnapshot.pending_to_be_delv_pcs).label('g_pending_count'), # Use pending_to_be_delv_pcs
        
        func.sum(OwnerWiseOrderSummarySnapshot.ordered_pcs).label('total_count'),
        
        # Stats cols for rows (if needed by template? template seems to assume they exist? No, template uses `r.total_count` etc)
        # Template uses `r.a_completed_count` etc.
        # It does NOT use `dispatched_count` per row in the table, only in stats at top.
    ]

    main_q = db.session.query(*(group_cols_make + agg_cols))
    main_q = apply_filters(main_q)
    main_q = main_q.group_by(*group_cols_make).order_by(OwnerWiseOrderSummarySnapshot.division, OwnerWiseOrderSummarySnapshot.group_name, OwnerWiseOrderSummarySnapshot.make)
    
    pagination = main_q.paginate(page=page, per_page=per_page, error_out=False)
    
    # Need to verify if 'rows' in template expects an object with attributes. 
    # `pagination.items` will be KeyedTuples.
    # Template does `r.division`, `r.a_completed_count`. KeyedTuple supports dot access.
    # One catch: `make_location` vs `make`.
    # Old model: `make_location`
    # New model: `make`
    # Template uses `r.make_location`.
    # I MUST alias `make` as `make_location`.
    
    # Let's adjust the group_cols_make to label `make` as `make_location`
    group_cols_make_aliased = [
        OwnerWiseOrderSummarySnapshot.division,
        OwnerWiseOrderSummarySnapshot.group_name,
        OwnerWiseOrderSummarySnapshot.purity,
        OwnerWiseOrderSummarySnapshot.classification,
        OwnerWiseOrderSummarySnapshot.make.label('make_location')
    ]
    
    # Re-build main_q with aliased group cols
    main_q = db.session.query(*(group_cols_make_aliased + agg_cols))
    main_q = apply_filters(main_q)
    main_q = main_q.group_by(
        OwnerWiseOrderSummarySnapshot.division,
        OwnerWiseOrderSummarySnapshot.group_name,
        OwnerWiseOrderSummarySnapshot.purity,
        OwnerWiseOrderSummarySnapshot.classification,
        OwnerWiseOrderSummarySnapshot.make
    ).order_by(
        OwnerWiseOrderSummarySnapshot.division, 
        OwnerWiseOrderSummarySnapshot.group_name, 
        OwnerWiseOrderSummarySnapshot.make
    )
    
    pagination = main_q.paginate(page=page, per_page=per_page, error_out=False)

    return render_template('order_status.html', unread_count=unread_count, sync_time=sync_time, stats=stats, rows=pagination.items, pagination=pagination, footer_totals=footer_totals)

@dashboard_bp.route('/api/orderstatus/options')
@jwt_required()
def order_status_options():
    options = {
        'divisions': [r[0] for r in db.session.query(OwnerWiseOrderSummarySnapshot.division.distinct()).order_by(OwnerWiseOrderSummarySnapshot.division).all() if r[0]],
        'groups': [r[0] for r in db.session.query(OwnerWiseOrderSummarySnapshot.group_name.distinct()).order_by(OwnerWiseOrderSummarySnapshot.group_name).all() if r[0]],
        'purities': [str(r[0]) for r in db.session.query(OwnerWiseOrderSummarySnapshot.purity.distinct()).order_by(OwnerWiseOrderSummarySnapshot.purity).all() if r[0]],
        'classifications': [r[0] for r in db.session.query(OwnerWiseOrderSummarySnapshot.classification.distinct()).order_by(OwnerWiseOrderSummarySnapshot.classification).all() if r[0]],
        'makes': [r[0] for r in db.session.query(OwnerWiseOrderSummarySnapshot.make.distinct()).order_by(OwnerWiseOrderSummarySnapshot.make).all() if r[0]],
        'collections': [r[0] for r in db.session.query(OwnerWiseOrderSummarySnapshot.collection.distinct()).order_by(OwnerWiseOrderSummarySnapshot.collection).all() if r[0]],
        'parties': [r[0] for r in db.session.query(OwnerWiseOrderSummarySnapshot.supplier.distinct()).order_by(OwnerWiseOrderSummarySnapshot.supplier).all() if r[0]],
        'make_owners': [r[0] for r in db.session.query(OwnerWiseOrderSummarySnapshot.make_owner.distinct()).order_by(OwnerWiseOrderSummarySnapshot.make_owner).all() if r[0]],
        'collection_owners': [r[0] for r in db.session.query(OwnerWiseOrderSummarySnapshot.collection_owner.distinct()).order_by(OwnerWiseOrderSummarySnapshot.collection_owner).all() if r[0]],
        'classification_owners': [r[0] for r in db.session.query(OwnerWiseOrderSummarySnapshot.classification_owner.distinct()).order_by(OwnerWiseOrderSummarySnapshot.classification_owner).all() if r[0]],
        'business_heads': [] # Not available in OwnerWiseOrderSummarySnapshot
    }
    return jsonify(options)

@dashboard_bp.route('/partial/<view_type>')
@jwt_required()
def get_dashboard_partial(view_type):
    if view_type not in ['make', 'collection', 'party']:
        return "Invalid view type", 400
        
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
            query = query.filter(
                (OwnerWiseOrderSummarySnapshot.division.ilike(f"%{search}%")) |
                (OwnerWiseOrderSummarySnapshot.group_name.ilike(f"%{search}%")) |
                (OwnerWiseOrderSummarySnapshot.make.ilike(f"%{search}%")) |
                (OwnerWiseOrderSummarySnapshot.collection.ilike(f"%{search}%")) |
                (OwnerWiseOrderSummarySnapshot.supplier.ilike(f"%{search}%"))
            )
        if division:
            query = query.filter(OwnerWiseOrderSummarySnapshot.division == division)
        if group:
            query = query.filter(OwnerWiseOrderSummarySnapshot.group_name == group)
        if purity:
            query = query.filter(OwnerWiseOrderSummarySnapshot.purity == purity)
        if classification:
            query = query.filter(OwnerWiseOrderSummarySnapshot.classification == classification)
        if make:
            query = query.filter(OwnerWiseOrderSummarySnapshot.make == make)
        if collection:
            query = query.filter(OwnerWiseOrderSummarySnapshot.collection == collection)
        if party:
            query = query.filter(OwnerWiseOrderSummarySnapshot.supplier == party)
            
        # Apply New Owner Filters
        if make_owner:
            query = query.filter(OwnerWiseOrderSummarySnapshot.make_owner == make_owner)
        if collection_owner:
            query = query.filter(OwnerWiseOrderSummarySnapshot.collection_owner == collection_owner)
        if classification_owner:
            query = query.filter(OwnerWiseOrderSummarySnapshot.classification_owner == classification_owner)
            
        return query

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    
    # Global Stats
    agg_q = db.session.query(
        func.sum(OwnerWiseOrderSummarySnapshot.ordered_pcs).label('total_orders'),
        func.sum(OwnerWiseOrderSummarySnapshot.delivered_pcs).label('dispatched'),
        func.sum(OwnerWiseOrderSummarySnapshot.ordered_pcs - OwnerWiseOrderSummarySnapshot.delivered_pcs).label('in_process'),
    )
    agg_q = apply_filters(agg_q)
    aggs = agg_q.first()

    total_orders = aggs.total_orders or 0
    dispatched = aggs.dispatched or 0
    in_process = aggs.in_process or 0
    fulfillment = 0
    if total_orders > 0:
        fulfillment = (dispatched / total_orders) * 100

    stats = {
        'total_orders': f"{total_orders:,.0f}",
        'dispatched': f"{dispatched:,.0f}",
        'in_process': f"{in_process:,.0f}",
        'delayed': "0",
        'active_slots': "0",
        'sla_index': "0%",
        'quality_score': "0/5",
        'fulfillment': f"{int(fulfillment)}%"
    }

    # Footer Totals
    f_agg_q = db.session.query(
        func.sum(OwnerWiseOrderSummarySnapshot.ordered_pcs).label('a'),
        func.sum(OwnerWiseOrderSummarySnapshot.accepted_pcs).label('b'),
        func.sum(OwnerWiseOrderSummarySnapshot.barcoded_pcs).label('c'),
        func.sum(OwnerWiseOrderSummarySnapshot.hm_passed_pcs).label('d'),
        func.sum(OwnerWiseOrderSummarySnapshot.qc_passed_pcs).label('e'),
        func.sum(OwnerWiseOrderSummarySnapshot.invoiced_pcs).label('f'),
        func.sum(OwnerWiseOrderSummarySnapshot.delivered_pcs).label('g'),
        func.sum(OwnerWiseOrderSummarySnapshot.ordered_pcs).label('total')
    )
    f_agg_q = apply_filters(f_agg_q)
    f_agg = f_agg_q.first()

    footer_totals = {
        'a': f"{f_agg.a or 0:,.0f}", 'b': f"{f_agg.b or 0:,.0f}", 'c': f"{f_agg.c or 0:,.0f}",
        'd': f"{f_agg.d or 0:,.0f}", 'e': f"{f_agg.e or 0:,.0f}", 'f': f"{f_agg.f or 0:,.0f}",
        'g': f"{f_agg.g or 0:,.0f}", 'total': f"{f_agg.total or 0:,.0f}"
    }

    # Paginate
    agg_cols = [
        func.sum(OwnerWiseOrderSummarySnapshot.ordered_pcs).label('a_completed_count'),
        func.sum(0).label('a_pending_count'), 
        func.sum(OwnerWiseOrderSummarySnapshot.accepted_pcs).label('b_completed_count'),
        func.sum(0).label('b_pending_count'),
        func.sum(OwnerWiseOrderSummarySnapshot.barcoded_pcs).label('c_completed_count'),
        func.sum(OwnerWiseOrderSummarySnapshot.not_barcoded_pcs).label('c_pending_count'),
        func.sum(OwnerWiseOrderSummarySnapshot.hm_passed_pcs).label('d_completed_count'),
        func.sum(0).label('d_pending_count'),
        func.sum(OwnerWiseOrderSummarySnapshot.qc_passed_pcs).label('e_completed_count'),
        func.sum(OwnerWiseOrderSummarySnapshot.qc_pending_pcs).label('e_pending_count'),
        func.sum(OwnerWiseOrderSummarySnapshot.invoiced_pcs).label('f_completed_count'),
        func.sum(0).label('f_pending_count'),
        func.sum(OwnerWiseOrderSummarySnapshot.delivered_pcs).label('g_completed_count'),
        func.sum(OwnerWiseOrderSummarySnapshot.pending_to_be_delv_pcs).label('g_pending_count'),
        func.sum(OwnerWiseOrderSummarySnapshot.ordered_pcs).label('total_count'),
    ]

    if view_type == 'make':
        group_cols = [
            OwnerWiseOrderSummarySnapshot.division,
            OwnerWiseOrderSummarySnapshot.group_name,
            OwnerWiseOrderSummarySnapshot.purity,
            OwnerWiseOrderSummarySnapshot.classification,
            OwnerWiseOrderSummarySnapshot.make.label('make_location')
        ]
        order_cols = [
            OwnerWiseOrderSummarySnapshot.division, 
            OwnerWiseOrderSummarySnapshot.group_name, 
            OwnerWiseOrderSummarySnapshot.make
        ]
    elif view_type == 'collection':
        group_cols = [
            OwnerWiseOrderSummarySnapshot.division,
            OwnerWiseOrderSummarySnapshot.group_name,
            OwnerWiseOrderSummarySnapshot.purity,
            OwnerWiseOrderSummarySnapshot.classification,
            OwnerWiseOrderSummarySnapshot.make.label('make_location'),
            OwnerWiseOrderSummarySnapshot.collection
        ]
        order_cols = [
            OwnerWiseOrderSummarySnapshot.division, 
            OwnerWiseOrderSummarySnapshot.group_name, 
            OwnerWiseOrderSummarySnapshot.make,
            OwnerWiseOrderSummarySnapshot.collection
        ]
    else: # party
        group_cols = [
            OwnerWiseOrderSummarySnapshot.division,
            OwnerWiseOrderSummarySnapshot.group_name,
            OwnerWiseOrderSummarySnapshot.purity,
            OwnerWiseOrderSummarySnapshot.classification,
            OwnerWiseOrderSummarySnapshot.make.label('make_location'),
            OwnerWiseOrderSummarySnapshot.collection,
            OwnerWiseOrderSummarySnapshot.supplier.label('party_name')
        ]
        order_cols = [
            OwnerWiseOrderSummarySnapshot.supplier
        ]
        
    main_q = db.session.query(*(group_cols + agg_cols))
    main_q = apply_filters(main_q)
    # Important: group_by MUST strictly match the selected columns (excluding aggs) or at least be consistent.
    # SQLAlchemy requires group_by to match clauses.
    # When using .label(), we can group by the entity column (e.g. OwnerWiseOrderSummarySnapshot.make).
    
    # We need to list unaliased columns for group_by to handle the label correctly or use the label object.
    # group_cols contains labeled columns for make and supplier.
    # Let's clean up group_by list.
    
    group_by_cols = []
    if view_type == 'make':
        group_by_cols = [
            OwnerWiseOrderSummarySnapshot.division,
            OwnerWiseOrderSummarySnapshot.group_name,
            OwnerWiseOrderSummarySnapshot.purity,
            OwnerWiseOrderSummarySnapshot.classification,
            OwnerWiseOrderSummarySnapshot.make
        ]
    elif view_type == 'collection':
        group_by_cols = [
            OwnerWiseOrderSummarySnapshot.division,
            OwnerWiseOrderSummarySnapshot.group_name,
            OwnerWiseOrderSummarySnapshot.purity,
            OwnerWiseOrderSummarySnapshot.classification,
            OwnerWiseOrderSummarySnapshot.make,
            OwnerWiseOrderSummarySnapshot.collection
        ]
    else: # party
        group_by_cols = [
            OwnerWiseOrderSummarySnapshot.division,
            OwnerWiseOrderSummarySnapshot.group_name,
            OwnerWiseOrderSummarySnapshot.purity,
            OwnerWiseOrderSummarySnapshot.classification,
            OwnerWiseOrderSummarySnapshot.make,
            OwnerWiseOrderSummarySnapshot.collection,
            OwnerWiseOrderSummarySnapshot.supplier
        ]
    
    main_q = main_q.group_by(*group_by_cols).order_by(*order_cols)
    pagination = main_q.paginate(page=page, per_page=per_page, error_out=False)

    return render_template(f'partials/_view_{view_type}.html', 
                         rows=pagination.items if pagination else [], 
                         pagination=pagination, 
                         footer_totals=footer_totals,
                         stats=stats)
