from flask import render_template, request, jsonify, session
from flask_jwt_extended import jwt_required
from app.dashboard import dashboard_bp
from app.models import Notification, PendingOrderDetailsSnapshot, OwnerWiseOrderSummarySnapshot
from app.extensions import db
from sqlalchemy import func
from datetime import datetime
from zoneinfo import ZoneInfo
import logging

logger = logging.getLogger(__name__)

def split_filter_values(value):
    return [v.strip() for v in (value or '').split(',') if v.strip()]

def apply_make_filter(query, make):
    makes = split_filter_values(make)
    if not makes:
        return query
    if len(makes) == 1:
        return query.filter(PendingOrderDetailsSnapshot.make == makes[0])
    return query.filter(PendingOrderDetailsSnapshot.make.in_(makes))

def get_owner_names_by_emp_code(emp_code):
    if not emp_code:
        return []
    names = []
    try:
        rows = db.session.query(OwnerWiseOrderSummarySnapshot.make_owner).filter(
            func.trim(OwnerWiseOrderSummarySnapshot.make_owner_emp_code) == emp_code
        ).distinct().all()
        names.extend([r[0] for r in rows if r[0]])
        
        rows2 = db.session.query(OwnerWiseOrderSummarySnapshot.collection_owner).filter(
            func.trim(OwnerWiseOrderSummarySnapshot.collection_owner_emp_code) == emp_code
        ).distinct().all()
        names.extend([r[0] for r in rows2 if r[0]])
    except Exception as e:
        logger.error(f"Error fetching owner names for user {emp_code}: {e}")
    return list(set(names))

def apply_owner_visibility_filter(query):
    user_id = str(session.get('user_id') or '').strip()
    names = get_owner_names_by_emp_code(user_id)
    if names:
        return query.filter(
            (PendingOrderDetailsSnapshot.make_owner.in_(names)) |
            (PendingOrderDetailsSnapshot.collection_owner.in_(names)) |
            (PendingOrderDetailsSnapshot.classification_owner.in_(names))
        )
    return query

@dashboard_bp.route('/pendingorderdetails')
def pending_order_details():
    try:
        unread_count = Notification.query.filter_by(is_read=False).count()
        sync_time = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%I:%M %p")

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
        order_type = request.args.get('order_type', '')
        order_ro = request.args.get('order_ro', '')
        order_request_type = request.args.get('order_request_type', '')
        provision_type = request.args.get('provision_type', '')
        branch_provision_type = request.args.get('branch_provision_type', '')
        branch_type = request.args.get('branch_type', '')

        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)

        def apply_filters(query):
            if search:
                query = query.filter(
                    (PendingOrderDetailsSnapshot.classification_owner.ilike(f"%{search}%")) |
                    (PendingOrderDetailsSnapshot.collection_owner.ilike(f"%{search}%")) |
                    (PendingOrderDetailsSnapshot.make_owner.ilike(f"%{search}%")) |
                    (PendingOrderDetailsSnapshot.collection.ilike(f"%{search}%")) |
                    (PendingOrderDetailsSnapshot.supplier.ilike(f"%{search}%"))
                )
            if division:
                query = query.filter(PendingOrderDetailsSnapshot.division == division)
            if group_name:
                query = query.filter(PendingOrderDetailsSnapshot.group_name == group_name)
            if purity:
                query = query.filter(PendingOrderDetailsSnapshot.purity == purity)
            if supplier:
                query = query.filter(PendingOrderDetailsSnapshot.supplier == supplier)
            if classification_owner:
                query = query.filter(PendingOrderDetailsSnapshot.classification_owner == classification_owner)
            if collection_owner:
                query = query.filter(PendingOrderDetailsSnapshot.collection_owner == collection_owner)
            if make_owner:
                query = query.filter(PendingOrderDetailsSnapshot.make_owner == make_owner)
            if classification:
                query = query.filter(PendingOrderDetailsSnapshot.classification == classification)
            query = apply_make_filter(query, make)
            if order_type:
                query = query.filter(PendingOrderDetailsSnapshot.order_type == order_type)
            if order_ro:
                query = query.filter(PendingOrderDetailsSnapshot.order_ro == order_ro)
            if order_request_type:
                query = query.filter(PendingOrderDetailsSnapshot.order_request_type == order_request_type)
            if provision_type:
                query = query.filter(PendingOrderDetailsSnapshot.provision_type == provision_type)
            if branch_provision_type:
                query = query.filter(PendingOrderDetailsSnapshot.branch_provision_type == branch_provision_type)
            if branch_type:
                query = query.filter(PendingOrderDetailsSnapshot.branch_type == branch_type)
            
            roles = [r.upper() for r in session.get('roles', [])]
            is_admin = 'ADMIN' in roles
            is_manager_2 = 'MANAGER_2' in roles
            
            if not is_admin and not is_manager_2:
                if 'MANAGER_KMU' in roles:
                    query = query.filter(PendingOrderDetailsSnapshot.make.in_([
                        'KMU - KERALA', 'KMU 999 COIN', 'KMU B2B', 'KMU KARNATAKA', 
                        'KMU MH', 'KMU-COIN', 'KMU-TN'
                    ]))
                else:
                    query = apply_owner_visibility_filter(query)

            return query

        def apply_options_filter(q):
            roles = [r.upper() for r in session.get('roles', [])]
            if 'ADMIN' in roles or 'MANAGER_2' in roles:
                return q
            
            if 'MANAGER_KMU' in roles:
                return q.filter(PendingOrderDetailsSnapshot.make.in_([
                    'KMU - KERALA', 'KMU 999 COIN', 'KMU B2B', 'KMU KARNATAKA', 
                    'KMU MH', 'KMU-COIN', 'KMU-TN'
                ]))
            
            return apply_owner_visibility_filter(q)

        filter_options = {
            'divisions': [r[0] for r in apply_options_filter(db.session.query(PendingOrderDetailsSnapshot.division)).distinct().order_by(PendingOrderDetailsSnapshot.division).all() if r[0]],
            'groups': [r[0] for r in apply_options_filter(db.session.query(PendingOrderDetailsSnapshot.group_name)).distinct().order_by(PendingOrderDetailsSnapshot.group_name).all() if r[0]],
            'purities': [str(r[0]) for r in apply_options_filter(db.session.query(PendingOrderDetailsSnapshot.purity)).distinct().order_by(PendingOrderDetailsSnapshot.purity).all() if r[0]],
            'suppliers': [r[0] for r in apply_options_filter(db.session.query(PendingOrderDetailsSnapshot.supplier)).distinct().order_by(PendingOrderDetailsSnapshot.supplier).all() if r[0]],
            'classification_owners': [r[0] for r in apply_options_filter(db.session.query(PendingOrderDetailsSnapshot.classification_owner)).distinct().order_by(PendingOrderDetailsSnapshot.classification_owner).all() if r[0]],
            'collection_owners': [r[0] for r in apply_options_filter(db.session.query(PendingOrderDetailsSnapshot.collection_owner)).distinct().order_by(PendingOrderDetailsSnapshot.collection_owner).all() if r[0]],
            'make_owners': [r[0] for r in apply_options_filter(db.session.query(PendingOrderDetailsSnapshot.make_owner)).distinct().order_by(PendingOrderDetailsSnapshot.make_owner).all() if r[0]],
            'classifications': [r[0] for r in apply_options_filter(db.session.query(PendingOrderDetailsSnapshot.classification)).distinct().order_by(PendingOrderDetailsSnapshot.classification).all() if r[0]],
            'makes': [r[0] for r in apply_options_filter(db.session.query(PendingOrderDetailsSnapshot.make)).distinct().order_by(PendingOrderDetailsSnapshot.make).all() if r[0]],
            'order_types': [r[0] for r in apply_options_filter(db.session.query(PendingOrderDetailsSnapshot.order_type)).distinct().order_by(PendingOrderDetailsSnapshot.order_type).all() if r[0]],
            'order_request_types': [r[0] for r in apply_options_filter(db.session.query(PendingOrderDetailsSnapshot.order_request_type)).distinct().order_by(PendingOrderDetailsSnapshot.order_request_type).all() if r[0]],
            'provision_types': [r[0] for r in apply_options_filter(db.session.query(PendingOrderDetailsSnapshot.provision_type)).distinct().order_by(PendingOrderDetailsSnapshot.provision_type).all() if r[0]],
            'branch_provision_types': [r[0] for r in apply_options_filter(db.session.query(PendingOrderDetailsSnapshot.branch_provision_type)).distinct().order_by(PendingOrderDetailsSnapshot.branch_provision_type).all() if r[0]],
            'branch_types': [r[0] for r in apply_options_filter(db.session.query(PendingOrderDetailsSnapshot.branch_type)).distinct().order_by(PendingOrderDetailsSnapshot.branch_type).all() if r[0]],
            'order_ros': [r[0] for r in apply_options_filter(db.session.query(PendingOrderDetailsSnapshot.order_ro)).distinct().order_by(PendingOrderDetailsSnapshot.order_ro).all() if r[0]]
        }

        # Global Stats (Using total pcs/weight)
        agg_cols = [
            func.sum(PendingOrderDetailsSnapshot.accept_pending_pcs).label('total_accept_pcs'),
            func.sum(PendingOrderDetailsSnapshot.accept_pending_wt).label('total_accept_wt'),
            func.sum(PendingOrderDetailsSnapshot.process_pending_pcs).label('total_process_pcs'),
            func.sum(PendingOrderDetailsSnapshot.process_pending_wt).label('total_process_wt'),
            func.sum(PendingOrderDetailsSnapshot.barcode_pending_pcs).label('total_barcode_pcs'),
            func.sum(PendingOrderDetailsSnapshot.barcode_pending_wt).label('total_barcode_wt'),
            func.sum(PendingOrderDetailsSnapshot.hallmark_pending_pcs).label('total_hallmark_pcs'),
            func.sum(PendingOrderDetailsSnapshot.hallmark_pending_wt).label('total_hallmark_wt'),
            func.sum(PendingOrderDetailsSnapshot.qc_issue_pending_pcs).label('total_qc_issue_pcs'),
            func.sum(PendingOrderDetailsSnapshot.qc_issue_pending_wt).label('total_qc_issue_wt'),
            func.sum(PendingOrderDetailsSnapshot.qc_complete_pending_pcs).label('total_qc_complete_pcs'),
            func.sum(PendingOrderDetailsSnapshot.qc_complete_pending_wt).label('total_qc_complete_wt'),
            func.sum(PendingOrderDetailsSnapshot.invoice_pending_pcs).label('total_invoice_pcs'),
            func.sum(PendingOrderDetailsSnapshot.invoice_pending_wt).label('total_invoice_wt'),
            func.sum(PendingOrderDetailsSnapshot.total_pcs).label('total_total_pcs'),
            func.sum(PendingOrderDetailsSnapshot.total_weight).label('total_total_wt')
        ]
        
        agg_q = db.session.query(*agg_cols)
        agg_q = apply_filters(agg_q)
        aggs = agg_q.first()

        total_wt = float(aggs.total_total_wt or 0)
        def get_perc(val):
            if total_wt <= 0: return 0
            return min(100, round((float(val or 0) / total_wt) * 100, 1))

        stats = {
            'total_pcs': f"{int(aggs.total_total_pcs or 0):,}",
            'total_wt': f"{float(aggs.total_total_wt or 0):,.3f}",
            'accept_pcs': f"{int(aggs.total_accept_pcs or 0):,}",
            'accept_wt': f"{float(aggs.total_accept_wt or 0):,.3f}",
            'accept_perc': get_perc(aggs.total_accept_wt),
            'process_pcs': f"{int(aggs.total_process_pcs or 0):,}",
            'process_wt': f"{float(aggs.total_process_wt or 0):,.3f}",
            'process_perc': get_perc(aggs.total_process_wt),
            'barcode_pcs': f"{int(aggs.total_barcode_pcs or 0):,}",
            'barcode_wt': f"{float(aggs.total_barcode_wt or 0):,.3f}",
            'barcode_perc': get_perc(aggs.total_barcode_wt),
            'hallmark_pcs': f"{int(aggs.total_hallmark_pcs or 0):,}",
            'hallmark_wt': f"{float(aggs.total_hallmark_wt or 0):,.3f}",
            'hallmark_perc': get_perc(aggs.total_hallmark_wt),
            'qc_issue_pcs': f"{int(aggs.total_qc_issue_pcs or 0):,}",
            'qc_issue_wt': f"{float(aggs.total_qc_issue_wt or 0):,.3f}",
            'qc_issue_perc': get_perc(aggs.total_qc_issue_wt),
            'qc_complete_pcs': f"{int(aggs.total_qc_complete_pcs or 0):,}",
            'qc_complete_wt': f"{float(aggs.total_qc_complete_wt or 0):,.3f}",
            'qc_complete_perc': get_perc(aggs.total_qc_complete_wt),
            'invoice_pcs': f"{int(aggs.total_invoice_pcs or 0):,}",
            'invoice_wt': f"{float(aggs.total_invoice_wt or 0):,.3f}",
            'invoice_perc': get_perc(aggs.total_invoice_wt)
        }

        # Drill-down level
        if not classification_owner:
            group_cols = [PendingOrderDetailsSnapshot.classification_owner]
            level = 'classification_owner'
        elif classification_owner and not make_owner:
            group_cols = [PendingOrderDetailsSnapshot.classification_owner, PendingOrderDetailsSnapshot.make_owner]
            level = 'make_owner'
        else:
            group_cols = [PendingOrderDetailsSnapshot.classification_owner, PendingOrderDetailsSnapshot.make_owner, PendingOrderDetailsSnapshot.collection_owner]
            level = 'collection_owner'

        # Row Aggregates
        row_agg_cols = [
            func.sum(PendingOrderDetailsSnapshot.accept_pending_pcs).label('accept_pcs'),
            func.sum(PendingOrderDetailsSnapshot.accept_pending_wt).label('accept_wt'),
            func.sum(PendingOrderDetailsSnapshot.process_pending_pcs).label('process_pcs'),
            func.sum(PendingOrderDetailsSnapshot.process_pending_wt).label('process_wt'),
            func.sum(PendingOrderDetailsSnapshot.barcode_pending_pcs).label('barcode_pcs'),
            func.sum(PendingOrderDetailsSnapshot.barcode_pending_wt).label('barcode_wt'),
            func.sum(PendingOrderDetailsSnapshot.hallmark_pending_pcs).label('hallmark_pcs'),
            func.sum(PendingOrderDetailsSnapshot.hallmark_pending_wt).label('hallmark_wt'),
            func.sum(PendingOrderDetailsSnapshot.qc_issue_pending_pcs).label('qc_issue_pcs'),
            func.sum(PendingOrderDetailsSnapshot.qc_issue_pending_wt).label('qc_issue_wt'),
            func.sum(PendingOrderDetailsSnapshot.qc_complete_pending_pcs).label('qc_complete_pcs'),
            func.sum(PendingOrderDetailsSnapshot.qc_complete_pending_wt).label('qc_complete_wt'),
            func.sum(PendingOrderDetailsSnapshot.invoice_pending_pcs).label('invoice_pcs'),
            func.sum(PendingOrderDetailsSnapshot.invoice_pending_wt).label('invoice_wt'),
            func.sum(PendingOrderDetailsSnapshot.total_pcs).label('tot_pcs'),
            func.sum(PendingOrderDetailsSnapshot.total_weight).label('tot_wt')
        ]

        main_q = db.session.query(*(group_cols + row_agg_cols))
        main_q = apply_filters(main_q)
        main_q = main_q.group_by(*group_cols).order_by(*group_cols)
        
        pagination = main_q.paginate(page=page, per_page=per_page, error_out=False)
        
        processed_rows = []
        for r in pagination.items:
            row_dict = {
                'classification_owner': r[0] or 'Unknown',
                'make_owner': r[1] if level in ['make_owner', 'collection_owner'] else '',
                'collection_owner': r[2] if level == 'collection_owner' else '',
                'accept_pcs': int(r.accept_pcs or 0), 'accept_wt': float(r.accept_wt or 0),
                'process_pcs': int(r.process_pcs or 0), 'process_wt': float(r.process_wt or 0),
                'barcode_pcs': int(r.barcode_pcs or 0), 'barcode_wt': float(r.barcode_wt or 0),
                'hallmark_pcs': int(r.hallmark_pcs or 0), 'hallmark_wt': float(r.hallmark_wt or 0),
                'qc_issue_pcs': int(r.qc_issue_pcs or 0), 'qc_issue_wt': float(r.qc_issue_wt or 0),
                'qc_complete_pcs': int(r.qc_complete_pcs or 0), 'qc_complete_wt': float(r.qc_complete_wt or 0),
                'invoice_pcs': int(r.invoice_pcs or 0), 'invoice_wt': float(r.invoice_wt or 0),
                'total_pcs': int(r.tot_pcs or 0), 'total_weight': float(r.tot_wt or 0),
                'level': level
            }
            processed_rows.append(row_dict)

        return render_template('pending_order_details.html', 
                             unread_count=unread_count, 
                             sync_time=sync_time, 
                             stats=stats, 
                             rows=processed_rows, 
                             pagination=pagination, 
                             current_level=level,
                             filter_options=filter_options)
    except Exception as e:
        logger.error(f"Error in pending_order_details: {str(e)}")
        return f"Error: {str(e)}", 500

@dashboard_bp.route('/partial/pendingorderdetails')
def get_pending_order_details_partial():
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
        order_type = request.args.get('order_type', '')
        order_ro = request.args.get('order_ro', '')
        order_request_type = request.args.get('order_request_type', '')
        provision_type = request.args.get('provision_type', '')
        branch_provision_type = request.args.get('branch_provision_type', '')
        branch_type = request.args.get('branch_type', '')
        
        parent_level = request.args.get('parent_level')
        parent_value = request.args.get('parent_value')
        grandparent_value = request.args.get('grandparent_value')

        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)
        
        is_child_rows = bool(parent_level)

        def apply_filters(query):
            if search:
                query = query.filter(
                    (PendingOrderDetailsSnapshot.classification_owner.ilike(f"%{search}%")) |
                    (PendingOrderDetailsSnapshot.collection_owner.ilike(f"%{search}%")) |
                    (PendingOrderDetailsSnapshot.make_owner.ilike(f"%{search}%")) |
                    (PendingOrderDetailsSnapshot.collection.ilike(f"%{search}%")) |
                    (PendingOrderDetailsSnapshot.supplier.ilike(f"%{search}%"))
                )
            if division:
                query = query.filter(PendingOrderDetailsSnapshot.division == division)
            if group_name:
                query = query.filter(PendingOrderDetailsSnapshot.group_name == group_name)
            if purity:
                query = query.filter(PendingOrderDetailsSnapshot.purity == purity)
            if supplier:
                query = query.filter(PendingOrderDetailsSnapshot.supplier == supplier)
            
            if parent_level == 'classification_owner':
                query = query.filter(PendingOrderDetailsSnapshot.classification_owner == parent_value)
            elif parent_level == 'make_owner':
                query = query.filter(
                    PendingOrderDetailsSnapshot.classification_owner == grandparent_value,
                    PendingOrderDetailsSnapshot.make_owner == parent_value
                )
            else:
                if classification_owner:
                    query = query.filter(PendingOrderDetailsSnapshot.classification_owner == classification_owner)
                if make_owner:
                    query = query.filter(PendingOrderDetailsSnapshot.make_owner == make_owner)
                if collection_owner:
                    query = query.filter(PendingOrderDetailsSnapshot.collection_owner == collection_owner)

            if classification:
                query = query.filter(PendingOrderDetailsSnapshot.classification == classification)
            query = apply_make_filter(query, make)
            if order_type:
                query = query.filter(PendingOrderDetailsSnapshot.order_type == order_type)
            if order_ro:
                query = query.filter(PendingOrderDetailsSnapshot.order_ro == order_ro)
            if order_request_type:
                query = query.filter(PendingOrderDetailsSnapshot.order_request_type == order_request_type)
            if provision_type:
                query = query.filter(PendingOrderDetailsSnapshot.provision_type == provision_type)
            if branch_provision_type:
                query = query.filter(PendingOrderDetailsSnapshot.branch_provision_type == branch_provision_type)
            if branch_type:
                query = query.filter(PendingOrderDetailsSnapshot.branch_type == branch_type)
            
            roles = [r.upper() for r in session.get('roles', [])]
            is_admin = 'ADMIN' in roles
            is_manager_2 = 'MANAGER_2' in roles
            
            if not is_admin and not is_manager_2:
                if 'MANAGER_KMU' in roles:
                    query = query.filter(PendingOrderDetailsSnapshot.make.in_([
                        'KMU - KERALA', 'KMU 999 COIN', 'KMU B2B', 'KMU KARNATAKA', 
                        'KMU MH', 'KMU-COIN', 'KMU-TN'
                    ]))
                else:
                    query = apply_owner_visibility_filter(query)

            return query

        if is_child_rows:
            if parent_level == 'classification_owner':
                group_cols = [PendingOrderDetailsSnapshot.classification_owner, PendingOrderDetailsSnapshot.make_owner]
                level = 'make_owner'
            else:
                group_cols = [PendingOrderDetailsSnapshot.classification_owner, PendingOrderDetailsSnapshot.make_owner, PendingOrderDetailsSnapshot.collection_owner]
                level = 'collection_owner'
        else:
            if not classification_owner:
                group_cols = [PendingOrderDetailsSnapshot.classification_owner]
                level = 'classification_owner'
            elif classification_owner and not make_owner:
                group_cols = [PendingOrderDetailsSnapshot.classification_owner, PendingOrderDetailsSnapshot.make_owner]
                level = 'make_owner'
            else:
                group_cols = [PendingOrderDetailsSnapshot.classification_owner, PendingOrderDetailsSnapshot.make_owner, PendingOrderDetailsSnapshot.collection_owner]
                level = 'collection_owner'

        row_agg_cols = [
            func.sum(PendingOrderDetailsSnapshot.accept_pending_pcs).label('accept_pcs'),
            func.sum(PendingOrderDetailsSnapshot.accept_pending_wt).label('accept_wt'),
            func.sum(PendingOrderDetailsSnapshot.process_pending_pcs).label('process_pcs'),
            func.sum(PendingOrderDetailsSnapshot.process_pending_wt).label('process_wt'),
            func.sum(PendingOrderDetailsSnapshot.barcode_pending_pcs).label('barcode_pcs'),
            func.sum(PendingOrderDetailsSnapshot.barcode_pending_wt).label('barcode_wt'),
            func.sum(PendingOrderDetailsSnapshot.hallmark_pending_pcs).label('hallmark_pcs'),
            func.sum(PendingOrderDetailsSnapshot.hallmark_pending_wt).label('hallmark_wt'),
            func.sum(PendingOrderDetailsSnapshot.qc_issue_pending_pcs).label('qc_issue_pcs'),
            func.sum(PendingOrderDetailsSnapshot.qc_issue_pending_wt).label('qc_issue_wt'),
            func.sum(PendingOrderDetailsSnapshot.qc_complete_pending_pcs).label('qc_complete_pcs'),
            func.sum(PendingOrderDetailsSnapshot.qc_complete_pending_wt).label('qc_complete_wt'),
            func.sum(PendingOrderDetailsSnapshot.invoice_pending_pcs).label('invoice_pcs'),
            func.sum(PendingOrderDetailsSnapshot.invoice_pending_wt).label('invoice_wt'),
            func.sum(PendingOrderDetailsSnapshot.total_pcs).label('tot_pcs'),
            func.sum(PendingOrderDetailsSnapshot.total_weight).label('tot_wt')
        ]

        main_q = db.session.query(*(group_cols + row_agg_cols))
        main_q = apply_filters(main_q)
        main_q = main_q.group_by(*group_cols).order_by(*group_cols)

        if is_child_rows:
            items = main_q.all()
            processed_rows = []
            for r in items:
                row_dict = {
                    'classification_owner': r[0] or 'Unknown',
                    'make_owner': r[1] if level in ['make_owner', 'collection_owner'] else '',
                    'collection_owner': r[2] if level == 'collection_owner' else '',
                    'accept_pcs': int(r.accept_pcs or 0), 'accept_wt': float(r.accept_wt or 0),
                    'process_pcs': int(r.process_pcs or 0), 'process_wt': float(r.process_wt or 0),
                    'barcode_pcs': int(r.barcode_pcs or 0), 'barcode_wt': float(r.barcode_wt or 0),
                    'hallmark_pcs': int(r.hallmark_pcs or 0), 'hallmark_wt': float(r.hallmark_wt or 0),
                    'qc_issue_pcs': int(r.qc_issue_pcs or 0), 'qc_issue_wt': float(r.qc_issue_wt or 0),
                    'qc_complete_pcs': int(r.qc_complete_pcs or 0), 'qc_complete_wt': float(r.qc_complete_wt or 0),
                    'invoice_pcs': int(r.invoice_pcs or 0), 'invoice_wt': float(r.invoice_wt or 0),
                    'total_pcs': int(r.tot_pcs or 0), 'total_weight': float(r.tot_wt or 0),
                    'level': level
                }
                processed_rows.append(row_dict)
            return render_template('partials/_view_pending_order_details.html', rows=processed_rows, is_child=True, parent_level=parent_level)

        pagination = main_q.paginate(page=page, per_page=per_page, error_out=False)
        processed_rows = []
        for r in pagination.items:
            row_dict = {
                'classification_owner': r[0] or 'Unknown',
                'make_owner': r[1] if level in ['make_owner', 'collection_owner'] else '',
                'collection_owner': r[2] if level == 'collection_owner' else '',
                'accept_pcs': int(r.accept_pcs or 0), 'accept_wt': float(r.accept_wt or 0),
                'process_pcs': int(r.process_pcs or 0), 'process_wt': float(r.process_wt or 0),
                'barcode_pcs': int(r.barcode_pcs or 0), 'barcode_wt': float(r.barcode_wt or 0),
                'hallmark_pcs': int(r.hallmark_pcs or 0), 'hallmark_wt': float(r.hallmark_wt or 0),
                'qc_issue_pcs': int(r.qc_issue_pcs or 0), 'qc_issue_wt': float(r.qc_issue_wt or 0),
                'qc_complete_pcs': int(r.qc_complete_pcs or 0), 'qc_complete_wt': float(r.qc_complete_wt or 0),
                'invoice_pcs': int(r.invoice_pcs or 0), 'invoice_wt': float(r.invoice_wt or 0),
                'total_pcs': int(r.tot_pcs or 0), 'total_weight': float(r.tot_wt or 0),
                'level': level
            }
            processed_rows.append(row_dict)

        return render_template('partials/_view_pending_order_details.html', rows=processed_rows, pagination=pagination, is_child=False)
    except Exception as e:
        logger.error(f"Error in get_pending_order_details_partial: {str(e)}")
        return f"Error: {str(e)}", 500

@dashboard_bp.route('/partial/pendingorderdetails/leaf_detail')
def get_pending_order_details_leaf_detail():
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
        order_type = request.args.get('order_type', '')
        order_ro = request.args.get('order_ro', '')
        order_request_type = request.args.get('order_request_type', '')
        provision_type = request.args.get('provision_type', '')
        branch_provision_type = request.args.get('branch_provision_type', '')
        branch_type = request.args.get('branch_type', '')

        # Leaf filters
        parent_classification_owner = request.args.get('parent_classification_owner', '')
        parent_make_owner = request.args.get('parent_make_owner', '')
        parent_collection_owner = request.args.get('parent_collection_owner', '')

        query = PendingOrderDetailsSnapshot.query.filter(
            PendingOrderDetailsSnapshot.classification_owner == parent_classification_owner,
            PendingOrderDetailsSnapshot.make_owner == parent_make_owner,
            PendingOrderDetailsSnapshot.collection_owner == parent_collection_owner
        )

        if search:
            query = query.filter(
                (PendingOrderDetailsSnapshot.classification.ilike(f"%{search}%")) |
                (PendingOrderDetailsSnapshot.make.ilike(f"%{search}%")) |
                (PendingOrderDetailsSnapshot.collection.ilike(f"%{search}%")) |
                (PendingOrderDetailsSnapshot.supplier.ilike(f"%{search}%"))
            )
        if division:
            query = query.filter(PendingOrderDetailsSnapshot.division == division)
        if group_name:
            query = query.filter(PendingOrderDetailsSnapshot.group_name == group_name)
        if purity:
            query = query.filter(PendingOrderDetailsSnapshot.purity == purity)
        if supplier:
            query = query.filter(PendingOrderDetailsSnapshot.supplier == supplier)
        if classification:
            query = query.filter(PendingOrderDetailsSnapshot.classification == classification)
        query = apply_make_filter(query, make)
        if order_type:
            query = query.filter(PendingOrderDetailsSnapshot.order_type == order_type)
        if order_ro:
            query = query.filter(PendingOrderDetailsSnapshot.order_ro == order_ro)
        if order_request_type:
            query = query.filter(PendingOrderDetailsSnapshot.order_request_type == order_request_type)
        if provision_type:
            query = query.filter(PendingOrderDetailsSnapshot.provision_type == provision_type)
        if branch_provision_type:
            query = query.filter(PendingOrderDetailsSnapshot.branch_provision_type == branch_provision_type)
        if branch_type:
            query = query.filter(PendingOrderDetailsSnapshot.branch_type == branch_type)

        roles = [r.upper() for r in session.get('roles', [])]
        is_admin = 'ADMIN' in roles
        is_manager_2 = 'MANAGER_2' in roles
        
        if not is_admin and not is_manager_2:
            if 'MANAGER_KMU' in roles:
                query = query.filter(PendingOrderDetailsSnapshot.make.in_([
                    'KMU - KERALA', 'KMU 999 COIN', 'KMU B2B', 'KMU KARNATAKA', 
                    'KMU MH', 'KMU-COIN', 'KMU-TN'
                ]))
            else:
                query = apply_owner_visibility_filter(query)

        records = query.all()
        return render_template('partials/_view_pending_order_details_leaf.html', records=records)
    except Exception as e:
        logger.error(f"Error in get_pending_order_details_leaf_detail: {str(e)}")
        return f"Error: {str(e)}", 500
