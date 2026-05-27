from flask import render_template, request, jsonify, session
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.dashboard import dashboard_bp
from app.models.snapshots import (
    QCDelayManagementSnapshot, 
    QCDelayManagementFeedback,
    SupplierQCIssueReceiptPendingSnapshot,
    QCReceiptCompletedQCPendingSnapshot,
    QCCompletedInvoiceRequestPendingSnapshot
)
from app.models.auth import User
from app.extensions import db, redis_client
from sqlalchemy import func, case, or_
from datetime import datetime
from zoneinfo import ZoneInfo
import logging
import json
from app.utils.decorators import require_perm

logger = logging.getLogger(__name__)

@dashboard_bp.route('/qc-delay-management')
@jwt_required()
def qc_delay_management():
    # Sync time
    sync_time = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%I:%M %p")
    
    # Get filters
    search = request.args.get('search', '')
    office = request.args.get('office', '')
    # Get latest snapshot date
    latest_date = db.session.query(func.max(QCDelayManagementSnapshot.snapshot_date)).scalar()
    
    roles = [r.upper() for r in session.get('roles', [])]
    is_admin = 'ADMIN' in roles
    is_manager_2 = 'MANAGER_2' in roles

    # Get unique offices for filter
    offices_query = db.session.query(QCDelayManagementSnapshot.qc_ro).distinct()
    if latest_date:
        offices_query = offices_query.filter(QCDelayManagementSnapshot.snapshot_date == latest_date)
    if not is_admin and not is_manager_2:
        if 'MANAGER_KMU' in roles:
            offices_query = offices_query.filter(QCDelayManagementSnapshot.make.in_([
                'KMU - KERALA', 'KMU 999 COIN', 'KMU B2B', 'KMU KARNATAKA', 
                'KMU MH', 'KMU-COIN', 'KMU-TN'
            ]))
        elif session.get('username'):
            u = session.get('username').strip().lower()
            offices_query = offices_query.filter(func.lower(func.trim(QCDelayManagementSnapshot.make_owner)) == u)
    offices = [o[0] for o in offices_query.all() if o[0]]

    # Get unique makes for filter
    makes_query = db.session.query(QCDelayManagementSnapshot.make).distinct()
    if latest_date:
        makes_query = makes_query.filter(QCDelayManagementSnapshot.snapshot_date == latest_date)
    if not is_admin and not is_manager_2:
        if 'MANAGER_KMU' in roles:
            makes_query = makes_query.filter(QCDelayManagementSnapshot.make.in_([
                'KMU - KERALA', 'KMU 999 COIN', 'KMU B2B', 'KMU KARNATAKA', 
                'KMU MH', 'KMU-COIN', 'KMU-TN'
            ]))
        elif session.get('username'):
            u = session.get('username').strip().lower()
            makes_query = makes_query.filter(func.lower(func.trim(QCDelayManagementSnapshot.make_owner)) == u)
    makes = [m[0] for m in makes_query.all() if m[0]]

    # Get unique parties for filter
    parties_query = db.session.query(QCDelayManagementSnapshot.party).distinct()
    if latest_date:
        parties_query = parties_query.filter(QCDelayManagementSnapshot.snapshot_date == latest_date)
    if not is_admin and not is_manager_2:
        if 'MANAGER_KMU' in roles:
            parties_query = parties_query.filter(QCDelayManagementSnapshot.make.in_([
                'KMU - KERALA', 'KMU 999 COIN', 'KMU B2B', 'KMU KARNATAKA', 
                'KMU MH', 'KMU-COIN', 'KMU-TN'
            ]))
        elif session.get('username'):
            u = session.get('username').strip().lower()
            parties_query = parties_query.filter(func.lower(func.trim(QCDelayManagementSnapshot.make_owner)) == u)
    parties = [p[0] for p in parties_query.all() if p[0]]

    return render_template(
        'qc_delay_management.html',
        offices=sorted(offices),
        makes=sorted(makes),
        parties=sorted(parties),
        sync_time=sync_time,
        current_username=session.get('username'),
        initial_load=True
    )

@dashboard_bp.route('/partial/qc-delay-management-report')
@jwt_required()
def partial_qc_delay_management_report():
    search = request.args.get('search', '')
    office = request.args.get('office', '')
    
    # Parse multiselect lists
    make_filter = request.args.get('make', '')
    makes_selected = [m.strip() for m in make_filter.split(',') if m.strip()]
    
    party_filter = request.args.get('party', '')
    parties_selected = [p.strip() for p in party_filter.split(',') if p.strip()]
    
    # Days delay filters
    delay_s1 = request.args.get('delay_s1', type=int)
    delay_s2 = request.args.get('delay_s2', type=int)
    delay_s3 = request.args.get('delay_s3', type=int)

    # Sort params
    sort_by = request.args.get('sort_by', '')
    sort_dir = request.args.get('sort_dir', 'desc')
    
    # Determine grouping (always False now so we always group by qc_ro)
    group_by_party = False
        
    latest_date = db.session.query(func.max(QCDelayManagementSnapshot.snapshot_date)).scalar()
    
    # Subquery helper for latest feedback
    def get_latest_feedback_subq(segment_id):
        subq = db.session.query(
            QCDelayManagementFeedback.qc_ro,
            func.max(QCDelayManagementFeedback.created_at).label('max_date')
        ).filter(QCDelayManagementFeedback.segment_id == segment_id).group_by(
            QCDelayManagementFeedback.qc_ro
        ).subquery()
        
        return db.session.query(QCDelayManagementFeedback).join(
            subq,
            db.and_(
                QCDelayManagementFeedback.qc_ro == subq.c.qc_ro,
                QCDelayManagementFeedback.created_at == subq.c.max_date
            )
        ).filter(QCDelayManagementFeedback.segment_id == segment_id).subquery()

    f1_subq = get_latest_feedback_subq(1)
    f2_subq = get_latest_feedback_subq(2)
    f3_subq = get_latest_feedback_subq(3)

    # Dynamic delayed columns
    current_date = func.current_date()
    
    # Segment 1 Delayed
    if delay_s1 is not None:
        s1_cond = (current_date - func.date(QCDelayManagementSnapshot.qc_issue_completed_date)) >= delay_s1
        s1_del_pcs = func.sum(case((s1_cond, QCDelayManagementSnapshot.qc_issue_completed_receipt_pending_piece), else_=0))
        s1_del_wt = func.sum(case((s1_cond, QCDelayManagementSnapshot.qc_issue_completed_receipt_pending_weight), else_=0))
    else:
        s1_del_pcs = func.sum(QCDelayManagementSnapshot.delayed_qc_issue_completed_receipt_pending_piece)
        s1_del_wt = func.sum(QCDelayManagementSnapshot.delayed_qc_issue_completed_receipt_pending_weight)
        
    # Segment 2 Delayed
    if delay_s2 is not None:
        s2_cond = (current_date - func.date(QCDelayManagementSnapshot.qc_receipt_completed_date)) >= delay_s2
        s2_del_pcs = func.sum(case((s2_cond, QCDelayManagementSnapshot.qc_receipt_completed_qc_pending_piece), else_=0))
        s2_del_wt = func.sum(case((s2_cond, QCDelayManagementSnapshot.qc_receipt_completed_qc_pending_weight), else_=0))
    else:
        s2_del_pcs = func.sum(QCDelayManagementSnapshot.delayed_qc_receipt_completed_qc_pending_piece)
        s2_del_wt = func.sum(QCDelayManagementSnapshot.delayed_qc_receipt_completed_qc_pending_weight)
        
    # Segment 3 Delayed
    if delay_s3 is not None:
        s3_cond = (current_date - func.date(QCDelayManagementSnapshot.qc_completed_date)) >= delay_s3
        s3_del_pcs = func.sum(case((s3_cond, QCDelayManagementSnapshot.qc_completed_invoice_request_pending_piece), else_=0))
        s3_del_wt = func.sum(case((s3_cond, QCDelayManagementSnapshot.qc_completed_invoice_request_pending_weight), else_=0))
    else:
        s3_del_pcs = func.sum(QCDelayManagementSnapshot.delayed_qc_completed_invoice_request_pending_piece)
        s3_del_wt = func.sum(QCDelayManagementSnapshot.delayed_qc_completed_invoice_request_pending_weight)

    # Base selection
    if group_by_party:
        selection = [
            QCDelayManagementSnapshot.party.label('party'),
            func.max(QCDelayManagementSnapshot.qc_ro).label('qc_ro'),
            func.max(QCDelayManagementSnapshot.qc_ro_code).label('qc_ro_code'),
            func.max(QCDelayManagementSnapshot.qc_ro_incharge).label('qc_ro_incharge'),
            func.max(QCDelayManagementSnapshot.qc_ro_incharge_email).label('qc_ro_incharge_email'),
            func.max(QCDelayManagementSnapshot.qc_ro_incharge_phone_number).label('qc_ro_incharge_phone_number'),
            func.max(QCDelayManagementSnapshot.qc_ro_address).label('qc_ro_address'),
        ]
        join_col = QCDelayManagementSnapshot.party
    else:
        selection = [
            func.max(QCDelayManagementSnapshot.party).label('party'),
            QCDelayManagementSnapshot.qc_ro.label('qc_ro'),
            func.max(QCDelayManagementSnapshot.qc_ro_code).label('qc_ro_code'),
            func.max(QCDelayManagementSnapshot.qc_ro_incharge).label('qc_ro_incharge'),
            func.max(QCDelayManagementSnapshot.qc_ro_incharge_email).label('qc_ro_incharge_email'),
            func.max(QCDelayManagementSnapshot.qc_ro_incharge_phone_number).label('qc_ro_incharge_phone_number'),
            func.max(QCDelayManagementSnapshot.qc_ro_address).label('qc_ro_address'),
        ]
        join_col = QCDelayManagementSnapshot.qc_ro

    # Build query
    query = db.session.query(
        *selection,
        func.sum(QCDelayManagementSnapshot.qc_issue_completed_receipt_pending_piece).label('qc_issue_completed_receipt_pending_piece'),
        func.sum(QCDelayManagementSnapshot.qc_issue_completed_receipt_pending_weight).label('qc_issue_completed_receipt_pending_weight'),
        func.sum(QCDelayManagementSnapshot.qc_receipt_completed_qc_pending_piece).label('qc_receipt_completed_qc_pending_piece'),
        func.sum(QCDelayManagementSnapshot.qc_receipt_completed_qc_pending_weight).label('qc_receipt_completed_qc_pending_weight'),
        func.sum(QCDelayManagementSnapshot.qc_completed_invoice_request_pending_piece).label('qc_completed_invoice_request_pending_piece'),
        func.sum(QCDelayManagementSnapshot.qc_completed_invoice_request_pending_weight).label('qc_completed_invoice_request_pending_weight'),
        
        s1_del_pcs.label('delayed_qc_issue_completed_receipt_pending_piece'),
        s1_del_wt.label('delayed_qc_issue_completed_receipt_pending_weight'),
        s2_del_pcs.label('delayed_qc_receipt_completed_qc_pending_piece'),
        s2_del_wt.label('delayed_qc_receipt_completed_qc_pending_weight'),
        s3_del_pcs.label('delayed_qc_completed_invoice_request_pending_piece'),
        s3_del_wt.label('delayed_qc_completed_invoice_request_pending_weight'),
        
        func.max(f1_subq.c.feedback_text).label('f1_text'),
        func.max(f1_subq.c.feedback_category).label('f1_category'),
        func.max(f1_subq.c.username).label('f1_username'),
        func.max(f1_subq.c.created_at).label('f1_date'),
        
        func.max(f2_subq.c.feedback_text).label('f2_text'),
        func.max(f2_subq.c.feedback_category).label('f2_category'),
        func.max(f2_subq.c.username).label('f2_username'),
        func.max(f2_subq.c.created_at).label('f2_date'),
        
        func.max(f3_subq.c.feedback_text).label('f3_text'),
        func.max(f3_subq.c.feedback_category).label('f3_category'),
        func.max(f3_subq.c.username).label('f3_username'),
        func.max(f3_subq.c.created_at).label('f3_date')
    ).outerjoin(f1_subq, join_col == f1_subq.c.qc_ro)\
     .outerjoin(f2_subq, join_col == f2_subq.c.qc_ro)\
     .outerjoin(f3_subq, join_col == f3_subq.c.qc_ro)

    if latest_date:
        query = query.filter(QCDelayManagementSnapshot.snapshot_date == latest_date)
    
    if search:
        query = query.filter(
            db.or_(
                QCDelayManagementSnapshot.party.ilike(f"%{search}%"),
                QCDelayManagementSnapshot.qc_ro.ilike(f"%{search}%")
            )
        )
    
    if office:
        query = query.filter(QCDelayManagementSnapshot.qc_ro == office)
        
    if makes_selected:
        query = query.filter(QCDelayManagementSnapshot.make.in_(makes_selected))
        
    if parties_selected:
        query = query.filter(QCDelayManagementSnapshot.party.in_(parties_selected))

    # Apply user-based filtering
    roles = [r.upper() for r in session.get('roles', [])]
    is_admin = 'ADMIN' in roles
    is_manager_2 = 'MANAGER_2' in roles
    if not is_admin and not is_manager_2:
        if 'MANAGER_KMU' in roles:
            query = query.filter(QCDelayManagementSnapshot.make.in_([
                'KMU - KERALA', 'KMU 999 COIN', 'KMU B2B', 'KMU KARNATAKA', 
                'KMU MH', 'KMU-COIN', 'KMU-TN'
            ]))
        elif session.get('username'):
            u = session.get('username').strip().lower()
            query = query.filter(func.lower(func.trim(QCDelayManagementSnapshot.make_owner)) == u)

    # Group by
    if group_by_party:
        query = query.group_by(QCDelayManagementSnapshot.party)
    else:
        query = query.group_by(QCDelayManagementSnapshot.qc_ro)

    # Sort order — map sort_by key to aggregated column expression
    sort_col_map = {
        's1_wt': func.sum(QCDelayManagementSnapshot.qc_issue_completed_receipt_pending_weight),
        's2_wt': func.sum(QCDelayManagementSnapshot.qc_receipt_completed_qc_pending_weight),
        's3_wt': func.sum(QCDelayManagementSnapshot.qc_completed_invoice_request_pending_weight),
    }
    if sort_by in sort_col_map:
        col_expr = sort_col_map[sort_by]
        query = query.order_by(col_expr.desc() if sort_dir == 'desc' else col_expr.asc())
    else:
        # Default: alphabetical by office name
        if group_by_party:
            query = query.order_by(QCDelayManagementSnapshot.party)
        else:
            query = query.order_by(QCDelayManagementSnapshot.qc_ro)

    rows = query.all()
    
    processed_rows = []
    for r in rows:
        summary_dict = {
            'party': r.party,
            'qc_ro': r.qc_ro,
            'qc_ro_code': r.qc_ro_code,
            'qc_ro_incharge': r.qc_ro_incharge,
            'qc_ro_incharge_email': r.qc_ro_incharge_email,
            'qc_ro_incharge_phone_number': r.qc_ro_incharge_phone_number,
            'qc_ro_address': r.qc_ro_address,
            'qc_issue_completed_receipt_pending_piece': r.qc_issue_completed_receipt_pending_piece or 0,
            'qc_issue_completed_receipt_pending_weight': float(r.qc_issue_completed_receipt_pending_weight or 0),
            'delayed_qc_issue_completed_receipt_pending_piece': r.delayed_qc_issue_completed_receipt_pending_piece or 0,
            'delayed_qc_issue_completed_receipt_pending_weight': float(r.delayed_qc_issue_completed_receipt_pending_weight or 0),
            'qc_receipt_completed_qc_pending_piece': r.qc_receipt_completed_qc_pending_piece or 0,
            'qc_receipt_completed_qc_pending_weight': float(r.qc_receipt_completed_qc_pending_weight or 0),
            'delayed_qc_receipt_completed_qc_pending_piece': r.delayed_qc_receipt_completed_qc_pending_piece or 0,
            'delayed_qc_receipt_completed_qc_pending_weight': float(r.delayed_qc_receipt_completed_qc_pending_weight or 0),
            'qc_completed_invoice_request_pending_piece': r.qc_completed_invoice_request_pending_piece or 0,
            'qc_completed_invoice_request_pending_weight': float(r.qc_completed_invoice_request_pending_weight or 0),
            'delayed_qc_completed_invoice_request_pending_piece': r.delayed_qc_completed_invoice_request_pending_piece or 0,
            'delayed_qc_completed_invoice_request_pending_weight': float(r.delayed_qc_completed_invoice_request_pending_weight or 0),
        }
        processed_rows.append({
            'summary': summary_dict,
            'feedbacks': {
                'segment1': {'feedback_text': r.f1_text, 'category': r.f1_category, 'username': r.f1_username, 'date': r.f1_date.strftime("%Y-%m-%d %H:%M") if r.f1_date else ''},
                'segment2': {'feedback_text': r.f2_text, 'category': r.f2_category, 'username': r.f2_username, 'date': r.f2_date.strftime("%Y-%m-%d %H:%M") if r.f2_date else ''},
                'segment3': {'feedback_text': r.f3_text, 'category': r.f3_category, 'username': r.f3_username, 'date': r.f3_date.strftime("%Y-%m-%d %H:%M") if r.f3_date else ''},
            }
        })

    return render_template(
        'partials/_view_qc_delay_management.html',
        rows=processed_rows,
        group_by_party=group_by_party,
        sort_by=sort_by,
        sort_dir=sort_dir
    )

@dashboard_bp.route('/api/qc-delay-management/feedback', methods=['POST'])
@jwt_required()
def save_qc_delay_feedback():
    data = request.json
    qc_ro = data.get('qc_ro')
    segment_id = data.get('segment_id')
    feedback_text = data.get('feedback_text')
    category = data.get('category')
    username = session.get('username')

    if not all([qc_ro, segment_id, feedback_text]):
        return jsonify({"status": "error", "message": "Missing required fields"}), 400

    feedback = QCDelayManagementFeedback(
        qc_ro=qc_ro,
        segment_id=segment_id,
        feedback_text=feedback_text,
        feedback_category=category,
        username=username
    )
    db.session.add(feedback)
    db.session.commit()

    return jsonify({"status": "success", "message": "Feedback saved successfully"})

@dashboard_bp.route('/api/qc-delay-management/details/<int:segment_id>')
@jwt_required()
def get_qc_delay_details(segment_id):
    qc_ro = request.args.get('qc_ro')
    party = request.args.get('party')
    make = request.args.get('make')
    delay = request.args.get('delay', type=int)
    
    if segment_id == 1:
        model = SupplierQCIssueReceiptPendingSnapshot
    elif segment_id == 2:
        model = QCReceiptCompletedQCPendingSnapshot
    elif segment_id == 3:
        model = QCCompletedInvoiceRequestPendingSnapshot
    else:
        return jsonify({"status": "error", "message": "Invalid segment"}), 400

    query = model.query
    if qc_ro:
        query = query.filter(model.qc_ro == qc_ro)
        
    if party:
        parties_list = [p.strip() for p in party.split(',') if p.strip()]
        if parties_list:
            query = query.filter(model.party.in_(parties_list))
            
    if make:
        makes_list = [m.strip() for m in make.split(',') if m.strip()]
        if makes_list:
            if hasattr(model, 'make'):
                query = query.filter(model.make.in_(makes_list))
            elif hasattr(model, 'make_owner'):
                query = query.filter(model.make_owner.in_(makes_list))
        
    # Get latest date for the detail model
    latest_date = db.session.query(func.max(model.snapshot_date)).scalar()
    if latest_date:
        query = query.filter(model.snapshot_date == latest_date)
        
    if delay is not None:
        if segment_id == 1:
            query = query.filter((func.current_date() - func.date(model.qc_issue_receipt_date)) >= delay)
        elif segment_id == 2:
            query = query.filter((func.current_date() - func.date(model.receipt_date)) >= delay)
        elif segment_id == 3:
            query = query.filter((func.current_date() - func.date(model.qc_completed_date)) >= delay)

    # Apply user-based filtering
    roles = [r.upper() for r in session.get('roles', [])]
    is_admin = 'ADMIN' in roles
    is_manager_2 = 'MANAGER_2' in roles
    if not is_admin and not is_manager_2:
        if 'MANAGER_KMU' in roles:
            query = query.filter(model.make.in_([
                'KMU - KERALA', 'KMU 999 COIN', 'KMU B2B', 'KMU KARNATAKA', 
                'KMU MH', 'KMU-COIN', 'KMU-TN'
            ]))
        elif session.get('username'):
            u = session.get('username').strip().lower()
            conds = []
            if hasattr(model, 'make_owner'):
                conds.append(func.lower(func.trim(model.make_owner)) == u)
            if hasattr(model, 'collection_owner'):
                conds.append(func.lower(func.trim(model.collection_owner)) == u)
            if hasattr(model, 'classification_owner'):
                conds.append(func.lower(func.trim(model.classification_owner)) == u)
            if conds:
                query = query.filter(or_(*conds))

    rows = query.all()
    return jsonify([r.to_dict() for r in rows])

@dashboard_bp.route('/api/qc-delay-management/feedback-info')
@jwt_required()
def get_feedback_info():
    qc_ro = request.args.get('qc_ro')
    segment_id = request.args.get('segment_id', type=int)
    
    feedback = QCDelayManagementFeedback.query.filter_by(
        qc_ro=qc_ro, 
        segment_id=segment_id
    ).order_by(QCDelayManagementFeedback.created_at.desc()).first()
    
    if not feedback:
        return jsonify({"status": "error", "message": "No feedback found"}), 404
        
    return jsonify({
        "status": "success",
        "data": {
            "username": feedback.username,
            "date": feedback.created_at.strftime("%Y-%m-%d %H:%M"),
            "category": feedback.feedback_category,
            "text": feedback.feedback_text
        }
    })
