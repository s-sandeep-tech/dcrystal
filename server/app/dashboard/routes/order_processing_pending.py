from flask import render_template, request, jsonify, session
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.dashboard import dashboard_bp
from app.models.snapshots import (
    OrderProcessingPendingSnapshot, OrderProcessingPendingFeedback,
    SupplierHMIssueSnapshot, SupplierHMIssueFeedback,
    HMCompletedReturnSnapshot, HMCompletedReturnFeedback,
    HMReturnQCIssueSnapshot, HMReturnQCIssueFeedback,
    SupplierQCIssueReceiptPendingSnapshot, SupplierQCIssueReceiptPendingFeedback,
    QCCompletedInvoicePendingSnapshot, QCCompletedInvoicePendingFeedback,
    InvoiceCompletedPendingDeliverSnapshot, InvoiceCompletedPendingDeliverFeedback
)
from app.models.auth import User
from app.extensions import db, redis_client
from sqlalchemy import func, case, text
from datetime import datetime
from zoneinfo import ZoneInfo
import logging
import json
from app.utils.decorators import require_perm

logger = logging.getLogger(__name__)

def get_latest_feedback_subquery():
    # Group columns that define the unique entity for feedback
    group_cols = [
        OrderProcessingPendingFeedback.collection_owner,
        OrderProcessingPendingFeedback.collection,
        OrderProcessingPendingFeedback.branch,
        OrderProcessingPendingFeedback.supplier
    ]
    # Find latest feedback date for each entity
    subq = db.session.query(
        *group_cols,
        func.max(OrderProcessingPendingFeedback.created_at).label('max_date')
    ).group_by(
        *group_cols
    ).subquery()
    
    # Join back to get the actual feedback record
    return db.session.query(OrderProcessingPendingFeedback).join(
        subq,
        db.and_(
            func.coalesce(OrderProcessingPendingFeedback.collection_owner, '') == func.coalesce(subq.c.collection_owner, ''),
            func.coalesce(OrderProcessingPendingFeedback.collection, '') == func.coalesce(subq.c.collection, ''),
            func.coalesce(OrderProcessingPendingFeedback.branch, '') == func.coalesce(subq.c.branch, ''),
            func.coalesce(OrderProcessingPendingFeedback.supplier, '') == func.coalesce(subq.c.supplier, ''),
            OrderProcessingPendingFeedback.created_at == subq.c.max_date
        )
    ).subquery()

def get_model_for_status(status):
    """Returns (Model, grouping_cols, feedback_model) for a given status."""
    if status == 'hm_issue':
        Model = SupplierHMIssueSnapshot
        grouping_cols = [Model.hm_ro, Model.make_owner, Model.collection_owner, Model.collection, Model.hallmark_agent, Model.supplier]
        FeedbackModel = SupplierHMIssueFeedback
    elif status == 'hm_return':
        Model = HMCompletedReturnSnapshot
        grouping_cols = [Model.hm_ro, Model.make_owner, Model.collection_owner, Model.collection, Model.hallmark_agent, Model.supplier]
        FeedbackModel = HMCompletedReturnFeedback
    elif status == 'hm_qc_issue':
        Model = HMReturnQCIssueSnapshot
        grouping_cols = [Model.hm_ro, Model.make_owner, Model.collection_owner, Model.collection, Model.party, Model.hallmark_agent]
        FeedbackModel = HMReturnQCIssueFeedback
    elif status == 'qc_issue_receipt':
        Model = SupplierQCIssueReceiptPendingSnapshot
        grouping_cols = [Model.qc_ro, Model.make_owner, Model.collection_owner, Model.collection, Model.party, Model.order_branch, Model.business_head_name]
        FeedbackModel = SupplierQCIssueReceiptPendingFeedback
    elif status == 'qc_completed_invoice':
        Model = QCCompletedInvoicePendingSnapshot
        grouping_cols = [Model.qc_ro, Model.make_owner, Model.collection_owner, Model.collection, Model.party]
        FeedbackModel = QCCompletedInvoicePendingFeedback
    elif status == 'invoice_completed_deliver':
        Model = InvoiceCompletedPendingDeliverSnapshot
        grouping_cols = [Model.order_branch, Model.make_owner, Model.collection_owner, Model.collection, Model.party]
        FeedbackModel = InvoiceCompletedPendingDeliverFeedback
    else: # Default: pending_acceptance
        Model = OrderProcessingPendingSnapshot
        grouping_cols = [Model.collection_owner, Model.collection, Model.supplier]
        FeedbackModel = OrderProcessingPendingFeedback
    
    return Model, grouping_cols, FeedbackModel

@dashboard_bp.route('/api/order-processing-pending-filters')
@jwt_required()
def api_order_processing_filters():
    from datetime import timedelta
    status = request.args.get('status', 'pending')
    Model, _, _ = get_model_for_status(status)
    
    try:
        latest_date = db.session.query(func.max(Model.snapshot_date)).scalar()
    except Exception as e:
        logger.error(f"Error fetching latest date for {status}: {str(e)}")
        return jsonify({'options': {}, 'valid_fields': []})
        
    if not latest_date:
        return jsonify({'options': {}, 'valid_fields': []})
        
    base_q = db.session.query(Model).filter(
        Model.snapshot_date >= latest_date - timedelta(milliseconds=10),
        Model.snapshot_date <= latest_date + timedelta(milliseconds=10)
    )
    
    def get_opts(col):
        if col not in Model.__table__.columns: return []
        attr = getattr(Model, col)
        try:
            return [r[0] for r in base_q.with_entities(attr).distinct().order_by(attr).all() if r[0]]
        except Exception as e:
            logger.error(f"Error fetching options for {col} in {status}: {str(e)}")
            return []

    # Map internal field names to UI filter IDs
    field_map = {
        'collection_owner': 'collection_owner',
        'collection': 'collection',
        'branch': 'branch',
        'order_branch': 'branch',
        'supplier': 'supplier',
        'party': 'supplier',
        'make_owner': 'make_owner',
        'order_type': 'order_type',
        'order_request_type': 'order_request_type',
        'business_head_name': 'business_head_name',
        'make': 'make'
    }
    
    options = {}
    valid_fields = ['feedback_status'] # Feedback status is always valid
    
    for model_field, ui_field in field_map.items():
        if model_field in Model.__table__.columns:
            opts = get_opts(model_field)
            if ui_field not in options: options[ui_field] = []
            # Merge options if multiple model fields map to same UI field (e.g. branch vs order_branch)
            options[ui_field] = sorted(list(set(options[ui_field] + opts)))
            if ui_field not in valid_fields: valid_fields.append(ui_field)

    # Checkboxes
    if 'is_qc_completed' in Model.__table__.columns: valid_fields.append('is_qc_completed')
    if 'is_rate_requisition_completed' in Model.__table__.columns: valid_fields.append('is_rate_requisition_completed')
    if 'is_invoiced' in Model.__table__.columns: valid_fields.append('is_invoiced')

    return jsonify({
        'options': options,
        'valid_fields': valid_fields
    })

@dashboard_bp.route('/order-processing-pending-stage-tatus')
@jwt_required()
@require_perm('report.view')
def order_processing_pending():
    try:
        from app.models.core import Notification
        unread_count = Notification.query.filter_by(is_read=False).count()
        sync_time = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%I:%M %p")

        latest_date_query = db.session.query(func.max(OrderProcessingPendingSnapshot.snapshot_date)).scalar()
        
        if not latest_date_query:
            return render_template('order_processing_pending.html', 
                                 unread_count=unread_count, 
                                 sync_time=sync_time, 
                                 rows=[], 
                                 pagination=None,
                                 current_username=session.get('username', ''),
                                 filter_options={},
                                 initial_load=True)

        def fetch_filter_options():
            base_q = db.session.query(OrderProcessingPendingSnapshot).filter(
                OrderProcessingPendingSnapshot.snapshot_date == latest_date_query
            )
            return {
                'make_owners': [r[0] for r in base_q.with_entities(OrderProcessingPendingSnapshot.make_owner).distinct().order_by(OrderProcessingPendingSnapshot.make_owner).all() if r[0]],
                'collection_owners': [r[0] for r in base_q.with_entities(OrderProcessingPendingSnapshot.collection_owner).distinct().order_by(OrderProcessingPendingSnapshot.collection_owner).all() if r[0]],
                'collections': [r[0] for r in base_q.with_entities(OrderProcessingPendingSnapshot.collection).distinct().order_by(OrderProcessingPendingSnapshot.collection).all() if r[0]],
                'branches': [r[0] for r in base_q.with_entities(OrderProcessingPendingSnapshot.branch).distinct().order_by(OrderProcessingPendingSnapshot.branch).all() if r[0]],
                'suppliers': [r[0] for r in base_q.with_entities(OrderProcessingPendingSnapshot.supplier).distinct().order_by(OrderProcessingPendingSnapshot.supplier).all() if r[0]],
                'order_types': [r[0] for r in base_q.with_entities(OrderProcessingPendingSnapshot.order_type).distinct().order_by(OrderProcessingPendingSnapshot.order_type).all() if r[0]],
                'order_request_types': [r[0] for r in base_q.with_entities(OrderProcessingPendingSnapshot.order_request_type).distinct().order_by(OrderProcessingPendingSnapshot.order_request_type).all() if r[0]],
                'business_heads': [r[0] for r in base_q.with_entities(SupplierQCIssueReceiptPendingSnapshot.business_head_name).distinct().order_by(SupplierQCIssueReceiptPendingSnapshot.business_head_name).all() if r[0]],
                'makes': [r[0] for r in base_q.with_entities(QCCompletedInvoicePendingSnapshot.make).distinct().order_by(QCCompletedInvoicePendingSnapshot.make).all() if r[0]],
            }

        filter_options = fetch_filter_options()

        return render_template('order_processing_pending.html', 
                             unread_count=unread_count, 
                             sync_time=sync_time, 
                             current_username=session.get('username', ''),
                             filter_options=filter_options,
                             initial_load=True)
    except Exception as e:
        logger.error(f"Error in order_processing_pending: {str(e)}")
        return f"Error: {str(e)}", 500

@dashboard_bp.route('/partial/order-processing-pending-status')
@jwt_required()
@require_perm('report.view')
def partial_order_processing_pending():
    search = request.args.get('search', '').strip()
    status = request.args.get('status', 'pending') # Default to pending
    
    # Filters
    f_make_owner = request.args.get('make_owner', '')
    f_collection_owner = request.args.get('collection_owner', '')
    f_collection = request.args.get('collection', '')
    f_branch = request.args.get('branch', '')
    f_supplier = request.args.get('supplier', '')
    f_order_type = request.args.get('order_type', '')
    f_order_request_type = request.args.get('order_request_type', '')
    f_feedback_status = request.args.get('feedback_status', '')
    f_business_head = request.args.get('business_head_name', '')
    f_make = request.args.get('make', '')
    f_is_qc_completed = request.args.get('is_qc_completed', '')
    f_is_rate_req_completed = request.args.get('is_rate_requisition_completed', '')
    f_is_invoiced = request.args.get('is_invoiced', '')

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)

    Model, grouping_cols, FeedbackModel = get_model_for_status(status)
    
    latest_date = db.session.query(func.max(Model.snapshot_date)).scalar()
    if not latest_date:
        return render_template('partials/_view_order_processing_pending.html', rows=[], pagination=None, stats={'total_pieces': 0, 'total_weight': 0})

    if status == 'hm_issue':
        latest_feedback = get_hm_latest_feedback_subquery()
    elif status == 'hm_qc_issue':
        latest_feedback = get_hm_qc_issue_latest_feedback_subquery()
    elif status == 'qc_issue_receipt':
        latest_feedback = get_qc_issue_receipt_latest_feedback_subquery()
    elif status == 'qc_completed_invoice':
        latest_feedback = get_qc_completed_invoice_latest_feedback_subquery()
    elif status == 'invoice_completed_deliver':
        latest_feedback = get_invoice_completed_deliver_latest_feedback_subquery()
    else:
        latest_feedback = get_latest_feedback_subquery()
    
    # Subquery for aggregation to handle distinct counts/sums before joining feedback
    from datetime import timedelta
    weight_col = Model.weight if hasattr(Model, 'weight') else Model.barcoded_weight
    
    agg_cols = [
        *[col.label(col.name) for col in grouping_cols],
        func.sum(weight_col).label('sum_weight'),
        func.sum(Model.pieces).label('sum_pieces')
    ]
    if status == 'hm_issue':
        agg_cols.extend([
            func.sum(Model.gross_weight).label('sum_gross_weight'),
            func.sum(Model.net_weight).label('sum_net_weight'),
            func.sum(Model.stone_weight).label('sum_stone_weight'),
            func.count(func.distinct(Model.po_number)).label('po_count')
        ])

    if status == 'hm_return' or status == 'hm_qc_issue':
        agg_cols.extend([
            func.max(Model.hm_agent_invoice_receipt_date).label('hm_agent_invoice_receipt_date'),
            func.max(Model.hm_agent_invoice_receipt_no).label('hm_agent_invoice_receipt_no')
        ])
        if status == 'hm_return':
            agg_cols.append(func.max(Model.hm_completed_date).label('hm_completed_date'))
            agg_cols.append(func.count(func.distinct(Model.po_number)).label('po_count'))
            agg_cols.extend([
                func.sum(Model.net_weight).label('sum_net_weight'),
                func.sum(Model.gross_weight).label('sum_gross_weight')
            ])
    
    if status == 'qc_issue_receipt':
        agg_cols.extend([
            func.max(Model.qc_issue_receipt_date).label('qc_issue_receipt_date'),
            func.max(Model.qc_issue_receipt_no).label('qc_issue_receipt_no')
        ])
    
    if status == 'qc_completed_invoice':
        agg_cols.extend([
            func.max(Model.qc_issue_receipt_date).label('qc_issue_receipt_date'),
            func.max(Model.qc_issue_receipt_no).label('qc_issue_receipt_no'),
            func.max(Model.qc_completed_date).label('qc_completed_date'),
            func.sum(Model.gross_weight).label('sum_gross_weight'),
            func.sum(Model.net_weight).label('sum_net_weight'),
            func.sum(Model.stone_weight).label('sum_stone_weight'),
            func.sum(Model.barcoded_weight).label('sum_barcoded_weight')
        ])
    
    if status == 'invoice_completed_deliver':
        agg_cols.extend([
            func.max(Model.invoice_no).label('invoice_no'),
            func.max(Model.invoice_date).label('invoice_date'),
            func.max(Model.invoice_amount).label('invoice_amount'),
            func.sum(Model.gross_weight).label('sum_gross_weight'),
            func.sum(Model.net_weight).label('sum_net_weight'),
            func.sum(Model.stone_weight).label('sum_stone_weight')
        ])

    q = db.session.query(*agg_cols).filter(
        Model.snapshot_date >= latest_date - timedelta(milliseconds=10),
        Model.snapshot_date <= latest_date + timedelta(milliseconds=10)
    )

    # Apply filters
    if search:
        search_filters = []
        if hasattr(Model, 'collection_owner'): search_filters.append(Model.collection_owner.ilike(f'%{search}%'))
        if hasattr(Model, 'collection'): search_filters.append(Model.collection.ilike(f'%{search}%'))
        if hasattr(Model, 'po_number'): search_filters.append(Model.po_number.ilike(f'%{search}%'))
        
        if hasattr(Model, 'supplier'): search_filters.append(Model.supplier.ilike(f'%{search}%'))
        elif hasattr(Model, 'party'): search_filters.append(Model.party.ilike(f'%{search}%'))
        
        if hasattr(Model, 'branch'): search_filters.append(Model.branch.ilike(f'%{search}%'))
        elif hasattr(Model, 'order_branch'): search_filters.append(Model.order_branch.ilike(f'%{search}%'))
        
        if hasattr(Model, 'hm_ro'): search_filters.append(Model.hm_ro.ilike(f'%{search}%'))
        if hasattr(Model, 'hallmark_agent'): search_filters.append(Model.hallmark_agent.ilike(f'%{search}%'))
        
        if search_filters:
            q = q.filter(db.or_(*search_filters))
    
    if f_make_owner and hasattr(Model, 'make_owner'): 
        q = q.filter(Model.make_owner == f_make_owner)
    if f_collection_owner and hasattr(Model, 'collection_owner'): 
        q = q.filter(Model.collection_owner == f_collection_owner)
    if f_collection and hasattr(Model, 'collection'): 
        q = q.filter(Model.collection == f_collection)
    
    if f_branch:
        if hasattr(Model, 'branch'): q = q.filter(Model.branch == f_branch)
        elif hasattr(Model, 'order_branch'): q = q.filter(Model.order_branch == f_branch)
        
    if f_supplier:
        if hasattr(Model, 'supplier'): q = q.filter(Model.supplier == f_supplier)
        elif hasattr(Model, 'party'): q = q.filter(Model.party == f_supplier)
        
    if f_order_type and hasattr(Model, 'order_type'): 
        q = q.filter(Model.order_type == f_order_type)
    if f_order_request_type and hasattr(Model, 'order_request_type'): 
        q = q.filter(Model.order_request_type == f_order_request_type)
    
    if f_business_head:
        if hasattr(Model, 'business_head_name'):
            q = q.filter(Model.business_head_name == f_business_head)
        elif hasattr(Model, 'bh_name'):
            q = q.filter(Model.bh_name == f_business_head)
    
    if f_make and hasattr(Model, 'make'):
        q = q.filter(Model.make == f_make)

    if f_is_qc_completed == 'true' and hasattr(Model, 'is_qc_completed'): 
        q = q.filter(Model.is_qc_completed == True)
    elif f_is_qc_completed == 'false' and hasattr(Model, 'is_qc_completed'): 
        q = q.filter(Model.is_qc_completed == False)
    
    if f_is_rate_req_completed == 'true' and hasattr(Model, 'is_rate_requisition_completed'): 
        q = q.filter(Model.is_rate_requisition_completed == True)
    elif f_is_rate_req_completed == 'false' and hasattr(Model, 'is_rate_requisition_completed'): 
        q = q.filter(Model.is_rate_requisition_completed == False)
    
    if f_is_invoiced == 'true' and hasattr(Model, 'is_invoiced'): 
        q = q.filter(Model.is_invoiced == True)
    elif f_is_invoiced == 'false' and hasattr(Model, 'is_invoiced'): 
        q = q.filter(Model.is_invoiced == False)

    q = q.group_by(*grouping_cols).subquery('agg')

    if status == 'hm_issue':
        latest_feedback = get_hm_latest_feedback_subquery()
        # Join with HM feedback
        final_q = db.session.query(
            *[q.c[col.name] for col in grouping_cols],
            q.c.sum_weight,
            q.c.sum_pieces,
            q.c.sum_gross_weight,
            q.c.sum_net_weight,
            q.c.sum_stone_weight,
            q.c.po_count,
            latest_feedback.c.feedback_text,
            latest_feedback.c.feedback_category,
            latest_feedback.c.username.label('feedback_username'),
            latest_feedback.c.created_at.label('feedback_date')
        ).outerjoin(
            latest_feedback,
            db.and_(
                *[func.coalesce(q.c[col.name], '') == func.coalesce(latest_feedback.c[col.name], '') for col in grouping_cols]
            )
        )
    elif status == 'hm_return':
        latest_feedback = get_hm_return_latest_feedback_subquery()
        # Join with HM Return feedback
        final_q = db.session.query(
            *[q.c[col.name] for col in grouping_cols],
            q.c.sum_weight,
            q.c.sum_pieces,
            q.c.hm_agent_invoice_receipt_date,
            q.c.hm_agent_invoice_receipt_no,
            q.c.hm_completed_date,
            q.c.po_count,
            q.c.sum_net_weight,
            q.c.sum_gross_weight,
            latest_feedback.c.feedback_text,
            latest_feedback.c.feedback_category,
            latest_feedback.c.username.label('feedback_username'),
            latest_feedback.c.created_at.label('feedback_date')
        ).outerjoin(
            latest_feedback,
            db.and_(
                *[func.coalesce(q.c[col.name], '') == func.coalesce(latest_feedback.c[col.name], '') for col in grouping_cols]
            )
        )
    elif status == 'hm_qc_issue':
        latest_feedback = get_hm_qc_issue_latest_feedback_subquery()
        final_q = db.session.query(
            *[q.c[col.name] for col in grouping_cols],
            q.c.sum_weight,
            q.c.sum_pieces,
            q.c.hm_agent_invoice_receipt_date,
            q.c.hm_agent_invoice_receipt_no,
            latest_feedback.c.feedback_text,
            latest_feedback.c.feedback_category,
            latest_feedback.c.username.label('feedback_username'),
            latest_feedback.c.created_at.label('feedback_date')
        ).outerjoin(
            latest_feedback,
            db.and_(
                *[func.coalesce(q.c[col.name], '') == func.coalesce(latest_feedback.c[col.name], '') for col in grouping_cols]
            )
        )
    elif status == 'qc_issue_receipt':
        latest_feedback = get_qc_issue_receipt_latest_feedback_subquery()
        final_q = db.session.query(
            *[q.c[col.name] for col in grouping_cols],
            q.c.sum_weight,
            q.c.sum_pieces,
            q.c.qc_issue_receipt_date,
            q.c.qc_issue_receipt_no,
            latest_feedback.c.feedback_text,
            latest_feedback.c.feedback_category,
            latest_feedback.c.username.label('feedback_username'),
            latest_feedback.c.created_at.label('feedback_date')
        ).outerjoin(
            latest_feedback,
            db.and_(
                *[func.coalesce(q.c[col.name], '') == func.coalesce(latest_feedback.c[col.name], '') for col in grouping_cols]
            )
        )
    elif status == 'invoice_completed_deliver':
        latest_feedback = get_invoice_completed_deliver_latest_feedback_subquery()
        final_q = db.session.query(
            *[q.c[col.name] for col in grouping_cols],
            q.c.sum_weight,
            q.c.sum_pieces,
            q.c.invoice_no,
            q.c.invoice_date,
            q.c.invoice_amount,
            q.c.sum_gross_weight,
            q.c.sum_net_weight,
            q.c.sum_stone_weight,
            latest_feedback.c.feedback_text,
            latest_feedback.c.feedback_category,
            latest_feedback.c.username.label('feedback_username'),
            latest_feedback.c.created_at.label('feedback_date')
        ).outerjoin(
            latest_feedback,
            db.and_(
                *[func.coalesce(q.c[col.name], '') == func.coalesce(latest_feedback.c[col.name], '') for col in grouping_cols]
            )
        )
    elif status == 'qc_completed_invoice':
        latest_feedback = get_qc_completed_invoice_latest_feedback_subquery()
        final_q = db.session.query(
            *[q.c[col.name] for col in grouping_cols],
            q.c.sum_weight,
            q.c.sum_pieces,
            q.c.qc_issue_receipt_date,
            q.c.qc_issue_receipt_no,
            q.c.qc_completed_date,
            q.c.sum_gross_weight,
            q.c.sum_net_weight,
            q.c.sum_stone_weight,
            q.c.sum_barcoded_weight,
            latest_feedback.c.feedback_text,
            latest_feedback.c.feedback_category,
            latest_feedback.c.username.label('feedback_username'),
            latest_feedback.c.created_at.label('feedback_date')
        ).outerjoin(
            latest_feedback,
            db.and_(
                *[func.coalesce(q.c[col.name], '') == func.coalesce(latest_feedback.c[col.name], '') for col in grouping_cols]
            )
        )
    else:
        latest_feedback = get_latest_feedback_subquery()
        # Join with regular feedback
        final_q = db.session.query(
            *[q.c[col.name] for col in grouping_cols],
            q.c.sum_weight,
            q.c.sum_pieces,
            latest_feedback.c.feedback_text,
            latest_feedback.c.feedback_category,
            latest_feedback.c.username.label('feedback_username'),
            latest_feedback.c.created_at.label('feedback_date')
        ).outerjoin(
            latest_feedback,
            db.and_(
                *[func.coalesce(q.c[col.name], '') == func.coalesce(latest_feedback.c[col.name], '') for col in grouping_cols]
            )
        )

    if f_feedback_status == 'with':
        final_q = final_q.filter(latest_feedback.c.feedback_text != None)
    elif f_feedback_status == 'without':
        final_q = final_q.filter(latest_feedback.c.feedback_text == None)

    # Calculate stats
    total_count = final_q.count()
    s = final_q.subquery()
    stats_res = db.session.query(
        func.sum(s.c.sum_weight),
        func.sum(s.c.sum_pieces),
        func.count(case(((s.c.feedback_text != None), 1))),
        func.count(case(((s.c.feedback_text == None), 1)))
    ).first()

    stats = {
        'total_weight': float(stats_res[0] or 0),
        'total_pieces': int(stats_res[1] or 0),
        'with_feedback': int(stats_res[2] or 0),
        'without_feedback': int(stats_res[3] or 0)
    }

    # Execute main query
    items = final_q.order_by(q.c.sum_weight.desc()).offset((page-1)*per_page).limit(per_page).all()
    
    # Process for display
    processed_rows = []
    for r in items:
        row_dict = {
            'weight': float(r.sum_weight or 0),
            'pieces': int(r.sum_pieces or 0),
            'feedback_text': r.feedback_text,
            'feedback_category': r.feedback_category,
            'feedback_username': r.feedback_username,
            'feedback_date': r.feedback_date.strftime('%Y-%m-%d %H:%M') if r.feedback_date else None
        }
        for col in grouping_cols:
            row_dict[col.name] = getattr(r, col.name)
            
        if status == 'hm_issue':
            row_dict['gross_weight'] = float(getattr(r, 'sum_gross_weight', 0) or 0)
            row_dict['net_weight'] = float(getattr(r, 'sum_net_weight', 0) or 0)
            row_dict['stone_weight'] = float(getattr(r, 'sum_stone_weight', 0) or 0)
            row_dict['po_count'] = int(getattr(r, 'po_count', 0) or 0)

        if status == 'hm_return' or status == 'hm_qc_issue':
            row_dict['hm_agent_invoice_receipt_date'] = getattr(r, 'hm_agent_invoice_receipt_date', None)
            row_dict['hm_agent_invoice_receipt_no'] = getattr(r, 'hm_agent_invoice_receipt_no', None)
            if status == 'hm_return':
                row_dict['hm_completed_date'] = getattr(r, 'hm_completed_date', None)
                row_dict['po_count'] = int(getattr(r, 'po_count', 0) or 0)
                row_dict['net_weight'] = float(getattr(r, 'sum_net_weight', 0) or 0)
                row_dict['gross_weight'] = float(getattr(r, 'sum_gross_weight', 0) or 0)
        
        if status == 'qc_issue_receipt' or status == 'qc_completed_invoice':
            row_dict['qc_issue_receipt_date'] = getattr(r, 'qc_issue_receipt_date', None)
            row_dict['qc_issue_receipt_no'] = getattr(r, 'qc_issue_receipt_no', None)
            if status == 'qc_completed_invoice':
                row_dict['qc_completed_date'] = getattr(r, 'qc_completed_date', None)
                row_dict['gross_weight'] = float(getattr(r, 'sum_gross_weight', 0) or 0)
                row_dict['net_weight'] = float(getattr(r, 'sum_net_weight', 0) or 0)
                row_dict['stone_weight'] = float(getattr(r, 'sum_stone_weight', 0) or 0)
                row_dict['barcoded_weight'] = float(getattr(r, 'sum_barcoded_weight', 0) or 0)

        if status == 'invoice_completed_deliver':
            row_dict['invoice_no'] = getattr(r, 'invoice_no', None)
            row_dict['invoice_date'] = getattr(r, 'invoice_date', None)
            row_dict['invoice_amount'] = float(getattr(r, 'invoice_amount', 0) or 0)
            row_dict['gross_weight'] = float(getattr(r, 'sum_gross_weight', 0) or 0)
            row_dict['net_weight'] = float(getattr(r, 'sum_net_weight', 0) or 0)
            row_dict['stone_weight'] = float(getattr(r, 'sum_stone_weight', 0) or 0)
            
        processed_rows.append(row_dict)

    if status == 'hm_issue':
        hierarchical_rows = get_hm_issue_hierarchical_rows(processed_rows)
        template = 'partials/_view_supplier_hm_issue.html'
    elif status == 'hm_return':
        hierarchical_rows = get_hm_return_hierarchical_rows(processed_rows)
        template = 'partials/_view_hm_return_pending.html'
    elif status == 'hm_qc_issue':
        hierarchical_rows = get_hm_qc_issue_hierarchical_rows(processed_rows)
        template = 'partials/_view_hm_qc_issue_pending.html'
    elif status == 'qc_issue_receipt':
        hierarchical_rows = get_qc_issue_receipt_hierarchical_rows(processed_rows)
        template = 'partials/_view_supplier_qc_issue_receipt_pending.html'
    elif status == 'qc_completed_invoice':
        hierarchical_rows = get_qc_completed_invoice_hierarchical_rows(processed_rows)
        template = 'partials/_view_qc_completed_invoice_pending.html'
    elif status == 'invoice_completed_deliver':
        hierarchical_rows = get_invoice_completed_deliver_hierarchical_rows(processed_rows)
        template = 'partials/_view_invoice_completed_pending_deliver.html'
    else:
        hierarchical_rows = get_opp_hierarchical_rows(processed_rows)
        template = 'partials/_view_order_processing_pending.html'

    return render_template(template,
                         rows=hierarchical_rows,
                         stats=stats,
                         pagination={
                             'page': page,
                             'per_page': per_page,
                             'total': total_count,
                             'has_prev': page > 1,
                             'has_next': (page * per_page) < total_count,
                             'prev_num': page - 1,
                             'next_num': page + 1
                         },
                         current_username=session.get('username', ''))

@dashboard_bp.route('/api/order-processing-pending-status/feedback', methods=['POST'])
@jwt_required()
@require_perm('report.view')
def save_opp_feedback():
    data = request.json
    username = session.get('username', 'Unknown')
    
    feedback = OrderProcessingPendingFeedback(
        collection_owner=data.get('collection_owner'),
        collection=data.get('collection'),
        branch=data.get('branch'),
        supplier=data.get('supplier'),
        feedback_text=data.get('feedback_text'),
        feedback_category=data.get('feedback_category'),
        username=username
    )
    db.session.add(feedback)
    db.session.commit()
    return jsonify({"status": "success"})

@dashboard_bp.route('/api/order-processing-pending-status/po-details')
@jwt_required()
@require_perm('report.view')
def get_opp_po_details():
    collection_owner = request.args.get('collection_owner')
    collection = request.args.get('collection')
    supplier = request.args.get('supplier')
    
    latest_date = db.session.query(func.max(OrderProcessingPendingSnapshot.snapshot_date)).scalar()
    
    q = OrderProcessingPendingSnapshot.query.filter(
        OrderProcessingPendingSnapshot.snapshot_date == latest_date,
        OrderProcessingPendingSnapshot.collection_owner == collection_owner,
        OrderProcessingPendingSnapshot.collection == collection,
        OrderProcessingPendingSnapshot.supplier == supplier
    ).order_by(OrderProcessingPendingSnapshot.po_date.desc())
    
    pos = q.all()
    return render_template('partials/_order_processing_pending_po_details_modal.html', pos=pos)

def get_opp_hierarchical_rows(flat_rows):
    """
    Transforms flat rows into a hierarchical structure:
    Collection Owner (L1) -> Collection (L2) -> Supplier (L3 - Leaf)
    """
    import hashlib
    def get_id(*args):
        return hashlib.md5((":".join(map(str, args))).encode()).hexdigest()[:8]

    hierarchy = {}
    for r in flat_rows:
        o = r.get('collection_owner') or 'Unknown'
        c = r.get('collection') or 'Unknown'
        s = r.get('supplier') or 'Unknown'
        
        if o not in hierarchy:
            hierarchy[o] = {'wt': 0, 'pcs': 0, 'children': {}}
        if c not in hierarchy[o]['children']:
            hierarchy[o]['children'][c] = {'wt': 0, 'pcs': 0, 'children': []}
            
        hierarchy[o]['wt'] += r['weight']
        hierarchy[o]['pcs'] += r['pieces']
        hierarchy[o]['children'][c]['wt'] += r['weight']
        hierarchy[o]['children'][c]['pcs'] += r['pieces']
        hierarchy[o]['children'][c]['children'].append(r)

    result = []
    for o, o_data in sorted(hierarchy.items()):
        o_id = f"o_{get_id(o)}"
        result.append({
            'level': 1, 'id': o_id, 'parent_id': None, 'label': o, 
            'weight': o_data['wt'], 'pieces': o_data['pcs'], 
            'is_leaf': False
        })
        for c, c_data in sorted(o_data['children'].items()):
            c_id = f"c_{get_id(o, c)}"
            result.append({
                'level': 2, 'id': c_id, 'parent_id': o_id, 'label': c, 
                'weight': c_data['wt'], 'pieces': c_data['pcs'], 
                'is_leaf': False
            })
            for r in sorted(c_data['children'], key=lambda x: x['weight'], reverse=True):
                r_id = f"s_{get_id(o, c, r['supplier'])}"
                r.update({
                    'level': 3, 'id': r_id, 'parent_id': c_id, 
                    'label': r['supplier'], 'is_leaf': True
                })
                result.append(r)
    return result

def get_hm_latest_feedback_subquery():
    latest_id_q = db.session.query(
        SupplierHMIssueFeedback.hm_ro,
        SupplierHMIssueFeedback.make_owner,
        SupplierHMIssueFeedback.collection_owner,
        SupplierHMIssueFeedback.collection,
        SupplierHMIssueFeedback.hallmark_agent,
        SupplierHMIssueFeedback.supplier,
        func.max(SupplierHMIssueFeedback.id).label('max_id')
    ).group_by(
        SupplierHMIssueFeedback.hm_ro,
        SupplierHMIssueFeedback.make_owner,
        SupplierHMIssueFeedback.collection_owner,
        SupplierHMIssueFeedback.collection,
        SupplierHMIssueFeedback.hallmark_agent,
        SupplierHMIssueFeedback.supplier
    ).subquery('latest_fb_ids')

    return db.session.query(
        SupplierHMIssueFeedback.hm_ro,
        SupplierHMIssueFeedback.make_owner,
        SupplierHMIssueFeedback.collection_owner,
        SupplierHMIssueFeedback.collection,
        SupplierHMIssueFeedback.hallmark_agent,
        SupplierHMIssueFeedback.supplier,
        SupplierHMIssueFeedback.feedback_text,
        SupplierHMIssueFeedback.feedback_category,
        SupplierHMIssueFeedback.username,
        SupplierHMIssueFeedback.created_at
    ).join(
        latest_id_q,
        SupplierHMIssueFeedback.id == latest_id_q.c.max_id
    ).subquery('latest_feedback')

def get_hm_issue_hierarchical_rows(flat_rows):
    """
    HM RO (L1) -> Make Owner (L2) -> Collection Owner (L3) -> Collection (L4) -> Hallmark Agency (L5) -> Supplier (L6 - Leaf)
    """
    import hashlib
    def get_id(*args):
        return hashlib.md5((":".join(map(str, args))).encode()).hexdigest()[:8]

    hierarchy = {}
    for r in flat_rows:
        hm = r.get('hm_ro') or 'Unknown'
        mo = r.get('make_owner') or 'Unknown'
        co = r.get('collection_owner') or 'Unknown'
        cl = r.get('collection') or 'Unknown'
        ha = r.get('hallmark_agent') or 'Unknown'
        sp = r.get('supplier') or 'Unknown'
        
        if hm not in hierarchy:
            hierarchy[hm] = {'wt': 0, 'pcs': 0, 'gross_wt': 0, 'net_wt': 0, 'stone_wt': 0, 'po_count': 0, 'children': {}}
        if mo not in hierarchy[hm]['children']:
            hierarchy[hm]['children'][mo] = {'wt': 0, 'pcs': 0, 'gross_wt': 0, 'net_wt': 0, 'stone_wt': 0, 'po_count': 0, 'children': {}}
        if co not in hierarchy[hm]['children'][mo]['children']:
            hierarchy[hm]['children'][mo]['children'][co] = {'wt': 0, 'pcs': 0, 'gross_wt': 0, 'net_wt': 0, 'stone_wt': 0, 'po_count': 0, 'children': {}}
        if cl not in hierarchy[hm]['children'][mo]['children'][co]['children']:
            hierarchy[hm]['children'][mo]['children'][co]['children'][cl] = {'wt': 0, 'pcs': 0, 'gross_wt': 0, 'net_wt': 0, 'stone_wt': 0, 'po_count': 0, 'children': {}}
        if ha not in hierarchy[hm]['children'][mo]['children'][co]['children'][cl]['children']:
            hierarchy[hm]['children'][mo]['children'][co]['children'][cl]['children'][ha] = {'wt': 0, 'pcs': 0, 'gross_wt': 0, 'net_wt': 0, 'stone_wt': 0, 'po_count': 0, 'children': []}
            
        hierarchy[hm]['wt'] += r['weight']
        hierarchy[hm]['pcs'] += r['pieces']
        hierarchy[hm]['gross_wt'] += r.get('gross_weight', 0)
        hierarchy[hm]['net_wt'] += r.get('net_weight', 0)
        hierarchy[hm]['stone_wt'] += r.get('stone_weight', 0)
        hierarchy[hm]['po_count'] += r.get('po_count', 0)

        hierarchy[hm]['children'][mo]['wt'] += r['weight']
        hierarchy[hm]['children'][mo]['pcs'] += r['pieces']
        hierarchy[hm]['children'][mo]['gross_wt'] += r.get('gross_weight', 0)
        hierarchy[hm]['children'][mo]['net_wt'] += r.get('net_weight', 0)
        hierarchy[hm]['children'][mo]['stone_wt'] += r.get('stone_weight', 0)
        hierarchy[hm]['children'][mo]['po_count'] += r.get('po_count', 0)

        hierarchy[hm]['children'][mo]['children'][co]['wt'] += r['weight']
        hierarchy[hm]['children'][mo]['children'][co]['pcs'] += r['pieces']
        hierarchy[hm]['children'][mo]['children'][co]['gross_wt'] += r.get('gross_weight', 0)
        hierarchy[hm]['children'][mo]['children'][co]['net_wt'] += r.get('net_weight', 0)
        hierarchy[hm]['children'][mo]['children'][co]['stone_wt'] += r.get('stone_weight', 0)
        hierarchy[hm]['children'][mo]['children'][co]['po_count'] += r.get('po_count', 0)

        hierarchy[hm]['children'][mo]['children'][co]['children'][cl]['wt'] += r['weight']
        hierarchy[hm]['children'][mo]['children'][co]['children'][cl]['pcs'] += r['pieces']
        hierarchy[hm]['children'][mo]['children'][co]['children'][cl]['gross_wt'] += r.get('gross_weight', 0)
        hierarchy[hm]['children'][mo]['children'][co]['children'][cl]['net_wt'] += r.get('net_weight', 0)
        hierarchy[hm]['children'][mo]['children'][co]['children'][cl]['stone_wt'] += r.get('stone_weight', 0)
        hierarchy[hm]['children'][mo]['children'][co]['children'][cl]['po_count'] += r.get('po_count', 0)

        hierarchy[hm]['children'][mo]['children'][co]['children'][cl]['children'][ha]['wt'] += r['weight']
        hierarchy[hm]['children'][mo]['children'][co]['children'][cl]['children'][ha]['pcs'] += r['pieces']
        hierarchy[hm]['children'][mo]['children'][co]['children'][cl]['children'][ha]['gross_wt'] += r.get('gross_weight', 0)
        hierarchy[hm]['children'][mo]['children'][co]['children'][cl]['children'][ha]['net_wt'] += r.get('net_weight', 0)
        hierarchy[hm]['children'][mo]['children'][co]['children'][cl]['children'][ha]['stone_wt'] += r.get('stone_weight', 0)
        hierarchy[hm]['children'][mo]['children'][co]['children'][cl]['children'][ha]['po_count'] += r.get('po_count', 0)

        hierarchy[hm]['children'][mo]['children'][co]['children'][cl]['children'][ha]['children'].append(r)

    result = []
    for hm, hm_data in sorted(hierarchy.items()):
        hm_id = f"hm_{get_id(hm)}"
        result.append({
            'level': 1, 'id': hm_id, 'parent_id': None, 'label': hm, 
            'weight': hm_data['wt'], 'pieces': hm_data['pcs'], 
            'gross_weight': hm_data['gross_wt'], 'net_weight': hm_data['net_wt'], 'stone_weight': hm_data['stone_wt'],
            'po_count': hm_data['po_count'],
            'is_leaf': False
        })
        for mo, mo_data in sorted(hm_data['children'].items()):
            mo_id = f"mo_{get_id(hm, mo)}"
            result.append({
                'level': 2, 'id': mo_id, 'parent_id': hm_id, 'label': mo, 
                'weight': mo_data['wt'], 'pieces': mo_data['pcs'], 
                'gross_weight': mo_data['gross_wt'], 'net_weight': mo_data['net_wt'], 'stone_weight': mo_data['stone_wt'],
                'po_count': mo_data['po_count'],
                'is_leaf': False
            })
            for co, co_data in sorted(mo_data['children'].items()):
                co_id = f"co_{get_id(hm, mo, co)}"
                result.append({
                    'level': 3, 'id': co_id, 'parent_id': mo_id, 'label': co, 
                    'weight': co_data['wt'], 'pieces': co_data['pcs'], 
                    'gross_weight': co_data['gross_wt'], 'net_weight': co_data['net_wt'], 'stone_weight': co_data['stone_wt'],
                    'po_count': co_data['po_count'],
                    'is_leaf': False
                })
                for cl, cl_data in sorted(co_data['children'].items()):
                    cl_id = f"cl_{get_id(hm, mo, co, cl)}"
                    result.append({
                        'level': 4, 'id': cl_id, 'parent_id': co_id, 'label': cl, 
                        'weight': cl_data['wt'], 'pieces': cl_data['pcs'], 
                        'gross_weight': cl_data['gross_wt'], 'net_weight': cl_data['net_wt'], 'stone_weight': cl_data['stone_wt'],
                        'po_count': cl_data['po_count'],
                        'is_leaf': False
                    })
                    for ha, ha_data in sorted(cl_data['children'].items()):
                        ha_id = f"ha_{get_id(hm, mo, co, cl, ha)}"
                        result.append({
                            'level': 5, 'id': ha_id, 'parent_id': cl_id, 'label': ha, 
                            'weight': ha_data['wt'], 'pieces': ha_data['pcs'], 
                            'gross_weight': ha_data['gross_wt'], 'net_weight': ha_data['net_wt'], 'stone_weight': ha_data['stone_wt'],
                            'po_count': ha_data['po_count'],
                            'is_leaf': False
                        })
                        for r in sorted(ha_data['children'], key=lambda x: x['supplier']):
                            result.append({
                                'level': 6, 'id': f"leaf_{get_id(hm, mo, co, cl, ha, r['supplier'])}", 'parent_id': ha_id, 'label': r['supplier'],
                                'weight': r['weight'], 'pieces': r['pieces'], 
                                'gross_weight': r.get('gross_weight', 0), 'net_weight': r.get('net_weight', 0), 'stone_weight': r.get('stone_weight', 0),
                                'po_count': r.get('po_count', 0),
                                'is_leaf': True,
                                'hm_ro': hm, 'make_owner': mo, 'collection_owner': co, 'collection': cl, 'hallmark_agent': ha, 'supplier': r['supplier'],
                                'feedback_text': r['feedback_text'], 'feedback_category': r['feedback_category'], 'feedback_username': r['feedback_username']
                            })
    return result

@dashboard_bp.route('/api/supplier-hm-issue/feedback', methods=['POST'])
@jwt_required()
@require_perm('report.view')
def save_hm_issue_feedback():
    data = request.json
    username = session.get('username', 'Unknown')
    
    feedback = SupplierHMIssueFeedback(
        hm_ro=data.get('hm_ro'),
        make_owner=data.get('make_owner'),
        collection_owner=data.get('collection_owner'),
        collection=data.get('collection'),
        hallmark_agent=data.get('hallmark_agent'),
        supplier=data.get('supplier'),
        feedback_text=data.get('feedback_text'),
        feedback_category=data.get('feedback_category'),
        username=username
    )
    db.session.add(feedback)
    db.session.commit()
    return jsonify({"status": "success"})

@dashboard_bp.route('/api/supplier-hm-issue/details')
@jwt_required()
@require_perm('report.view')
def get_hm_issue_details():
    hm_ro = request.args.get('hm_ro')
    make_owner = request.args.get('make_owner')
    collection_owner = request.args.get('collection_owner')
    collection = request.args.get('collection')
    hallmark_agent = request.args.get('hallmark_agent')
    supplier = request.args.get('supplier')
    
    latest_date = db.session.query(func.max(SupplierHMIssueSnapshot.snapshot_date)).scalar()
    
    q = SupplierHMIssueSnapshot.query.filter(
        SupplierHMIssueSnapshot.snapshot_date == latest_date,
        SupplierHMIssueSnapshot.hm_ro == hm_ro,
        SupplierHMIssueSnapshot.make_owner == make_owner,
        SupplierHMIssueSnapshot.collection_owner == collection_owner,
        SupplierHMIssueSnapshot.collection == collection,
        SupplierHMIssueSnapshot.hallmark_agent == hallmark_agent,
        SupplierHMIssueSnapshot.supplier == supplier
    ).order_by(SupplierHMIssueSnapshot.po_date.desc())
    
    pos = q.all()
    return render_template('partials/_hm_issue_details_modal.html', pos=pos)

def get_hm_return_latest_feedback_subquery():
    latest_id_q = db.session.query(
        HMCompletedReturnFeedback.hm_ro,
        HMCompletedReturnFeedback.make_owner,
        HMCompletedReturnFeedback.collection_owner,
        HMCompletedReturnFeedback.collection,
        HMCompletedReturnFeedback.hallmark_agent,
        HMCompletedReturnFeedback.supplier,
        func.max(HMCompletedReturnFeedback.id).label('max_id')
    ).group_by(
        HMCompletedReturnFeedback.hm_ro,
        HMCompletedReturnFeedback.make_owner,
        HMCompletedReturnFeedback.collection_owner,
        HMCompletedReturnFeedback.collection,
        HMCompletedReturnFeedback.hallmark_agent,
        HMCompletedReturnFeedback.supplier
    ).subquery('latest_fb_ids')

    return db.session.query(
        HMCompletedReturnFeedback.hm_ro,
        HMCompletedReturnFeedback.make_owner,
        HMCompletedReturnFeedback.collection_owner,
        HMCompletedReturnFeedback.collection,
        HMCompletedReturnFeedback.hallmark_agent,
        HMCompletedReturnFeedback.supplier,
        HMCompletedReturnFeedback.feedback_text,
        HMCompletedReturnFeedback.feedback_category,
        HMCompletedReturnFeedback.username,
        HMCompletedReturnFeedback.created_at
    ).join(
        latest_id_q,
        HMCompletedReturnFeedback.id == latest_id_q.c.max_id
    ).subquery('latest_feedback')

def get_hm_return_hierarchical_rows(flat_rows):
    import hashlib
    def get_id(*args):
        return hashlib.md5((":".join(map(str, args))).encode()).hexdigest()[:8]

    hierarchy = {}
    for r in flat_rows:
        hm = r.get('hm_ro') or 'Unknown'
        mo = r.get('make_owner') or 'Unknown'
        co = r.get('collection_owner') or 'Unknown'
        cl = r.get('collection') or 'Unknown'
        ha = r.get('hallmark_agent') or 'Unknown'
        sp = r.get('supplier') or 'Unknown'
        
        if hm not in hierarchy:
            hierarchy[hm] = {'wt': 0, 'pcs': 0, 'po_count': 0, 'net_wt': 0, 'gross_wt': 0, 'children': {}}
        if mo not in hierarchy[hm]['children']:
            hierarchy[hm]['children'][mo] = {'wt': 0, 'pcs': 0, 'po_count': 0, 'net_wt': 0, 'gross_wt': 0, 'children': {}}
        if co not in hierarchy[hm]['children'][mo]['children']:
            hierarchy[hm]['children'][mo]['children'][co] = {'wt': 0, 'pcs': 0, 'po_count': 0, 'net_wt': 0, 'gross_wt': 0, 'children': {}}
        if cl not in hierarchy[hm]['children'][mo]['children'][co]['children']:
            hierarchy[hm]['children'][mo]['children'][co]['children'][cl] = {'wt': 0, 'pcs': 0, 'po_count': 0, 'net_wt': 0, 'gross_wt': 0, 'children': {}}
        if ha not in hierarchy[hm]['children'][mo]['children'][co]['children'][cl]['children']:
            hierarchy[hm]['children'][mo]['children'][co]['children'][cl]['children'][ha] = {'wt': 0, 'pcs': 0, 'po_count': 0, 'net_wt': 0, 'gross_wt': 0, 'children': []}
            
        hierarchy[hm]['wt'] += r['weight']
        hierarchy[hm]['pcs'] += r['pieces']
        hierarchy[hm]['po_count'] += r.get('po_count', 0)
        hierarchy[hm]['net_wt'] += r.get('net_weight', 0)
        hierarchy[hm]['gross_wt'] += r.get('gross_weight', 0)

        hierarchy[hm]['children'][mo]['wt'] += r['weight']
        hierarchy[hm]['children'][mo]['pcs'] += r['pieces']
        hierarchy[hm]['children'][mo]['po_count'] += r.get('po_count', 0)
        hierarchy[hm]['children'][mo]['net_wt'] += r.get('net_weight', 0)
        hierarchy[hm]['children'][mo]['gross_wt'] += r.get('gross_weight', 0)

        hierarchy[hm]['children'][mo]['children'][co]['wt'] += r['weight']
        hierarchy[hm]['children'][mo]['children'][co]['pcs'] += r['pieces']
        hierarchy[hm]['children'][mo]['children'][co]['po_count'] += r.get('po_count', 0)
        hierarchy[hm]['children'][mo]['children'][co]['net_wt'] += r.get('net_weight', 0)
        hierarchy[hm]['children'][mo]['children'][co]['gross_wt'] += r.get('gross_weight', 0)

        hierarchy[hm]['children'][mo]['children'][co]['children'][cl]['wt'] += r['weight']
        hierarchy[hm]['children'][mo]['children'][co]['children'][cl]['pcs'] += r['pieces']
        hierarchy[hm]['children'][mo]['children'][co]['children'][cl]['po_count'] += r.get('po_count', 0)
        hierarchy[hm]['children'][mo]['children'][co]['children'][cl]['net_wt'] += r.get('net_weight', 0)
        hierarchy[hm]['children'][mo]['children'][co]['children'][cl]['gross_wt'] += r.get('gross_weight', 0)

        hierarchy[hm]['children'][mo]['children'][co]['children'][cl]['children'][ha]['wt'] += r['weight']
        hierarchy[hm]['children'][mo]['children'][co]['children'][cl]['children'][ha]['pcs'] += r['pieces']
        hierarchy[hm]['children'][mo]['children'][co]['children'][cl]['children'][ha]['po_count'] += r.get('po_count', 0)
        hierarchy[hm]['children'][mo]['children'][co]['children'][cl]['children'][ha]['net_wt'] += r.get('net_weight', 0)
        hierarchy[hm]['children'][mo]['children'][co]['children'][cl]['children'][ha]['gross_wt'] += r.get('gross_weight', 0)
        hierarchy[hm]['children'][mo]['children'][co]['children'][cl]['children'][ha]['children'].append(r)

    def calc_efficiency(n, g):
        if not g: return 0
        return round((float(n) / float(g)) * 100, 2)

    result = []
    for hm, hm_data in sorted(hierarchy.items()):
        hm_id = f"hmret_{get_id(hm)}"
        result.append({
            'level': 1, 'id': hm_id, 'parent_id': None, 'label': hm, 
            'weight': hm_data['wt'], 'pieces': hm_data['pcs'], 'po_count': hm_data['po_count'], 
            'efficiency': calc_efficiency(hm_data['net_wt'], hm_data['gross_wt']),
            'is_leaf': False
        })
        for mo, mo_data in sorted(hm_data['children'].items()):
            mo_id = f"mo_{get_id(hm, mo)}"
            result.append({
                'level': 2, 'id': mo_id, 'parent_id': hm_id, 'label': mo, 
                'weight': mo_data['wt'], 'pieces': mo_data['pcs'], 'po_count': mo_data['po_count'], 
                'efficiency': calc_efficiency(mo_data['net_wt'], mo_data['gross_wt']),
                'is_leaf': False
            })
            for co, co_data in sorted(mo_data['children'].items()):
                co_id = f"co_{get_id(hm, mo, co)}"
                result.append({
                    'level': 3, 'id': co_id, 'parent_id': mo_id, 'label': co, 
                    'weight': co_data['wt'], 'pieces': co_data['pcs'], 'po_count': co_data['po_count'], 
                    'efficiency': calc_efficiency(co_data['net_wt'], co_data['gross_wt']),
                    'is_leaf': False
                })
                for cl, cl_data in sorted(co_data['children'].items()):
                    cl_id = f"cl_{get_id(hm, mo, co, cl)}"
                    result.append({
                        'level': 4, 'id': cl_id, 'parent_id': co_id, 'label': cl, 
                        'weight': cl_data['wt'], 'pieces': cl_data['pcs'], 'po_count': cl_data['po_count'], 
                        'efficiency': calc_efficiency(cl_data['net_wt'], cl_data['gross_wt']),
                        'is_leaf': False
                    })
                    for ha, ha_data in sorted(cl_data['children'].items()):
                        ha_id = f"ha_{get_id(hm, mo, co, cl, ha)}"
                        result.append({
                            'level': 5, 'id': ha_id, 'parent_id': cl_id, 'label': ha, 
                            'weight': ha_data['wt'], 'pieces': ha_data['pcs'], 'po_count': ha_data['po_count'], 
                            'efficiency': calc_efficiency(ha_data['net_wt'], ha_data['gross_wt']),
                            'is_leaf': False
                        })
                        for r in sorted(ha_data['children'], key=lambda x: x['supplier']):
                            result.append({
                                'level': 6, 'id': f"leaf_{get_id(hm, mo, co, cl, ha, r['supplier'])}", 'parent_id': ha_id, 'label': r['supplier'],
                                'weight': r['weight'], 'pieces': r['pieces'], 
                                'po_count': r.get('po_count', 0),
                                'efficiency': calc_efficiency(r.get('net_weight', 0), r.get('gross_weight', 0)),
                                'is_leaf': True,
                                'hm_ro': hm, 'make_owner': mo, 'collection_owner': co, 'collection': cl, 'hallmark_agent': ha, 'supplier': r['supplier'],
                                'hm_agent_invoice_receipt_date': r['hm_agent_invoice_receipt_date'],
                                'hm_agent_invoice_receipt_no': r['hm_agent_invoice_receipt_no'],
                                'hm_completed_date': r['hm_completed_date'],
                                'feedback_text': r['feedback_text'], 'feedback_category': r['feedback_category'], 'feedback_username': r['feedback_username']
                            })
    return result

@dashboard_bp.route('/api/hm-return/feedback', methods=['POST'])
@jwt_required()
@require_perm('report.view')
def save_hm_return_feedback():
    data = request.json
    username = session.get('username', 'Unknown')
    feedback = HMCompletedReturnFeedback(
        hm_ro=data.get('hm_ro'),
        make_owner=data.get('make_owner'),
        collection_owner=data.get('collection_owner'),
        collection=data.get('collection'),
        hallmark_agent=data.get('hallmark_agent'),
        supplier=data.get('supplier'),
        feedback_text=data.get('feedback_text'),
        feedback_category=data.get('feedback_category'),
        username=username
    )
    db.session.add(feedback)
    db.session.commit()
    return jsonify({"status": "success"})

@dashboard_bp.route('/api/hm-return/details')
@jwt_required()
@require_perm('report.view')
def get_hm_return_details():
    hm_ro = request.args.get('hm_ro')
    make_owner = request.args.get('make_owner')
    collection_owner = request.args.get('collection_owner')
    collection = request.args.get('collection')
    hallmark_agent = request.args.get('hallmark_agent')
    supplier = request.args.get('supplier')
    
    latest_date = db.session.query(func.max(HMCompletedReturnSnapshot.snapshot_date)).scalar()
    pos = HMCompletedReturnSnapshot.query.filter(
        HMCompletedReturnSnapshot.snapshot_date == latest_date,
        HMCompletedReturnSnapshot.hm_ro == hm_ro,
        HMCompletedReturnSnapshot.make_owner == make_owner,
        HMCompletedReturnSnapshot.collection_owner == collection_owner,
        HMCompletedReturnSnapshot.collection == collection,
        HMCompletedReturnSnapshot.hallmark_agent == hallmark_agent,
        HMCompletedReturnSnapshot.supplier == supplier
    ).order_by(HMCompletedReturnSnapshot.po_date.desc()).all()
    
    return render_template('partials/_hm_return_details_modal.html', pos=pos)

@dashboard_bp.route('/api/hm-return/logistic-details')
@jwt_required()
@require_perm('report.view')
def get_hm_return_logistic_details():
    hm_ro = request.args.get('hm_ro')
    make_owner = request.args.get('make_owner')
    collection_owner = request.args.get('collection_owner')
    collection = request.args.get('collection')
    hallmark_agent = request.args.get('hallmark_agent')
    supplier = request.args.get('supplier')
    
    latest_date = db.session.query(func.max(HMCompletedReturnSnapshot.snapshot_date)).scalar()
    details = db.session.query(
        HMCompletedReturnSnapshot.logistic_mobile_no,
        HMCompletedReturnSnapshot.logistic_date,
        HMCompletedReturnSnapshot.vehicle_no
    ).filter(
        HMCompletedReturnSnapshot.snapshot_date == latest_date,
        HMCompletedReturnSnapshot.hm_ro == hm_ro,
        HMCompletedReturnSnapshot.make_owner == make_owner,
        HMCompletedReturnSnapshot.collection_owner == collection_owner,
        HMCompletedReturnSnapshot.collection == collection,
        HMCompletedReturnSnapshot.hallmark_agent == hallmark_agent,
        HMCompletedReturnSnapshot.supplier == supplier
    ).distinct().all()
    
    return render_template('partials/_hm_return_logistic_modal.html', details=details)

def get_hm_qc_issue_latest_feedback_subquery():
    latest_id_q = db.session.query(
        HMReturnQCIssueFeedback.hm_ro,
        HMReturnQCIssueFeedback.make_owner,
        HMReturnQCIssueFeedback.collection_owner,
        HMReturnQCIssueFeedback.collection,
        HMReturnQCIssueFeedback.hallmark_agent,
        HMReturnQCIssueFeedback.party,
        func.max(HMReturnQCIssueFeedback.id).label('max_id')
    ).group_by(
        HMReturnQCIssueFeedback.hm_ro,
        HMReturnQCIssueFeedback.make_owner,
        HMReturnQCIssueFeedback.collection_owner,
        HMReturnQCIssueFeedback.collection,
        HMReturnQCIssueFeedback.hallmark_agent,
        HMReturnQCIssueFeedback.party
    ).subquery('latest_fb_ids')

    return db.session.query(
        HMReturnQCIssueFeedback.hm_ro,
        HMReturnQCIssueFeedback.make_owner,
        HMReturnQCIssueFeedback.collection_owner,
        HMReturnQCIssueFeedback.collection,
        HMReturnQCIssueFeedback.hallmark_agent,
        HMReturnQCIssueFeedback.party,
        HMReturnQCIssueFeedback.feedback_text,
        HMReturnQCIssueFeedback.feedback_category,
        HMReturnQCIssueFeedback.username,
        HMReturnQCIssueFeedback.created_at
    ).join(
        latest_id_q,
        HMReturnQCIssueFeedback.id == latest_id_q.c.max_id
    ).subquery('latest_feedback')

def get_hm_qc_issue_hierarchical_rows(flat_rows):
    import hashlib
    def get_id(*args):
        return hashlib.md5((":".join(map(str, args))).encode()).hexdigest()[:8]

    hierarchy = {}
    for r in flat_rows:
        ob = r.get('hm_ro') or 'Unknown HM RO'
        mo = r.get('make_owner') or 'Unknown'
        co = r.get('collection_owner') or 'Unknown'
        cl = r.get('collection') or 'Unknown'
        ha = r.get('hallmark_agent') or 'Unknown'
        pt = r.get('party') or 'Unknown'
        
        if ob not in hierarchy:
            hierarchy[ob] = {'wt': 0, 'pcs': 0, 'children': {}}
        if mo not in hierarchy[ob]['children']:
            hierarchy[ob]['children'][mo] = {'wt': 0, 'pcs': 0, 'children': {}}
        if co not in hierarchy[ob]['children'][mo]['children']:
            hierarchy[ob]['children'][mo]['children'][co] = {'wt': 0, 'pcs': 0, 'children': {}}
        if cl not in hierarchy[ob]['children'][mo]['children'][co]['children']:
            hierarchy[ob]['children'][mo]['children'][co]['children'][cl] = {'wt': 0, 'pcs': 0, 'children': {}}
        if ha not in hierarchy[ob]['children'][mo]['children'][co]['children'][cl]['children']:
            hierarchy[ob]['children'][mo]['children'][co]['children'][cl]['children'][ha] = {'wt': 0, 'pcs': 0, 'children': []}
            
        hierarchy[ob]['wt'] += r['weight']
        hierarchy[ob]['pcs'] += r['pieces']
        hierarchy[ob]['children'][mo]['wt'] += r['weight']
        hierarchy[ob]['children'][mo]['pcs'] += r['pieces']
        hierarchy[ob]['children'][mo]['children'][co]['wt'] += r['weight']
        hierarchy[ob]['children'][mo]['children'][co]['pcs'] += r['pieces']
        hierarchy[ob]['children'][mo]['children'][co]['children'][cl]['wt'] += r['weight']
        hierarchy[ob]['children'][mo]['children'][co]['children'][cl]['pcs'] += r['pieces']
        hierarchy[ob]['children'][mo]['children'][co]['children'][cl]['children'][ha]['wt'] += r['weight']
        hierarchy[ob]['children'][mo]['children'][co]['children'][cl]['children'][ha]['pcs'] += r['pieces']
        hierarchy[ob]['children'][mo]['children'][co]['children'][cl]['children'][ha]['children'].append(r)

    result = []
    for ob, ob_data in sorted(hierarchy.items()):
        ob_id = f"ob_{get_id(ob)}"
        result.append({'level': 1, 'id': ob_id, 'parent_id': None, 'label': ob, 'weight': ob_data['wt'], 'pieces': ob_data['pcs'], 'is_leaf': False})
        for mo, mo_data in sorted(ob_data['children'].items()):
            mo_id = f"mo_{get_id(ob, mo)}"
            result.append({'level': 2, 'id': mo_id, 'parent_id': ob_id, 'label': mo, 'weight': mo_data['wt'], 'pieces': mo_data['pcs'], 'is_leaf': False})
            for co, co_data in sorted(mo_data['children'].items()):
                co_id = f"co_{get_id(ob, mo, co)}"
                result.append({'level': 3, 'id': co_id, 'parent_id': mo_id, 'label': co, 'weight': co_data['wt'], 'pieces': co_data['pcs'], 'is_leaf': False})
                for cl, cl_data in sorted(co_data['children'].items()):
                    cl_id = f"cl_{get_id(ob, mo, co, cl)}"
                    result.append({'level': 4, 'id': cl_id, 'parent_id': co_id, 'label': cl, 'weight': cl_data['wt'], 'pieces': cl_data['pcs'], 'is_leaf': False})
                    for ha, ha_data in sorted(cl_data['children'].items()):
                        ha_id = f"ha_{get_id(ob, mo, co, cl, ha)}"
                        result.append({'level': 5, 'id': ha_id, 'parent_id': cl_id, 'label': ha, 'weight': ha_data['wt'], 'pieces': ha_data['pcs'], 'is_leaf': False})
                        for r in sorted(ha_data['children'], key=lambda x: x['party']):
                            result.append({
                                'level': 6, 'id': f"leaf_{get_id(ob, mo, co, cl, ha, r['party'])}", 'parent_id': ha_id, 'label': r['party'],
                                'weight': r['weight'], 'pieces': r['pieces'], 'is_leaf': True,
                                'hm_ro': ob, 'make_owner': mo, 'collection_owner': co, 'collection': cl, 'hallmark_agent': ha, 'party': r['party'],
                                'hm_agent_invoice_receipt_date': r['hm_agent_invoice_receipt_date'],
                                'hm_agent_invoice_receipt_no': r['hm_agent_invoice_receipt_no'],
                                'feedback_text': r['feedback_text'], 'feedback_category': r['feedback_category'], 'feedback_username': r['feedback_username']
                            })
    return result

@dashboard_bp.route('/api/hm-qc-issue/feedback', methods=['POST'])
@jwt_required()
@require_perm('report.view')
def save_hm_qc_issue_feedback():
    data = request.json
    username = session.get('username', 'Unknown')
    feedback = HMReturnQCIssueFeedback(
        hm_ro=data.get('hm_ro'),
        make_owner=data.get('make_owner'),
        collection_owner=data.get('collection_owner'),
        collection=data.get('collection'),
        hallmark_agent=data.get('hallmark_agent'),
        party=data.get('party'),
        feedback_text=data.get('feedback_text'),
        feedback_category=data.get('feedback_category'),
        username=username
    )
    db.session.add(feedback)
    db.session.commit()
    return jsonify({"status": "success"})

@dashboard_bp.route('/api/hm-qc-issue/details')
@jwt_required()
@require_perm('report.view')
def get_hm_qc_issue_details():
    hm_ro = request.args.get('hm_ro')
    make_owner = request.args.get('make_owner')
    collection_owner = request.args.get('collection_owner')
    collection = request.args.get('collection')
    hallmark_agent = request.args.get('hallmark_agent')
    party = request.args.get('party')
    
    latest_date = db.session.query(func.max(HMReturnQCIssueSnapshot.snapshot_date)).scalar()
    pos = HMReturnQCIssueSnapshot.query.filter(
        HMReturnQCIssueSnapshot.snapshot_date == latest_date,
        HMReturnQCIssueSnapshot.hm_ro == hm_ro,
        HMReturnQCIssueSnapshot.make_owner == make_owner,
        HMReturnQCIssueSnapshot.collection_owner == collection_owner,
        HMReturnQCIssueSnapshot.collection == collection,
        HMReturnQCIssueSnapshot.hallmark_agent == hallmark_agent,
        HMReturnQCIssueSnapshot.party == party
    ).order_by(HMReturnQCIssueSnapshot.po_date.desc()).all()
    
    return render_template('partials/_hm_qc_issue_details_modal.html', pos=pos)

def get_qc_issue_receipt_latest_feedback_subquery():
    latest_id_q = db.session.query(
        SupplierQCIssueReceiptPendingFeedback.qc_ro,
        SupplierQCIssueReceiptPendingFeedback.make_owner,
        SupplierQCIssueReceiptPendingFeedback.collection_owner,
        SupplierQCIssueReceiptPendingFeedback.collection,
        SupplierQCIssueReceiptPendingFeedback.party,
        SupplierQCIssueReceiptPendingFeedback.order_branch,
        SupplierQCIssueReceiptPendingFeedback.business_head_name,
        func.max(SupplierQCIssueReceiptPendingFeedback.id).label('max_id')
    ).group_by(
        SupplierQCIssueReceiptPendingFeedback.qc_ro,
        SupplierQCIssueReceiptPendingFeedback.make_owner,
        SupplierQCIssueReceiptPendingFeedback.collection_owner,
        SupplierQCIssueReceiptPendingFeedback.collection,
        SupplierQCIssueReceiptPendingFeedback.party,
        SupplierQCIssueReceiptPendingFeedback.order_branch,
        SupplierQCIssueReceiptPendingFeedback.business_head_name
    ).subquery('latest_fb_ids')

    return db.session.query(
        SupplierQCIssueReceiptPendingFeedback.qc_ro,
        SupplierQCIssueReceiptPendingFeedback.make_owner,
        SupplierQCIssueReceiptPendingFeedback.collection_owner,
        SupplierQCIssueReceiptPendingFeedback.collection,
        SupplierQCIssueReceiptPendingFeedback.party,
        SupplierQCIssueReceiptPendingFeedback.order_branch,
        SupplierQCIssueReceiptPendingFeedback.business_head_name,
        SupplierQCIssueReceiptPendingFeedback.feedback_text,
        SupplierQCIssueReceiptPendingFeedback.feedback_category,
        SupplierQCIssueReceiptPendingFeedback.username,
        SupplierQCIssueReceiptPendingFeedback.created_at
    ).join(
        latest_id_q,
        SupplierQCIssueReceiptPendingFeedback.id == latest_id_q.c.max_id
    ).subquery('latest_feedback')

def get_qc_issue_receipt_hierarchical_rows(flat_rows):
    import hashlib
    def get_id(*args):
        return hashlib.md5((":".join(map(str, args))).encode()).hexdigest()[:8]

    hierarchy = {}
    for r in flat_rows:
        ro = r.get('qc_ro') or 'Unknown'
        mo = r.get('make_owner') or 'Unknown'
        co = r.get('collection_owner') or 'Unknown'
        cl = r.get('collection') or 'Unknown'
        py = r.get('party') or 'Unknown'
        
        if ro not in hierarchy:
            hierarchy[ro] = {'wt': 0, 'pcs': 0, 'children': {}}
        if mo not in hierarchy[ro]['children']:
            hierarchy[ro]['children'][mo] = {'wt': 0, 'pcs': 0, 'children': {}}
        if co not in hierarchy[ro]['children'][mo]['children']:
            hierarchy[ro]['children'][mo]['children'][co] = {'wt': 0, 'pcs': 0, 'children': {}}
        if cl not in hierarchy[ro]['children'][mo]['children'][co]['children']:
            hierarchy[ro]['children'][mo]['children'][co]['children'][cl] = {'wt': 0, 'pcs': 0, 'children': []}
            
        hierarchy[ro]['wt'] += r['weight']
        hierarchy[ro]['pcs'] += r['pieces']
        hierarchy[ro]['children'][mo]['wt'] += r['weight']
        hierarchy[ro]['children'][mo]['pcs'] += r['pieces']
        hierarchy[ro]['children'][mo]['children'][co]['wt'] += r['weight']
        hierarchy[ro]['children'][mo]['children'][co]['pcs'] += r['pieces']
        hierarchy[ro]['children'][mo]['children'][co]['children'][cl]['wt'] += r['weight']
        hierarchy[ro]['children'][mo]['children'][co]['children'][cl]['pcs'] += r['pieces']
        hierarchy[ro]['children'][mo]['children'][co]['children'][cl]['children'].append(r)

    result = []
    for ro, ro_data in sorted(hierarchy.items()):
        ro_id = f"ro_{get_id(ro)}"
        result.append({'level': 1, 'id': ro_id, 'parent_id': None, 'label': ro, 'weight': ro_data['wt'], 'pieces': ro_data['pcs'], 'is_leaf': False})
        for mo, mo_data in sorted(ro_data['children'].items()):
            mo_id = f"mo_{get_id(ro, mo)}"
            result.append({'level': 2, 'id': mo_id, 'parent_id': ro_id, 'label': mo, 'weight': mo_data['wt'], 'pieces': mo_data['pcs'], 'is_leaf': False})
            for co, co_data in sorted(mo_data['children'].items()):
                co_id = f"co_{get_id(ro, mo, co)}"
                result.append({'level': 3, 'id': co_id, 'parent_id': mo_id, 'label': co, 'weight': co_data['wt'], 'pieces': co_data['pcs'], 'is_leaf': False})
                for cl, cl_data in sorted(co_data['children'].items()):
                    cl_id = f"cl_{get_id(ro, mo, co, cl)}"
                    result.append({'level': 4, 'id': cl_id, 'parent_id': co_id, 'label': cl, 'weight': cl_data['wt'], 'pieces': cl_data['pcs'], 'is_leaf': False})
                    for r in sorted(cl_data['children'], key=lambda x: x['party']):
                        result.append({
                            'level': 5, 'id': f"leaf_{get_id(ro, mo, co, cl, r['party'])}", 'parent_id': cl_id, 'label': r['party'],
                            'weight': r['weight'], 'pieces': r['pieces'], 'is_leaf': True,
                            'qc_ro': ro, 'make_owner': mo, 'collection_owner': co, 'collection': cl, 'party': r['party'],
                            'qc_issue_receipt_date': r['qc_issue_receipt_date'],
                            'qc_issue_receipt_no': r['qc_issue_receipt_no'],
                            'feedback_text': r['feedback_text'], 'feedback_category': r['feedback_category'], 'feedback_username': r['feedback_username']
                        })
    return result

@dashboard_bp.route('/api/qc-issue-receipt/feedback', methods=['POST'])
@jwt_required()
@require_perm('report.view')
def save_qc_issue_receipt_feedback():
    data = request.json
    username = session.get('username', 'Unknown')
    feedback = SupplierQCIssueReceiptPendingFeedback(
        qc_ro=data.get('qc_ro'),
        make_owner=data.get('make_owner'),
        collection_owner=data.get('collection_owner'),
        collection=data.get('collection'),
        party=data.get('party'),
        feedback_text=data.get('feedback_text'),
        feedback_category=data.get('feedback_category'),
        username=username
    )
    db.session.add(feedback)
    db.session.commit()
    return jsonify({"status": "success"})

@dashboard_bp.route('/api/qc-issue-receipt/details')
@jwt_required()
@require_perm('report.view')
def get_qc_issue_receipt_details():
    qc_ro = request.args.get('qc_ro')
    make_owner = request.args.get('make_owner')
    collection_owner = request.args.get('collection_owner')
    collection = request.args.get('collection')
    party = request.args.get('party')
    
    latest_date = db.session.query(func.max(SupplierQCIssueReceiptPendingSnapshot.snapshot_date)).scalar()
    pos = SupplierQCIssueReceiptPendingSnapshot.query.filter(
        SupplierQCIssueReceiptPendingSnapshot.snapshot_date == latest_date,
        SupplierQCIssueReceiptPendingSnapshot.qc_ro == qc_ro,
        SupplierQCIssueReceiptPendingSnapshot.make_owner == make_owner,
        SupplierQCIssueReceiptPendingSnapshot.collection_owner == collection_owner,
        SupplierQCIssueReceiptPendingSnapshot.collection == collection,
        SupplierQCIssueReceiptPendingSnapshot.party == party
    ).order_by(SupplierQCIssueReceiptPendingSnapshot.po_date.desc()).all()
    
    return render_template('partials/_supplier_qc_issue_receipt_pending_details_modal.html', pos=pos)

def get_qc_completed_invoice_latest_feedback_subquery():
    subq = db.session.query(
        QCCompletedInvoicePendingFeedback.qc_ro,
        QCCompletedInvoicePendingFeedback.make_owner,
        QCCompletedInvoicePendingFeedback.collection_owner,
        QCCompletedInvoicePendingFeedback.collection,
        QCCompletedInvoicePendingFeedback.party,
        func.max(QCCompletedInvoicePendingFeedback.id).label('max_id')
    ).group_by(
        QCCompletedInvoicePendingFeedback.qc_ro,
        QCCompletedInvoicePendingFeedback.make_owner,
        QCCompletedInvoicePendingFeedback.collection_owner,
        QCCompletedInvoicePendingFeedback.collection,
        QCCompletedInvoicePendingFeedback.party
    ).subquery()
    
    return db.session.query(QCCompletedInvoicePendingFeedback).join(
        subq, QCCompletedInvoicePendingFeedback.id == subq.c.max_id
    ).subquery('latest_fb')

def get_qc_completed_invoice_hierarchical_rows(processed_rows):
    hierarchy = {}
    def get_id(*args): return "_".join(str(a).replace(" ", "_").replace("&", "_") for a in args)
    
    for r in processed_rows:
        ro = r['qc_ro'] or 'Unknown QC RO'
        mo = r['make_owner'] or 'Unknown MO'
        co = r['collection_owner'] or 'Unknown CO'
        cl = r['collection'] or 'Unknown Coll'
        
        if ro not in hierarchy: hierarchy[ro] = {'wt': 0, 'pcs': 0, 'gross_wt': 0, 'net_wt': 0, 'stone_wt': 0, 'bc_wt': 0, 'children': {}}
        if mo not in hierarchy[ro]['children']: hierarchy[ro]['children'][mo] = {'wt': 0, 'pcs': 0, 'gross_wt': 0, 'net_wt': 0, 'stone_wt': 0, 'bc_wt': 0, 'children': {}}
        if co not in hierarchy[ro]['children'][mo]['children']: hierarchy[ro]['children'][mo]['children'][co] = {'wt': 0, 'pcs': 0, 'gross_wt': 0, 'net_wt': 0, 'stone_wt': 0, 'bc_wt': 0, 'children': {}}
        if cl not in hierarchy[ro]['children'][mo]['children'][co]['children']: hierarchy[ro]['children'][mo]['children'][co]['children'][cl] = {'wt': 0, 'pcs': 0, 'gross_wt': 0, 'net_wt': 0, 'stone_wt': 0, 'bc_wt': 0, 'children': []}
        
        hierarchy[ro]['wt'] += r['weight']
        hierarchy[ro]['pcs'] += r['pieces']
        hierarchy[ro]['gross_wt'] += r.get('gross_weight', 0)
        hierarchy[ro]['net_wt'] += r.get('net_weight', 0)
        hierarchy[ro]['stone_wt'] += r.get('stone_weight', 0)
        hierarchy[ro]['bc_wt'] += r.get('barcoded_weight', 0)
        
        hierarchy[ro]['children'][mo]['wt'] += r['weight']
        hierarchy[ro]['children'][mo]['pcs'] += r['pieces']
        hierarchy[ro]['children'][mo]['gross_wt'] += r.get('gross_weight', 0)
        hierarchy[ro]['children'][mo]['net_wt'] += r.get('net_weight', 0)
        hierarchy[ro]['children'][mo]['stone_wt'] += r.get('stone_weight', 0)
        hierarchy[ro]['children'][mo]['bc_wt'] += r.get('barcoded_weight', 0)

        hierarchy[ro]['children'][mo]['children'][co]['wt'] += r['weight']
        hierarchy[ro]['children'][mo]['children'][co]['pcs'] += r['pieces']
        hierarchy[ro]['children'][mo]['children'][co]['gross_wt'] += r.get('gross_weight', 0)
        hierarchy[ro]['children'][mo]['children'][co]['net_wt'] += r.get('net_weight', 0)
        hierarchy[ro]['children'][mo]['children'][co]['stone_wt'] += r.get('stone_weight', 0)
        hierarchy[ro]['children'][mo]['children'][co]['bc_wt'] += r.get('barcoded_weight', 0)

        hierarchy[ro]['children'][mo]['children'][co]['children'][cl]['wt'] += r['weight']
        hierarchy[ro]['children'][mo]['children'][co]['children'][cl]['pcs'] += r['pieces']
        hierarchy[ro]['children'][mo]['children'][co]['children'][cl]['gross_wt'] += r.get('gross_weight', 0)
        hierarchy[ro]['children'][mo]['children'][co]['children'][cl]['net_wt'] += r.get('net_weight', 0)
        hierarchy[ro]['children'][mo]['children'][co]['children'][cl]['stone_wt'] += r.get('stone_weight', 0)
        hierarchy[ro]['children'][mo]['children'][co]['children'][cl]['bc_wt'] += r.get('barcoded_weight', 0)
        
        hierarchy[ro]['children'][mo]['children'][co]['children'][cl]['children'].append(r)

    result = []
    for ro, ro_data in sorted(hierarchy.items()):
        ro_id = f"ro_{get_id(ro)}"
        result.append({'level': 1, 'id': ro_id, 'parent_id': None, 'label': ro, 'weight': ro_data['wt'], 'pieces': ro_data['pcs'], 'gross_weight': ro_data['gross_wt'], 'net_weight': ro_data['net_wt'], 'stone_weight': ro_data['stone_wt'], 'barcoded_weight': ro_data['bc_wt'], 'is_leaf': False})
        for mo, mo_data in sorted(ro_data['children'].items()):
            mo_id = f"mo_{get_id(ro, mo)}"
            result.append({'level': 2, 'id': mo_id, 'parent_id': ro_id, 'label': mo, 'weight': mo_data['wt'], 'pieces': mo_data['pcs'], 'gross_weight': mo_data['gross_wt'], 'net_weight': mo_data['net_wt'], 'stone_weight': mo_data['stone_wt'], 'barcoded_weight': mo_data['bc_wt'], 'is_leaf': False})
            for co, co_data in sorted(mo_data['children'].items()):
                co_id = f"co_{get_id(ro, mo, co)}"
                result.append({'level': 3, 'id': co_id, 'parent_id': mo_id, 'label': co, 'weight': co_data['wt'], 'pieces': co_data['pcs'], 'gross_weight': co_data['gross_wt'], 'net_weight': co_data['net_wt'], 'stone_weight': co_data['stone_wt'], 'barcoded_weight': co_data['bc_wt'], 'is_leaf': False})
                for cl, cl_data in sorted(co_data['children'].items()):
                    cl_id = f"cl_{get_id(ro, mo, co, cl)}"
                    result.append({'level': 4, 'id': cl_id, 'parent_id': co_id, 'label': cl, 'weight': cl_data['wt'], 'pieces': cl_data['pcs'], 'gross_weight': cl_data['gross_wt'], 'net_weight': cl_data['net_wt'], 'stone_weight': cl_data['stone_wt'], 'barcoded_weight': cl_data['bc_wt'], 'is_leaf': False})
                    for r in sorted(cl_data['children'], key=lambda x: x['party']):
                        result.append({
                            'level': 5, 'id': f"leaf_{get_id(ro, mo, co, cl, r['party'])}", 'parent_id': cl_id, 'label': r['party'],
                            'weight': r['weight'], 'pieces': r['pieces'], 'gross_weight': r.get('gross_weight', 0), 'net_weight': r.get('net_weight', 0), 'stone_weight': r.get('stone_weight', 0), 'barcoded_weight': r.get('barcoded_weight', 0), 'is_leaf': True,
                            'qc_ro': ro, 'make_owner': mo, 'collection_owner': co, 'collection': cl, 'party': r['party'],
                            'qc_issue_receipt_date': r['qc_issue_receipt_date'],
                            'qc_issue_receipt_no': r['qc_issue_receipt_no'],
                            'qc_completed_date': r['qc_completed_date'],
                            'feedback_text': r['feedback_text'], 'feedback_category': r['feedback_category'], 'feedback_username': r['feedback_username']
                        })
    return result

@dashboard_bp.route('/api/qc-completed-invoice/feedback', methods=['POST'])
@jwt_required()
@require_perm('report.view')
def save_qc_completed_invoice_feedback():
    data = request.json
    username = session.get('username', 'Unknown')
    feedback = QCCompletedInvoicePendingFeedback(
        qc_ro=data.get('qc_ro'),
        make_owner=data.get('make_owner'),
        collection_owner=data.get('collection_owner'),
        collection=data.get('collection'),
        party=data.get('party'),
        qc_issue_receipt_no=data.get('qc_issue_receipt_no'),
        feedback_text=data.get('feedback_text'),
        feedback_category=data.get('feedback_category'),
        username=username
    )
    db.session.add(feedback)
    db.session.commit()
    return jsonify({"status": "success"})

@dashboard_bp.route('/api/qc-completed-invoice/details')
@jwt_required()
@require_perm('report.view')
def get_qc_completed_invoice_details():
    qc_ro = request.args.get('qc_ro')
    make_owner = request.args.get('make_owner')
    collection_owner = request.args.get('collection_owner')
    collection = request.args.get('collection')
    party = request.args.get('party')
    
    latest_date = db.session.query(func.max(QCCompletedInvoicePendingSnapshot.snapshot_date)).scalar()
    pos = QCCompletedInvoicePendingSnapshot.query.filter(
        QCCompletedInvoicePendingSnapshot.snapshot_date == latest_date,
        QCCompletedInvoicePendingSnapshot.qc_ro == qc_ro,
        QCCompletedInvoicePendingSnapshot.make_owner == make_owner,
        QCCompletedInvoicePendingSnapshot.collection_owner == collection_owner,
        QCCompletedInvoicePendingSnapshot.collection == collection,
        QCCompletedInvoicePendingSnapshot.party == party
    ).order_by(QCCompletedInvoicePendingSnapshot.po_date.desc()).all()
    
    return render_template('partials/_qc_completed_invoice_pending_details_modal.html', pos=pos)

def get_invoice_completed_deliver_latest_feedback_subquery():
    subq = db.session.query(
        InvoiceCompletedPendingDeliverFeedback.order_branch,
        InvoiceCompletedPendingDeliverFeedback.make_owner,
        InvoiceCompletedPendingDeliverFeedback.collection_owner,
        InvoiceCompletedPendingDeliverFeedback.collection,
        InvoiceCompletedPendingDeliverFeedback.party,
        func.max(InvoiceCompletedPendingDeliverFeedback.id).label('max_id')
    ).group_by(
        InvoiceCompletedPendingDeliverFeedback.order_branch,
        InvoiceCompletedPendingDeliverFeedback.make_owner,
        InvoiceCompletedPendingDeliverFeedback.collection_owner,
        InvoiceCompletedPendingDeliverFeedback.collection,
        InvoiceCompletedPendingDeliverFeedback.party
    ).subquery()
    
    return db.session.query(InvoiceCompletedPendingDeliverFeedback).join(
        subq, InvoiceCompletedPendingDeliverFeedback.id == subq.c.max_id
    ).subquery('latest_fb')

def get_invoice_completed_deliver_hierarchical_rows(processed_rows):
    hierarchy = {}
    def get_id(*args): return "_".join(str(a).replace(" ", "_").replace("&", "_") for a in args)
    
    for r in processed_rows:
        ro = r['order_branch'] or 'Unknown RO'
        mo = r['make_owner'] or 'Unknown MO'
        co = r['collection_owner'] or 'Unknown CO'
        cl = r['collection'] or 'Unknown Coll'
        
        if ro not in hierarchy: hierarchy[ro] = {'wt': 0, 'pcs': 0, 'gross_wt': 0, 'net_wt': 0, 'stone_wt': 0, 'children': {}}
        if mo not in hierarchy[ro]['children']: hierarchy[ro]['children'][mo] = {'wt': 0, 'pcs': 0, 'gross_wt': 0, 'net_wt': 0, 'stone_wt': 0, 'children': {}}
        if co not in hierarchy[ro]['children'][mo]['children']: hierarchy[ro]['children'][mo]['children'][co] = {'wt': 0, 'pcs': 0, 'gross_wt': 0, 'net_wt': 0, 'stone_wt': 0, 'children': {}}
        if cl not in hierarchy[ro]['children'][mo]['children'][co]['children']: hierarchy[ro]['children'][mo]['children'][co]['children'][cl] = {'wt': 0, 'pcs': 0, 'gross_wt': 0, 'net_wt': 0, 'stone_wt': 0, 'children': []}
        
        hierarchy[ro]['wt'] += r['weight']
        hierarchy[ro]['pcs'] += r['pieces']
        hierarchy[ro]['gross_wt'] += r.get('gross_weight', 0)
        hierarchy[ro]['net_wt'] += r.get('net_weight', 0)
        hierarchy[ro]['stone_wt'] += r.get('stone_weight', 0)
        
        hierarchy[ro]['children'][mo]['wt'] += r['weight']
        hierarchy[ro]['children'][mo]['pcs'] += r['pieces']
        hierarchy[ro]['children'][mo]['gross_wt'] += r.get('gross_weight', 0)
        hierarchy[ro]['children'][mo]['net_wt'] += r.get('net_weight', 0)
        hierarchy[ro]['children'][mo]['stone_wt'] += r.get('stone_weight', 0)

        hierarchy[ro]['children'][mo]['children'][co]['wt'] += r['weight']
        hierarchy[ro]['children'][mo]['children'][co]['pcs'] += r['pieces']
        hierarchy[ro]['children'][mo]['children'][co]['gross_wt'] += r.get('gross_weight', 0)
        hierarchy[ro]['children'][mo]['children'][co]['net_wt'] += r.get('net_weight', 0)
        hierarchy[ro]['children'][mo]['children'][co]['stone_wt'] += r.get('stone_weight', 0)

        hierarchy[ro]['children'][mo]['children'][co]['children'][cl]['wt'] += r['weight']
        hierarchy[ro]['children'][mo]['children'][co]['children'][cl]['pcs'] += r['pieces']
        hierarchy[ro]['children'][mo]['children'][co]['children'][cl]['gross_wt'] += r.get('gross_weight', 0)
        hierarchy[ro]['children'][mo]['children'][co]['children'][cl]['net_wt'] += r.get('net_weight', 0)
        hierarchy[ro]['children'][mo]['children'][co]['children'][cl]['stone_wt'] += r.get('stone_weight', 0)
        
        hierarchy[ro]['children'][mo]['children'][co]['children'][cl]['children'].append(r)

    result = []
    for ro, ro_data in sorted(hierarchy.items()):
        ro_id = f"ro_{get_id(ro)}"
        result.append({'level': 1, 'id': ro_id, 'parent_id': None, 'label': ro, 'weight': ro_data['wt'], 'pieces': ro_data['pcs'], 'gross_weight': ro_data['gross_wt'], 'net_weight': ro_data['net_wt'], 'stone_weight': ro_data['stone_wt'], 'is_leaf': False})
        for mo, mo_data in sorted(ro_data['children'].items()):
            mo_id = f"mo_{get_id(ro, mo)}"
            result.append({'level': 2, 'id': mo_id, 'parent_id': ro_id, 'label': mo, 'weight': mo_data['wt'], 'pieces': mo_data['pcs'], 'gross_weight': mo_data['gross_wt'], 'net_weight': mo_data['net_wt'], 'stone_weight': mo_data['stone_wt'], 'is_leaf': False})
            for co, co_data in sorted(mo_data['children'].items()):
                co_id = f"co_{get_id(ro, mo, co)}"
                result.append({'level': 3, 'id': co_id, 'parent_id': mo_id, 'label': co, 'weight': co_data['wt'], 'pieces': co_data['pcs'], 'gross_weight': co_data['gross_wt'], 'net_weight': co_data['net_wt'], 'stone_weight': co_data['stone_wt'], 'is_leaf': False})
                for cl, cl_data in sorted(co_data['children'].items()):
                    cl_id = f"cl_{get_id(ro, mo, co, cl)}"
                    result.append({'level': 4, 'id': cl_id, 'parent_id': co_id, 'label': cl, 'weight': cl_data['wt'], 'pieces': cl_data['pcs'], 'gross_weight': cl_data['gross_wt'], 'net_weight': cl_data['net_wt'], 'stone_weight': cl_data['stone_wt'], 'is_leaf': False})
                    for r in sorted(cl_data['children'], key=lambda x: x['party']):
                        result.append({
                            'level': 5, 'id': f"leaf_{get_id(ro, mo, co, cl, r['party'])}", 'parent_id': cl_id, 'label': r['party'],
                            'weight': r['weight'], 'pieces': r['pieces'], 'gross_weight': r.get('gross_weight', 0), 'net_weight': r.get('net_weight', 0), 'stone_weight': r.get('stone_weight', 0), 'is_leaf': True,
                            'order_branch': ro, 'make_owner': mo, 'collection_owner': co, 'collection': cl, 'party': r['party'],
                            'invoice_no': r['invoice_no'],
                            'invoice_date': r['invoice_date'],
                            'invoice_amount': r['invoice_amount'],
                            'feedback_text': r['feedback_text'], 'feedback_category': r['feedback_category'], 'feedback_username': r['feedback_username']
                        })
    return result

@dashboard_bp.route('/api/invoice-completed-deliver/feedback', methods=['POST'])
@jwt_required()
@require_perm('report.view')
def save_invoice_completed_deliver_feedback():
    data = request.json
    username = session.get('username', 'Unknown')
    feedback = InvoiceCompletedPendingDeliverFeedback(
        order_branch=data.get('order_branch'),
        make_owner=data.get('make_owner'),
        collection_owner=data.get('collection_owner'),
        collection=data.get('collection'),
        party=data.get('party'),
        feedback_text=data.get('feedback_text'),
        feedback_category=data.get('feedback_category'),
        username=username
    )
    db.session.add(feedback)
    db.session.commit()
    return jsonify({"status": "success"})

@dashboard_bp.route('/api/invoice-completed-deliver/details')
@jwt_required()
@require_perm('report.view')
def get_invoice_completed_deliver_details():
    order_branch = request.args.get('order_branch')
    make_owner = request.args.get('make_owner')
    collection_owner = request.args.get('collection_owner')
    collection = request.args.get('collection')
    party = request.args.get('party')
    
    latest_date = db.session.query(func.max(InvoiceCompletedPendingDeliverSnapshot.snapshot_date)).scalar()
    pos = InvoiceCompletedPendingDeliverSnapshot.query.filter(
        InvoiceCompletedPendingDeliverSnapshot.snapshot_date == latest_date,
        InvoiceCompletedPendingDeliverSnapshot.order_branch == order_branch,
        InvoiceCompletedPendingDeliverSnapshot.make_owner == make_owner,
        InvoiceCompletedPendingDeliverSnapshot.collection_owner == collection_owner,
        InvoiceCompletedPendingDeliverSnapshot.collection == collection,
        InvoiceCompletedPendingDeliverSnapshot.party == party
    ).order_by(InvoiceCompletedPendingDeliverSnapshot.po_date.desc()).all()
    
    return render_template('partials/_invoice_completed_pending_deliver_details_modal.html', pos=pos)
