from flask import render_template, request, jsonify, session
from flask_jwt_extended import jwt_required
from app.dashboard import dashboard_bp
from app.models import Notification, OwnerWiseOrderSummarySnapshot
from app.extensions import db
from sqlalchemy import func
from sqlalchemy.sql import literal_column
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

@dashboard_bp.route('/orderpendingrejection')
def order_pending_rejection_summary():
    try:
        unread_count = Notification.query.filter_by(is_read=False).count()
        sync_time = datetime.now().strftime("%H:%M")

        # Filters
        search = request.args.get('search', '').strip()
        division = request.args.get('division', '')
        group_name = request.args.get('group', '')
        purity = request.args.get('purity', '')
        supplier = request.args.get('supplier', '')
        classification_owner = request.args.get('classification_owner', '')
        collection_owner = request.args.get('collection_owner', '')
        make_owner = request.args.get('make_owner', '')
        classification = request.args.get('classification', '')
        make = request.args.get('make', '')
        collection = request.args.get('collection', '')
        order_ro = request.args.get('order_ro', '')
        order_request_type = request.args.get('order_request_type', '')
        order_type = request.args.get('order_type', '')
        batch = request.args.get('batch', '')
        days = request.args.get('days', type=int) if request.args.get('days') else None
        
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)

        def apply_filters(query):
            if search:
                query = query.filter(
                    (OwnerWiseOrderSummarySnapshot.supplier.ilike(f"%{search}%")) |
                    (OwnerWiseOrderSummarySnapshot.order_ro.ilike(f"%{search}%"))
                )
            if division:
                query = query.filter(OwnerWiseOrderSummarySnapshot.division == division)
            if group_name:
                query = query.filter(OwnerWiseOrderSummarySnapshot.group_name == group_name)
            if purity:
                query = query.filter(OwnerWiseOrderSummarySnapshot.purity == purity)
            if supplier:
                query = query.filter(OwnerWiseOrderSummarySnapshot.supplier == supplier)
            if classification_owner:
                query = query.filter(OwnerWiseOrderSummarySnapshot.classification_owner == classification_owner)
            if collection_owner:
                query = query.filter(OwnerWiseOrderSummarySnapshot.collection_owner == collection_owner)
            if make_owner:
                query = query.filter(OwnerWiseOrderSummarySnapshot.make_owner == make_owner)
            if classification:
                query = query.filter(OwnerWiseOrderSummarySnapshot.classification == classification)
            if make:
                query = query.filter(OwnerWiseOrderSummarySnapshot.make == make)
            if collection:
                query = query.filter(OwnerWiseOrderSummarySnapshot.collection == collection)
            if order_ro:
                query = query.filter(OwnerWiseOrderSummarySnapshot.order_ro == order_ro)
            if order_request_type:
                query = query.filter(OwnerWiseOrderSummarySnapshot.order_request_type == order_request_type)
            if order_type:
                query = query.filter(OwnerWiseOrderSummarySnapshot.order_type == order_type)
            if batch:
                query = query.filter(OwnerWiseOrderSummarySnapshot.batch == batch)
            if days:
                query = query.filter(OwnerWiseOrderSummarySnapshot.order_date >= func.current_date() - days)
            
            # User-based filtering
            roles = [r.upper() for r in session.get('roles', [])]
            if not session.get('is_admin', False) and 'MANAGER_2' not in roles and session.get('username'):
                u = session.get('username').strip().lower()
                query = query.filter(
                    (func.lower(func.trim(OwnerWiseOrderSummarySnapshot.make_owner)) == u) |
                    (func.lower(func.trim(OwnerWiseOrderSummarySnapshot.collection_owner)) == u) |
                    (func.lower(func.trim(OwnerWiseOrderSummarySnapshot.classification_owner)) == u)
                )
            return query

        # Aggregated Metrics
        agg_cols = [
            # 1. Pending to Accept = Ordered - (Accepted + Rejected)
            func.sum(OwnerWiseOrderSummarySnapshot.ordered_pcs - OwnerWiseOrderSummarySnapshot.accepted_pcs - OwnerWiseOrderSummarySnapshot.rejected_pcs).label('pending_accept_pcs'),
            func.sum(OwnerWiseOrderSummarySnapshot.ordered_wt - OwnerWiseOrderSummarySnapshot.accepted_wt - OwnerWiseOrderSummarySnapshot.rejected_wt).label('pending_accept_wt'),
            
            # 2. Rejected
            func.sum(OwnerWiseOrderSummarySnapshot.rejected_pcs).label('rejected_pcs'),
            func.sum(OwnerWiseOrderSummarySnapshot.rejected_wt).label('rejected_wt'),
            
            # 3. Hallmark Failed
            func.sum(OwnerWiseOrderSummarySnapshot.hm_failed_pcs).label('hm_failed_pcs'),
            func.sum(OwnerWiseOrderSummarySnapshot.hm_failed_wt).label('hm_failed_wt'),
            
            # 4. Hallmark Test Cut = Hm Processed - (Hm Passed + Hm Failed)
            func.sum(OwnerWiseOrderSummarySnapshot.hm_processed_pcs - OwnerWiseOrderSummarySnapshot.hm_passed_pcs - OwnerWiseOrderSummarySnapshot.hm_failed_pcs).label('hm_test_cut_pcs'),
            func.sum(OwnerWiseOrderSummarySnapshot.hm_testcut_wt - OwnerWiseOrderSummarySnapshot.hm_passed_wt - OwnerWiseOrderSummarySnapshot.hm_failed_wt).label('hm_test_cut_wt'),
            
            # 5. QC Pending
            func.sum(OwnerWiseOrderSummarySnapshot.qc_pending_pcs).label('qc_pending_pcs'),
            func.sum(OwnerWiseOrderSummarySnapshot.qc_pending_wt).label('qc_pending_wt'),
            
            # 6. QC Rejected
            func.sum(OwnerWiseOrderSummarySnapshot.qc_rejected_pcs).label('qc_rejected_pcs'),
            func.sum(OwnerWiseOrderSummarySnapshot.qc_rejected_wt).label('qc_rejected_wt'),
            
            # 7. Not Barcoded
            func.sum(OwnerWiseOrderSummarySnapshot.not_barcoded_pcs).label('not_barcode_pcs'),
            func.sum(OwnerWiseOrderSummarySnapshot.not_barcoded_wt).label('not_barcode_wt'),
        ]

        # Global Stats
        stats_q = db.session.query(*agg_cols)
        stats_q = apply_filters(stats_q)
        stats = stats_q.first()

        # Drill-down level (Party -> Purchase RO -> Division -> Group -> Purity -> Classification -> Make -> Collection)
        if not supplier:
            group_cols = [OwnerWiseOrderSummarySnapshot.supplier]
            current_level = 'party'
        elif supplier and not order_ro:
            group_cols = [OwnerWiseOrderSummarySnapshot.supplier, OwnerWiseOrderSummarySnapshot.order_ro]
            current_level = 'purchase_ro'
        elif order_ro and not division:
            group_cols = [OwnerWiseOrderSummarySnapshot.supplier, OwnerWiseOrderSummarySnapshot.order_ro, OwnerWiseOrderSummarySnapshot.division]
            current_level = 'division'
        elif division and not group_name:
            group_cols = [OwnerWiseOrderSummarySnapshot.supplier, OwnerWiseOrderSummarySnapshot.order_ro, OwnerWiseOrderSummarySnapshot.division, OwnerWiseOrderSummarySnapshot.group_name]
            current_level = 'group'
        elif group_name and not purity:
            group_cols = [OwnerWiseOrderSummarySnapshot.supplier, OwnerWiseOrderSummarySnapshot.order_ro, OwnerWiseOrderSummarySnapshot.division, OwnerWiseOrderSummarySnapshot.group_name, OwnerWiseOrderSummarySnapshot.purity]
            current_level = 'purity'
        elif purity and not classification:
            group_cols = [OwnerWiseOrderSummarySnapshot.supplier, OwnerWiseOrderSummarySnapshot.order_ro, OwnerWiseOrderSummarySnapshot.division, OwnerWiseOrderSummarySnapshot.group_name, OwnerWiseOrderSummarySnapshot.purity, OwnerWiseOrderSummarySnapshot.classification]
            current_level = 'classification'
        elif classification and not make:
            group_cols = [OwnerWiseOrderSummarySnapshot.supplier, OwnerWiseOrderSummarySnapshot.order_ro, OwnerWiseOrderSummarySnapshot.division, OwnerWiseOrderSummarySnapshot.group_name, OwnerWiseOrderSummarySnapshot.purity, OwnerWiseOrderSummarySnapshot.classification, OwnerWiseOrderSummarySnapshot.make]
            current_level = 'make'
        else:
            group_cols = [OwnerWiseOrderSummarySnapshot.supplier, OwnerWiseOrderSummarySnapshot.order_ro, OwnerWiseOrderSummarySnapshot.division, OwnerWiseOrderSummarySnapshot.group_name, OwnerWiseOrderSummarySnapshot.purity, OwnerWiseOrderSummarySnapshot.classification, OwnerWiseOrderSummarySnapshot.make, OwnerWiseOrderSummarySnapshot.collection]
            current_level = 'collection'

        main_q = db.session.query(*(group_cols + agg_cols))
        main_q = apply_filters(main_q)
        main_q = main_q.group_by(*group_cols).order_by(*group_cols)
        
        pagination = main_q.paginate(page=page, per_page=per_page, error_out=False)
        
        # Fetch Filter Options
        def get_distinct(column):
            return [r[0] for r in db.session.query(column).distinct().filter(column != None).order_by(column).all() if r[0]]

        filter_options = {
            'classification_owners': get_distinct(OwnerWiseOrderSummarySnapshot.classification_owner),
            'make_owners': get_distinct(OwnerWiseOrderSummarySnapshot.make_owner),
            'collection_owners': get_distinct(OwnerWiseOrderSummarySnapshot.collection_owner),
            'classifications': get_distinct(OwnerWiseOrderSummarySnapshot.classification),
            'makes': get_distinct(OwnerWiseOrderSummarySnapshot.make),
            'collections': get_distinct(OwnerWiseOrderSummarySnapshot.collection),
            'purchase_ros': get_distinct(OwnerWiseOrderSummarySnapshot.order_ro),
            'parties': get_distinct(OwnerWiseOrderSummarySnapshot.supplier),
            'batches': get_distinct(OwnerWiseOrderSummarySnapshot.batch),
            'order_types': get_distinct(OwnerWiseOrderSummarySnapshot.order_type),
            'order_request_types': get_distinct(OwnerWiseOrderSummarySnapshot.order_request_type),
        }

        processed_rows = []
        for r in pagination.items:
            row = {
                'party': r[0] or 'Unknown',
                'purchase_ro': r[1] if current_level in ['purchase_ro', 'division', 'group', 'purity', 'classification', 'make', 'collection'] else '',
                'division': r[2] if current_level in ['division', 'group', 'purity', 'classification', 'make', 'collection'] else '',
                'group': r[3] if current_level in ['group', 'purity', 'classification', 'make', 'collection'] else '',
                'purity': str(r[4]) if current_level in ['purity', 'classification', 'make', 'collection'] else '',
                'classification': r[5] if current_level in ['classification', 'make', 'collection'] else '',
                'make': r[6] if current_level in ['make', 'collection'] else '',
                'collection': r[7] if current_level == 'collection' else '',
                
                'pending_accept_pcs': int(r.pending_accept_pcs or 0),
                'pending_accept_wt': float(r.pending_accept_wt or 0),
                'rejected_pcs': int(r.rejected_pcs or 0),
                'rejected_wt': float(r.rejected_wt or 0),
                'hm_failed_pcs': int(r.hm_failed_pcs or 0),
                'hm_failed_wt': float(r.hm_failed_wt or 0),
                'hm_test_cut_pcs': int(r.hm_test_cut_pcs or 0),
                'hm_test_cut_wt': float(r.hm_test_cut_wt or 0),
                'qc_pending_pcs': int(r.qc_pending_pcs or 0),
                'qc_pending_wt': float(r.qc_pending_wt or 0),
                'qc_rejected_pcs': int(r.qc_rejected_pcs or 0),
                'qc_rejected_wt': float(r.qc_rejected_wt or 0),
                'not_barcode_pcs': int(r.not_barcode_pcs or 0),
                'not_barcode_wt': float(r.not_barcode_wt or 0),
                'level': current_level
            }
            processed_rows.append(row)

        return render_template('order_pending_rejection.html', 
                             unread_count=unread_count, 
                             sync_time=sync_time, 
                             stats=stats, 
                             rows=processed_rows, 
                             pagination=pagination, 
                             current_level=current_level,
                             filter_options=filter_options)
    except Exception as e:
        logger.error(f"Error in order_pending_rejection_summary: {str(e)}")
        return f"Error: {str(e)}", 500

@dashboard_bp.route('/partial/orderpendingrejection')
@jwt_required()
def get_order_pending_rejection_partial():
    try:
        search = request.args.get('search', '').strip()
        division = request.args.get('division', '')
        group_name = request.args.get('group', '')
        purity = request.args.get('purity', '')
        supplier = request.args.get('supplier', '')
        classification_owner = request.args.get('classification_owner', '')
        collection_owner = request.args.get('collection_owner', '')
        make_owner = request.args.get('make_owner', '')
        classification = request.args.get('classification', '')
        make = request.args.get('make', '')
        collection = request.args.get('collection', '')
        order_ro = request.args.get('order_ro', '')
        order_request_type = request.args.get('order_request_type', '')
        order_type = request.args.get('order_type', '')
        batch = request.args.get('batch', '')
        days = request.args.get('days', type=int) if request.args.get('days') else None

        parent_level = request.args.get('parent_level')
        parent_value = request.args.get('parent_value')
        
        # Grandparents for uniqueness
        grandparent_party = request.args.get('grandparent_party')
        grandparent_ro = request.args.get('grandparent_ro')
        grandparent_division = request.args.get('grandparent_division')
        grandparent_group = request.args.get('grandparent_group')
        grandparent_purity = request.args.get('grandparent_purity')
        grandparent_classification = request.args.get('grandparent_classification')
        grandparent_make = request.args.get('grandparent_make')

        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)
        
        is_child_rows = bool(parent_level)

        def apply_filters(query):
            if search:
                query = query.filter(
                    (OwnerWiseOrderSummarySnapshot.supplier.ilike(f"%{search}%")) |
                    (OwnerWiseOrderSummarySnapshot.order_ro.ilike(f"%{search}%"))
                )
            if division:
                query = query.filter(OwnerWiseOrderSummarySnapshot.division == division)
            if group_name:
                query = query.filter(OwnerWiseOrderSummarySnapshot.group_name == group_name)
            if purity:
                query = query.filter(OwnerWiseOrderSummarySnapshot.purity == purity)
            if supplier:
                query = query.filter(OwnerWiseOrderSummarySnapshot.supplier == supplier)
            if classification_owner:
                query = query.filter(OwnerWiseOrderSummarySnapshot.classification_owner == classification_owner)
            if collection_owner:
                query = query.filter(OwnerWiseOrderSummarySnapshot.collection_owner == collection_owner)
            if make_owner:
                query = query.filter(OwnerWiseOrderSummarySnapshot.make_owner == make_owner)
            if classification:
                query = query.filter(OwnerWiseOrderSummarySnapshot.classification == classification)
            if make:
                query = query.filter(OwnerWiseOrderSummarySnapshot.make == make)
            if collection:
                query = query.filter(OwnerWiseOrderSummarySnapshot.collection == collection)
            if order_ro:
                query = query.filter(OwnerWiseOrderSummarySnapshot.order_ro == order_ro)
            if order_request_type:
                query = query.filter(OwnerWiseOrderSummarySnapshot.order_request_type == order_request_type)
            if order_type:
                query = query.filter(OwnerWiseOrderSummarySnapshot.order_type == order_type)
            if batch:
                query = query.filter(OwnerWiseOrderSummarySnapshot.batch == batch)
            if days:
                query = query.filter(OwnerWiseOrderSummarySnapshot.order_date >= func.current_date() - days)
            
            roles = [r.upper() for r in session.get('roles', [])]
            if not session.get('is_admin', False) and 'MANAGER_2' not in roles and session.get('username'):
                u = session.get('username').strip().lower()
                query = query.filter(
                    (func.lower(func.trim(OwnerWiseOrderSummarySnapshot.make_owner)) == u) |
                    (func.lower(func.trim(OwnerWiseOrderSummarySnapshot.collection_owner)) == u) |
                    (func.lower(func.trim(OwnerWiseOrderSummarySnapshot.classification_owner)) == u)
                )
            return query

        # Determine level and base query
        if parent_level == 'party':
            group_cols = [OwnerWiseOrderSummarySnapshot.supplier, OwnerWiseOrderSummarySnapshot.order_ro]
            level = 'purchase_ro'
            base_query = db.session.query(OwnerWiseOrderSummarySnapshot).filter(OwnerWiseOrderSummarySnapshot.supplier == parent_value)
        elif parent_level == 'purchase_ro':
            group_cols = [OwnerWiseOrderSummarySnapshot.supplier, OwnerWiseOrderSummarySnapshot.order_ro, OwnerWiseOrderSummarySnapshot.division]
            level = 'division'
            base_query = db.session.query(OwnerWiseOrderSummarySnapshot).filter(OwnerWiseOrderSummarySnapshot.order_ro == parent_value)
            if grandparent_party: base_query = base_query.filter(OwnerWiseOrderSummarySnapshot.supplier == grandparent_party)
        elif parent_level == 'division':
            group_cols = [OwnerWiseOrderSummarySnapshot.supplier, OwnerWiseOrderSummarySnapshot.order_ro, OwnerWiseOrderSummarySnapshot.division, OwnerWiseOrderSummarySnapshot.group_name]
            level = 'group'
            base_query = db.session.query(OwnerWiseOrderSummarySnapshot).filter(OwnerWiseOrderSummarySnapshot.division == parent_value)
            if grandparent_ro: base_query = base_query.filter(OwnerWiseOrderSummarySnapshot.order_ro == grandparent_ro)
            if grandparent_party: base_query = base_query.filter(OwnerWiseOrderSummarySnapshot.supplier == grandparent_party)
        elif parent_level == 'group':
            group_cols = [OwnerWiseOrderSummarySnapshot.supplier, OwnerWiseOrderSummarySnapshot.order_ro, OwnerWiseOrderSummarySnapshot.division, OwnerWiseOrderSummarySnapshot.group_name, OwnerWiseOrderSummarySnapshot.purity]
            level = 'purity'
            base_query = db.session.query(OwnerWiseOrderSummarySnapshot).filter(OwnerWiseOrderSummarySnapshot.group_name == parent_value)
            if grandparent_division: base_query = base_query.filter(OwnerWiseOrderSummarySnapshot.division == grandparent_division)
            if grandparent_ro: base_query = base_query.filter(OwnerWiseOrderSummarySnapshot.order_ro == grandparent_ro)
            if grandparent_party: base_query = base_query.filter(OwnerWiseOrderSummarySnapshot.supplier == grandparent_party)
        elif parent_level == 'purity':
            group_cols = [OwnerWiseOrderSummarySnapshot.supplier, OwnerWiseOrderSummarySnapshot.order_ro, OwnerWiseOrderSummarySnapshot.division, OwnerWiseOrderSummarySnapshot.group_name, OwnerWiseOrderSummarySnapshot.purity, OwnerWiseOrderSummarySnapshot.classification]
            level = 'classification'
            base_query = db.session.query(OwnerWiseOrderSummarySnapshot).filter(OwnerWiseOrderSummarySnapshot.purity == parent_value)
            if grandparent_group: base_query = base_query.filter(OwnerWiseOrderSummarySnapshot.group_name == grandparent_group)
            if grandparent_division: base_query = base_query.filter(OwnerWiseOrderSummarySnapshot.division == grandparent_division)
            if grandparent_ro: base_query = base_query.filter(OwnerWiseOrderSummarySnapshot.order_ro == grandparent_ro)
            if grandparent_party: base_query = base_query.filter(OwnerWiseOrderSummarySnapshot.supplier == grandparent_party)
        elif parent_level == 'classification':
            group_cols = [OwnerWiseOrderSummarySnapshot.supplier, OwnerWiseOrderSummarySnapshot.order_ro, OwnerWiseOrderSummarySnapshot.division, OwnerWiseOrderSummarySnapshot.group_name, OwnerWiseOrderSummarySnapshot.purity, OwnerWiseOrderSummarySnapshot.classification, OwnerWiseOrderSummarySnapshot.make]
            level = 'make'
            base_query = db.session.query(OwnerWiseOrderSummarySnapshot).filter(OwnerWiseOrderSummarySnapshot.classification == parent_value)
            if grandparent_purity: base_query = base_query.filter(OwnerWiseOrderSummarySnapshot.purity == grandparent_purity)
            if grandparent_group: base_query = base_query.filter(OwnerWiseOrderSummarySnapshot.group_name == grandparent_group)
            if grandparent_division: base_query = base_query.filter(OwnerWiseOrderSummarySnapshot.division == grandparent_division)
            if grandparent_ro: base_query = base_query.filter(OwnerWiseOrderSummarySnapshot.order_ro == grandparent_ro)
            if grandparent_party: base_query = base_query.filter(OwnerWiseOrderSummarySnapshot.supplier == grandparent_party)
        elif parent_level == 'make':
            group_cols = [OwnerWiseOrderSummarySnapshot.supplier, OwnerWiseOrderSummarySnapshot.order_ro, OwnerWiseOrderSummarySnapshot.division, OwnerWiseOrderSummarySnapshot.group_name, OwnerWiseOrderSummarySnapshot.purity, OwnerWiseOrderSummarySnapshot.classification, OwnerWiseOrderSummarySnapshot.make, OwnerWiseOrderSummarySnapshot.collection]
            level = 'collection'
            base_query = db.session.query(OwnerWiseOrderSummarySnapshot).filter(OwnerWiseOrderSummarySnapshot.make == parent_value)
            if grandparent_classification: base_query = base_query.filter(OwnerWiseOrderSummarySnapshot.classification == grandparent_classification)
            if grandparent_purity: base_query = base_query.filter(OwnerWiseOrderSummarySnapshot.purity == grandparent_purity)
            if grandparent_group: base_query = base_query.filter(OwnerWiseOrderSummarySnapshot.group_name == grandparent_group)
            if grandparent_division: base_query = base_query.filter(OwnerWiseOrderSummarySnapshot.division == grandparent_division)
            if grandparent_ro: base_query = base_query.filter(OwnerWiseOrderSummarySnapshot.order_ro == grandparent_ro)
            if grandparent_party: base_query = base_query.filter(OwnerWiseOrderSummarySnapshot.supplier == grandparent_party)
        else:
            group_cols = [OwnerWiseOrderSummarySnapshot.supplier]
            level = 'party'
            base_query = db.session.query(OwnerWiseOrderSummarySnapshot)

        agg_cols = [
            func.sum(OwnerWiseOrderSummarySnapshot.ordered_pcs - OwnerWiseOrderSummarySnapshot.accepted_pcs - OwnerWiseOrderSummarySnapshot.rejected_pcs).label('pending_accept_pcs'),
            func.sum(OwnerWiseOrderSummarySnapshot.ordered_wt - OwnerWiseOrderSummarySnapshot.accepted_wt - OwnerWiseOrderSummarySnapshot.rejected_wt).label('pending_accept_wt'),
            func.sum(OwnerWiseOrderSummarySnapshot.rejected_pcs).label('rejected_pcs'),
            func.sum(OwnerWiseOrderSummarySnapshot.rejected_wt).label('rejected_wt'),
            func.sum(OwnerWiseOrderSummarySnapshot.hm_failed_pcs).label('hm_failed_pcs'),
            func.sum(OwnerWiseOrderSummarySnapshot.hm_failed_wt).label('hm_failed_wt'),
            func.sum(OwnerWiseOrderSummarySnapshot.hm_processed_pcs - OwnerWiseOrderSummarySnapshot.hm_passed_pcs - OwnerWiseOrderSummarySnapshot.hm_failed_pcs).label('hm_test_cut_pcs'),
            func.sum(OwnerWiseOrderSummarySnapshot.hm_testcut_wt - OwnerWiseOrderSummarySnapshot.hm_passed_wt - OwnerWiseOrderSummarySnapshot.hm_failed_wt).label('hm_test_cut_wt'),
            func.sum(OwnerWiseOrderSummarySnapshot.qc_pending_pcs).label('qc_pending_pcs'),
            func.sum(OwnerWiseOrderSummarySnapshot.qc_pending_wt).label('qc_pending_wt'),
            func.sum(OwnerWiseOrderSummarySnapshot.qc_rejected_pcs).label('qc_rejected_pcs'),
            func.sum(OwnerWiseOrderSummarySnapshot.qc_rejected_wt).label('qc_rejected_wt'),
            func.sum(OwnerWiseOrderSummarySnapshot.not_barcoded_pcs).label('not_barcode_pcs'),
            func.sum(OwnerWiseOrderSummarySnapshot.not_barcoded_wt).label('not_barcode_wt'),
        ]

        main_q = base_query.with_entities(*(group_cols + agg_cols))
        main_q = apply_filters(main_q)
        main_q = main_q.group_by(*group_cols).order_by(*group_cols)

        # Global stats for the footer (only for main table load)
        stats = None
        if not is_child_rows:
            stats_q = db.session.query(*agg_cols)
            # Use a fresh query for global stats with same filters but no parent filters
            from sqlalchemy.orm import Query
            global_stats_q = db.session.query(OwnerWiseOrderSummarySnapshot).with_entities(*agg_cols)
            # Need a version of apply_filters that doesn't use the localized base_query
            # Actually, I can just use the same logic as the main route
            def apply_global_filters(q):
                if search:
                    q = q.filter(
                        (OwnerWiseOrderSummarySnapshot.supplier.ilike(f"%{search}%")) |
                        (OwnerWiseOrderSummarySnapshot.order_ro.ilike(f"%{search}%"))
                    )
                if division: q = q.filter(OwnerWiseOrderSummarySnapshot.division == division)
                if group_name: q = q.filter(OwnerWiseOrderSummarySnapshot.group_name == group_name)
                if purity: q = q.filter(OwnerWiseOrderSummarySnapshot.purity == purity)
                if supplier: q = q.filter(OwnerWiseOrderSummarySnapshot.supplier == supplier)
                if classification_owner: q = q.filter(OwnerWiseOrderSummarySnapshot.classification_owner == classification_owner)
                if collection_owner: q = q.filter(OwnerWiseOrderSummarySnapshot.collection_owner == collection_owner)
                if make_owner: q = q.filter(OwnerWiseOrderSummarySnapshot.make_owner == make_owner)
                if classification: q = q.filter(OwnerWiseOrderSummarySnapshot.classification == classification)
                if make: q = q.filter(OwnerWiseOrderSummarySnapshot.make == make)
                if collection: q = q.filter(OwnerWiseOrderSummarySnapshot.collection == collection)
                if order_ro: q = q.filter(OwnerWiseOrderSummarySnapshot.order_ro == order_ro)
                if order_request_type: q = q.filter(OwnerWiseOrderSummarySnapshot.order_request_type == order_request_type)
                if order_type: q = q.filter(OwnerWiseOrderSummarySnapshot.order_type == order_type)
                if batch: q = q.filter(OwnerWiseOrderSummarySnapshot.batch == batch)
                
                roles = [r.upper() for r in session.get('roles', [])]
                if not session.get('is_admin', False) and 'MANAGER_2' not in roles and session.get('username'):
                    u = session.get('username').strip().lower()
                    q = q.filter(
                        (func.lower(func.trim(OwnerWiseOrderSummarySnapshot.make_owner)) == u) |
                        (func.lower(func.trim(OwnerWiseOrderSummarySnapshot.collection_owner)) == u) |
                        (func.lower(func.trim(OwnerWiseOrderSummarySnapshot.classification_owner)) == u)
                    )
                return q
            
            global_stats_q = apply_global_filters(global_stats_q)
            stats = global_stats_q.first()
        
        pagination = main_q.paginate(page=page, per_page=per_page, error_out=False)

        processed_rows = []
        for r in pagination.items:
            row = {
                'party': r[0] or 'Unknown',
                'purchase_ro': r[1] if level in ['purchase_ro', 'division', 'group', 'purity', 'classification', 'make', 'collection'] else '',
                'division': r[2] if level in ['division', 'group', 'purity', 'classification', 'make', 'collection'] else '',
                'group': r[3] if level in ['group', 'purity', 'classification', 'make', 'collection'] else '',
                'purity': str(r[4]) if level in ['purity', 'classification', 'make', 'collection'] else '',
                'classification': r[5] if level in ['classification', 'make', 'collection'] else '',
                'make': r[6] if level in ['make', 'collection'] else '',
                'collection': r[7] if level == 'collection' else '',
                
                'pending_accept_pcs': int(r.pending_accept_pcs or 0),
                'pending_accept_wt': float(r.pending_accept_wt or 0),
                'rejected_pcs': int(r.rejected_pcs or 0),
                'rejected_wt': float(r.rejected_wt or 0),
                'hm_failed_pcs': int(r.hm_failed_pcs or 0),
                'hm_failed_wt': float(r.hm_failed_wt or 0),
                'hm_test_cut_pcs': int(r.hm_test_cut_pcs or 0),
                'hm_test_cut_wt': float(r.hm_test_cut_wt or 0),
                'qc_pending_pcs': int(r.qc_pending_pcs or 0),
                'qc_pending_wt': float(r.qc_pending_wt or 0),
                'qc_rejected_pcs': int(r.qc_rejected_pcs or 0),
                'qc_rejected_wt': float(r.qc_rejected_wt or 0),
                'not_barcode_pcs': int(r.not_barcode_pcs or 0),
                'not_barcode_wt': float(r.not_barcode_wt or 0),
                'level': level
            }
            processed_rows.append(row)

        return render_template('partials/_view_order_pending_rejection.html', 
                             rows=processed_rows, 
                             pagination=pagination if not is_child_rows else None, 
                             current_level=level,
                             is_child_rows=is_child_rows,
                             parent_level=parent_level,
                             parent_value=parent_value,
                             stats=stats)
    except Exception as e:
        logger.error(f"Error in get_order_pending_rejection_partial: {str(e)}")
        return f'<div class="p-8 text-center text-red-500 font-bold">Backend Error: {str(e)}</div>', 200
