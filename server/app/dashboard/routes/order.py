from flask import render_template, request, jsonify, session
from flask_jwt_extended import jwt_required
from app.dashboard import dashboard_bp
from app.models import Notification, OwnerWiseOrderSummarySnapshot, TicketLogSnapshot
from app.extensions import db
from sqlalchemy import func
from datetime import datetime
from zoneinfo import ZoneInfo
import time


@dashboard_bp.route('/orderstatus')
def order_status():
    unread_count = Notification.query.filter_by(is_read=False).count()
    sync_time = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%I:%M %p")

    per_page = request.args.get('per_page', 50, type=int)
    pagination = {'per_page': per_page, 'page': 1, 'total': 0, 'has_prev': False, 'has_next': False}
    return render_template('order_status.html',
                           unread_count=unread_count,
                           sync_time=sync_time,
                           stats={},
                           rows=[],
                           pagination=pagination, # Minimal object for select
                           footer_totals={})

@dashboard_bp.route('/api/orderstatus/options')
@jwt_required()
def order_status_options():
    is_admin = session.get('is_admin', False)
    username = session.get('username')
    
    def apply_options_filter(q):
        roles = [r.upper() for r in session.get('roles', [])]
        is_manager_2 = 'MANAGER_2' in roles
        if not is_admin and not is_manager_2 and username:
            u = username.strip().lower()
            return q.filter(
                (func.lower(func.trim(OwnerWiseOrderSummarySnapshot.make_owner)) == u) |
                (func.lower(func.trim(OwnerWiseOrderSummarySnapshot.collection_owner)) == u) |
                (func.lower(func.trim(OwnerWiseOrderSummarySnapshot.classification_owner)) == u)
            )
        return q

    options = {
        'divisions': [r[0] for r in apply_options_filter(db.session.query(OwnerWiseOrderSummarySnapshot.division.distinct())).order_by(OwnerWiseOrderSummarySnapshot.division).all() if r[0]],
        'groups': [r[0] for r in apply_options_filter(db.session.query(OwnerWiseOrderSummarySnapshot.group_name.distinct())).order_by(OwnerWiseOrderSummarySnapshot.group_name).all() if r[0]],
        'purities': [str(r[0]) for r in apply_options_filter(db.session.query(OwnerWiseOrderSummarySnapshot.purity.distinct())).order_by(OwnerWiseOrderSummarySnapshot.purity).all() if r[0]],
        'classifications': [r[0] for r in apply_options_filter(db.session.query(OwnerWiseOrderSummarySnapshot.classification.distinct())).order_by(OwnerWiseOrderSummarySnapshot.classification).all() if r[0]],
        'makes': [r[0] for r in apply_options_filter(db.session.query(OwnerWiseOrderSummarySnapshot.make.distinct())).order_by(OwnerWiseOrderSummarySnapshot.make).all() if r[0]],
        'collections': [r[0] for r in apply_options_filter(db.session.query(OwnerWiseOrderSummarySnapshot.collection.distinct())).order_by(OwnerWiseOrderSummarySnapshot.collection).all() if r[0]],
        'parties': [r[0] for r in apply_options_filter(db.session.query(OwnerWiseOrderSummarySnapshot.supplier.distinct())).order_by(OwnerWiseOrderSummarySnapshot.supplier).all() if r[0]],
        'make_owners': [r[0] for r in apply_options_filter(db.session.query(OwnerWiseOrderSummarySnapshot.make_owner.distinct())).order_by(OwnerWiseOrderSummarySnapshot.make_owner).all() if r[0]],
        'collection_owners': [r[0] for r in apply_options_filter(db.session.query(OwnerWiseOrderSummarySnapshot.collection_owner.distinct())).order_by(OwnerWiseOrderSummarySnapshot.collection_owner).all() if r[0]],
        'classification_owners': [r[0] for r in apply_options_filter(db.session.query(OwnerWiseOrderSummarySnapshot.classification_owner.distinct())).order_by(OwnerWiseOrderSummarySnapshot.classification_owner).all() if r[0]],
        'business_heads': []
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

        # User-based filtering: Restrict to any owner = username if not admin or MANAGER_2
        is_admin = session.get('is_admin', False)
        username = session.get('username')
        roles = [r.upper() for r in session.get('roles', [])]
        is_manager_2 = 'MANAGER_2' in roles
        from flask import current_app
        if not is_admin and not is_manager_2 and username:
            u = username.strip().lower()
            current_app.logger.info(f'Applying restricted owner filter for {u}')
            query = query.filter(
                (func.lower(func.trim(OwnerWiseOrderSummarySnapshot.make_owner)) == u) |
                (func.lower(func.trim(OwnerWiseOrderSummarySnapshot.collection_owner)) == u) |
                (func.lower(func.trim(OwnerWiseOrderSummarySnapshot.classification_owner)) == u)
            )
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
    
    # Global Stats Aggregates
    agg_q = db.session.query(
        func.sum(OwnerWiseOrderSummarySnapshot.ordered_pcs).label('ordered_pcs'),
        func.sum(OwnerWiseOrderSummarySnapshot.ordered_wt).label('ordered_wt'),
        func.sum(OwnerWiseOrderSummarySnapshot.accepted_pcs).label('accepted_pcs'),
        func.sum(OwnerWiseOrderSummarySnapshot.accepted_wt).label('accepted_wt'),
        func.sum(OwnerWiseOrderSummarySnapshot.rejected_pcs).label('rejected_pcs'),
        func.sum(OwnerWiseOrderSummarySnapshot.rejected_wt).label('rejected_wt'),
        func.sum(OwnerWiseOrderSummarySnapshot.barcoded_pcs).label('barcoded_pcs'),
        func.sum(OwnerWiseOrderSummarySnapshot.barcoded_wt).label('barcoded_wt'),
        func.sum(OwnerWiseOrderSummarySnapshot.hm_passed_pcs).label('hallmarked_pcs'),
        func.sum(OwnerWiseOrderSummarySnapshot.hm_passed_wt).label('hallmarked_wt'),
        func.sum(OwnerWiseOrderSummarySnapshot.qc_passed_pcs).label('qc_passed_pcs'),
        func.sum(OwnerWiseOrderSummarySnapshot.qc_passed_wt).label('qc_passed_wt'),
        func.sum(OwnerWiseOrderSummarySnapshot.invoiced_pcs).label('invoiced_pcs'),
        func.sum(OwnerWiseOrderSummarySnapshot.invoiced_wt).label('invoiced_wt'),
        func.sum(OwnerWiseOrderSummarySnapshot.delivered_pcs).label('delivered_pcs'),
        func.sum(OwnerWiseOrderSummarySnapshot.delivered_wt).label('delivered_wt'),
        func.sum(OwnerWiseOrderSummarySnapshot.pending_to_be_delv_pcs).label('pending_to_be_delv_pcs'),
        func.sum(OwnerWiseOrderSummarySnapshot.pending_to_be_delv_wt).label('pending_to_be_delv_wt')
    )
    agg_q = apply_filters(agg_q)
    aggs = agg_q.first()

    stats = {
        'total_orders': f"{aggs.ordered_pcs or 0:,.0f}",
        'accepted': f"{aggs.accepted_pcs or 0:,.0f}",
        'rejected': f"{aggs.rejected_pcs or 0:,.0f}",
        'barcoded': f"{aggs.barcoded_pcs or 0:,.0f}",
        'hallmarked': f"{aggs.hallmarked_pcs or 0:,.0f}",
        'qc_passed': f"{aggs.qc_passed_pcs or 0:,.0f}",
        'invoiced': f"{aggs.invoiced_pcs or 0:,.0f}",
        'delivered': f"{aggs.delivered_pcs or 0:,.0f}",
        
        'ordered_pcs': f"{aggs.ordered_pcs or 0:,.0f}",
        'ordered_wt': f"{aggs.ordered_wt or 0:,.3f}",
        'accepted_pcs': f"{aggs.accepted_pcs or 0:,.0f}",
        'accepted_wt': f"{aggs.accepted_wt or 0:,.3f}",
        'rejected_pcs': f"{aggs.rejected_pcs or 0:,.0f}",
        'rejected_wt': f"{aggs.rejected_wt or 0:,.3f}",
        'barcoded_pcs': f"{aggs.barcoded_pcs or 0:,.0f}",
        'barcoded_wt': f"{aggs.barcoded_wt or 0:,.3f}",
        'hallmarked_pcs': f"{aggs.hallmarked_pcs or 0:,.0f}",
        'hallmarked_wt': f"{aggs.hallmarked_wt or 0:,.3f}",
        'qc_passed_pcs': f"{aggs.qc_passed_pcs or 0:,.0f}",
        'qc_passed_wt': f"{aggs.qc_passed_wt or 0:,.3f}",
        'invoiced_pcs': f"{aggs.invoiced_pcs or 0:,.0f}",
        'invoiced_wt': f"{aggs.invoiced_wt or 0:,.3f}",
        'delivered_pcs': f"{aggs.delivered_pcs or 0:,.0f}",
        'delivered_wt': f"{aggs.delivered_wt or 0:,.3f}",
        'pending_to_be_delv_pcs': f"{aggs.pending_to_be_delv_pcs or 0:,.0f}",
        'pending_to_be_delv_wt': f"{aggs.pending_to_be_delv_wt or 0:,.3f}"
    }

    footer_totals = {
        'a': stats['ordered_pcs'],
        'b': stats['accepted_pcs'],
        'c': stats['barcoded_pcs'],
        'd': stats['hallmarked_pcs'],
        'e': stats['qc_passed_pcs'],
        'f': stats['invoiced_pcs'],
        'g': stats['delivered_pcs'],
        'total': stats['ordered_pcs']
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


