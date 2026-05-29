from flask import render_template, request, jsonify, session
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.dashboard import dashboard_bp
from app.models.snapshots import (
    PartyDelayManagementSnapshot, 
    PartyDelayManagementFeedback,
    PartyAcceptPendingSnapshot,
    PartyProcessPendingSnapshot,
    PartyBarcodePendingSnapshot,
    PartyBarcodeCompletedBISRequestPendingSnapshot,
    PartyBISRequestCompletedHMIssuePendingSnapshot,
    PartyHMReceiptCompletedQCIssuePendingSnapshot,
    PartyInvoiceGeneratedInvoiceApprovePendingSnapshot,
    PartyInvoiceApprovedNotSynchedToMuzirisSnapshot
)
from app.models.auth import User
from app.extensions import db, redis_client
from sqlalchemy import func, case, or_, and_
from datetime import datetime
from zoneinfo import ZoneInfo
import logging
import json
from app.utils.decorators import require_perm

logger = logging.getLogger(__name__)

@dashboard_bp.route('/party-delay-management')
@jwt_required()
def party_delay_management():
    # Sync time
    sync_time = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%I:%M %p")
    
    # Get filters
    search = request.args.get('search', '')
    party_filter = request.args.get('party', '')
    
    # Get latest snapshot date
    latest_date = db.session.query(func.max(PartyDelayManagementSnapshot.snapshot_date)).scalar()
    
    # Get unique parties for filter
    parties_query = db.session.query(PartyDelayManagementSnapshot.party).distinct()
    if latest_date:
        parties_query = parties_query.filter(PartyDelayManagementSnapshot.snapshot_date == latest_date)
    
    roles = [r.upper() for r in session.get('roles', [])]
    is_admin = 'ADMIN' in roles
    is_manager_2 = 'MANAGER_2' in roles or 'MANAGER-BIC' in roles
    if not is_admin and not is_manager_2:
        if 'MANAGER_KMU' in roles:
            parties_query = parties_query.filter(PartyDelayManagementSnapshot.make.in_([
                'KMU - KERALA', 'KMU 999 COIN', 'KMU B2B', 'KMU KARNATAKA', 
                'KMU MH', 'KMU-COIN', 'KMU-TN'
            ]))
        elif session.get('username'):
            u = session.get('username').strip().lower()
            parties_query = parties_query.filter(func.lower(func.trim(PartyDelayManagementSnapshot.make_owner)) == u)
            
    parties = [p[0] for p in parties_query.all() if p[0]]

    # Get unique makes for filter
    makes_query = db.session.query(PartyDelayManagementSnapshot.make).distinct()
    if latest_date:
        makes_query = makes_query.filter(PartyDelayManagementSnapshot.snapshot_date == latest_date)
    
    if not is_admin and not is_manager_2:
        if 'MANAGER_KMU' in roles:
            makes_query = makes_query.filter(PartyDelayManagementSnapshot.make.in_([
                'KMU - KERALA', 'KMU 999 COIN', 'KMU B2B', 'KMU KARNATAKA', 
                'KMU MH', 'KMU-COIN', 'KMU-TN'
            ]))
        elif session.get('username'):
            u = session.get('username').strip().lower()
            makes_query = makes_query.filter(func.lower(func.trim(PartyDelayManagementSnapshot.make_owner)) == u)
            
    makes = [m[0] for m in makes_query.all() if m[0]]

    return render_template(
        'party_delay_management.html',
        parties=sorted(parties),
        makes=sorted(makes),
        sync_time=sync_time,
        current_username=session.get('username'),
        initial_load=True
    )

@dashboard_bp.route('/partial/party-delay-management-report')
@jwt_required()
def partial_party_delay_management_report():
    search = request.args.get('search', '')
    party_filter = request.args.get('party', '')
    
    # Parse multiselect lists for make
    make_filter = request.args.get('make', '')
    makes_selected = [m.strip() for m in make_filter.split(',') if m.strip()]
    
    feedback_filter = request.args.get('feedback', '')
    
    # Get latest snapshot date
    latest_date = db.session.query(func.max(PartyDelayManagementSnapshot.snapshot_date)).scalar()
    
    # Subquery helper for latest feedback
    def get_latest_feedback_subq(segment_id):
        subq = db.session.query(
            PartyDelayManagementFeedback.party,
            func.max(PartyDelayManagementFeedback.created_at).label('max_date')
        ).filter(PartyDelayManagementFeedback.segment_id == segment_id).group_by(
            PartyDelayManagementFeedback.party
        ).subquery()
        
        return db.session.query(PartyDelayManagementFeedback).join(
            subq,
            db.and_(
                PartyDelayManagementFeedback.party == subq.c.party,
                PartyDelayManagementFeedback.created_at == subq.c.max_date
            )
        ).filter(PartyDelayManagementFeedback.segment_id == segment_id).subquery()

    f_subqs = [get_latest_feedback_subq(i) for i in range(1, 9)]

    # Days delay filters
    delay_s1 = request.args.get('delay_s1', type=int)
    delay_s2 = request.args.get('delay_s2', type=int)
    delay_s3 = request.args.get('delay_s3', type=int)
    delay_s4 = request.args.get('delay_s4', type=int)
    delay_s5 = request.args.get('delay_s5', type=int)
    delay_s6 = request.args.get('delay_s6', type=int)
    delay_s7 = request.args.get('delay_s7', type=int)
    delay_s8 = request.args.get('delay_s8', type=int)

    current_date = func.current_date()

    # Dynamic delayed columns
    # Segment 1 Delayed
    if delay_s1 is not None:
        s1_cond = (current_date - func.date(PartyDelayManagementSnapshot.order_date)) >= delay_s1
        s1_pcs = func.sum(case((s1_cond, PartyDelayManagementSnapshot.invited_pending_orders), else_=0))
        s1_wt = func.sum(case((s1_cond, PartyDelayManagementSnapshot.invited_pending_weight), else_=0))
    else:
        s1_pcs = func.sum(PartyDelayManagementSnapshot.invited_pending_orders)
        s1_wt = func.sum(PartyDelayManagementSnapshot.invited_pending_weight)

    # Segment 2 Delayed
    if delay_s2 is not None:
        s2_cond = (current_date - func.date(PartyDelayManagementSnapshot.accepted_date)) >= delay_s2
        s2_pcs = func.sum(case((s2_cond, PartyDelayManagementSnapshot.process_pending_orders), else_=0))
        s2_wt = func.sum(case((s2_cond, PartyDelayManagementSnapshot.process_pending_weight), else_=0))
    else:
        s2_pcs = func.sum(PartyDelayManagementSnapshot.process_pending_orders)
        s2_wt = func.sum(PartyDelayManagementSnapshot.process_pending_weight)

    # Segment 3 Delayed
    if delay_s3 is not None:
        s3_cond = (current_date - func.date(PartyDelayManagementSnapshot.accepted_date)) >= delay_s3
        s3_pcs = func.sum(case((s3_cond, PartyDelayManagementSnapshot.process_completed_barcode_pending_orders), else_=0))
        s3_wt = func.sum(case((s3_cond, PartyDelayManagementSnapshot.process_completed_barcode_pending_weight), else_=0))
    else:
        s3_pcs = func.sum(PartyDelayManagementSnapshot.process_completed_barcode_pending_orders)
        s3_wt = func.sum(PartyDelayManagementSnapshot.process_completed_barcode_pending_weight)

    # Segment 4 Delayed
    if delay_s4 is not None:
        s4_cond = (current_date - func.date(PartyDelayManagementSnapshot.barcoded_completed_date)) >= delay_s4
        s4_pcs = func.sum(case((s4_cond, PartyDelayManagementSnapshot.barcode_completed_bis_request_pending_orders), else_=0))
        s4_wt = func.sum(case((s4_cond, PartyDelayManagementSnapshot.barcode_completed_bis_request_pending_weight), else_=0))
    else:
        s4_pcs = func.sum(PartyDelayManagementSnapshot.barcode_completed_bis_request_pending_orders)
        s4_wt = func.sum(PartyDelayManagementSnapshot.barcode_completed_bis_request_pending_weight)

    # Segment 5 Delayed
    if delay_s5 is not None:
        s5_cond = (current_date - func.date(PartyDelayManagementSnapshot.bis_request_complete_date)) >= delay_s5
        s5_pcs = func.sum(case((s5_cond, PartyDelayManagementSnapshot.bis_request_completed_hm_issue_pending_orders), else_=0))
        s5_wt = func.sum(case((s5_cond, PartyDelayManagementSnapshot.bis_request_completed_hm_issue_pending_weight), else_=0))
    else:
        s5_pcs = func.sum(PartyDelayManagementSnapshot.bis_request_completed_hm_issue_pending_orders)
        s5_wt = func.sum(PartyDelayManagementSnapshot.bis_request_completed_hm_issue_pending_weight)

    # Segment 6 Delayed
    if delay_s6 is not None:
        s6_cond = (current_date - func.date(PartyDelayManagementSnapshot.hm_receipt_return_completed_date)) >= delay_s6
        s6_pcs = func.sum(case((s6_cond, PartyDelayManagementSnapshot.hm_receipt_return_completed_qc_issue_pending), else_=0))
        s6_wt = func.sum(case((s6_cond, PartyDelayManagementSnapshot.hm_receipt_return_completed_qc_issue_pending_weight), else_=0))
    else:
        s6_pcs = func.sum(PartyDelayManagementSnapshot.hm_receipt_return_completed_qc_issue_pending)
        s6_wt = func.sum(PartyDelayManagementSnapshot.hm_receipt_return_completed_qc_issue_pending_weight)

    # Segment 7 Delayed
    if delay_s7 is not None:
        s7_cond = (current_date - func.date(PartyDelayManagementSnapshot.invoice_generated_date)) >= delay_s7
        s7_pcs = func.sum(case((s7_cond, PartyDelayManagementSnapshot.invoice_generated_invoice_approve_pending), else_=0))
        s7_wt = func.sum(case((s7_cond, PartyDelayManagementSnapshot.invoice_generated_invoice_approve_pending_weight), else_=0))
    else:
        s7_pcs = func.sum(PartyDelayManagementSnapshot.invoice_generated_invoice_approve_pending)
        s7_wt = func.sum(PartyDelayManagementSnapshot.invoice_generated_invoice_approve_pending_weight)

    # Segment 8 Delayed
    if delay_s8 is not None:
        s8_cond = (current_date - func.date(PartyDelayManagementSnapshot.invoice_approved_date)) >= delay_s8
        s8_pcs = func.sum(case((s8_cond, PartyDelayManagementSnapshot.invoice_approved_not_synched_to_muziris), else_=0))
        s8_wt = func.sum(case((s8_cond, PartyDelayManagementSnapshot.invoice_approved_not_synched_to_muziris_weight), else_=0))
    else:
        s8_pcs = func.sum(PartyDelayManagementSnapshot.invoice_approved_not_synched_to_muziris)
        s8_wt = func.sum(PartyDelayManagementSnapshot.invoice_approved_not_synched_to_muziris_weight)

    total_pieces = s1_pcs + s2_pcs + s3_pcs + s4_pcs + s5_pcs + s6_pcs + s7_pcs + s8_pcs
    total_weight = s1_wt + s2_wt + s3_wt + s4_wt + s5_wt + s6_wt + s7_wt + s8_wt

    # Grouped snapshots subquery to sum metrics and aggregate addresses
    subq_selection = [
        PartyDelayManagementSnapshot.party,
        PartyDelayManagementSnapshot.party_code,
        func.max(PartyDelayManagementSnapshot.party_address).label('party_address'),
        s1_pcs.label('invited_pending_orders'),
        s1_wt.label('invited_pending_weight'),
        s2_pcs.label('process_pending_orders'),
        s2_wt.label('process_pending_weight'),
        s3_pcs.label('process_completed_barcode_pending_orders'),
        s3_wt.label('process_completed_barcode_pending_weight'),
        s4_pcs.label('barcode_completed_bis_request_pending_orders'),
        s4_wt.label('barcode_completed_bis_request_pending_weight'),
        s5_pcs.label('bis_request_completed_hm_issue_pending_orders'),
        s5_wt.label('bis_request_completed_hm_issue_pending_weight'),
        s6_pcs.label('hm_receipt_return_completed_qc_issue_pending'),
        s6_wt.label('hm_receipt_return_completed_qc_issue_pending_weight'),
        s7_pcs.label('invoice_generated_invoice_approve_pending'),
        s7_wt.label('invoice_generated_invoice_approve_pending_weight'),
        s8_pcs.label('invoice_approved_not_synched_to_muziris'),
        s8_wt.label('invoice_approved_not_synched_to_muziris_weight'),
        total_pieces.label('total_pieces'),
        total_weight.label('total_weight')
    ]
    
    snapshot_q = db.session.query(*subq_selection)
    if latest_date:
        snapshot_q = snapshot_q.filter(PartyDelayManagementSnapshot.snapshot_date == latest_date)
    
    if search:
        snapshot_q = snapshot_q.filter(PartyDelayManagementSnapshot.party.ilike(f"%{search}%"))
        
    if party_filter:
        snapshot_q = snapshot_q.filter(PartyDelayManagementSnapshot.party == party_filter)
        
    if makes_selected:
        snapshot_q = snapshot_q.filter(PartyDelayManagementSnapshot.make.in_(makes_selected))
        
    # Apply user-based filtering
    roles = [r.upper() for r in session.get('roles', [])]
    is_admin = 'ADMIN' in roles
    is_manager_2 = 'MANAGER_2' in roles or 'MANAGER-BIC' in roles
    if not is_admin and not is_manager_2:
        if 'MANAGER_KMU' in roles:
            snapshot_q = snapshot_q.filter(PartyDelayManagementSnapshot.make.in_([
                'KMU - KERALA', 'KMU 999 COIN', 'KMU B2B', 'KMU KARNATAKA', 
                'KMU MH', 'KMU-COIN', 'KMU-TN'
            ]))
        elif session.get('username'):
            u = session.get('username').strip().lower()
            snapshot_q = snapshot_q.filter(func.lower(func.trim(PartyDelayManagementSnapshot.make_owner)) == u)

    snapshot_q = snapshot_q.group_by(
        PartyDelayManagementSnapshot.party,
        PartyDelayManagementSnapshot.party_code
    )
    
    snapshot_subq = snapshot_q.subquery('snapshot_subq')

    # Re-build selection to include feedback columns joined on the grouped party
    selection = [
        snapshot_subq.c.party,
        snapshot_subq.c.party_code,
        snapshot_subq.c.party_address,
        snapshot_subq.c.invited_pending_orders,
        snapshot_subq.c.invited_pending_weight,
        snapshot_subq.c.process_pending_orders,
        snapshot_subq.c.process_pending_weight,
        snapshot_subq.c.process_completed_barcode_pending_orders,
        snapshot_subq.c.process_completed_barcode_pending_weight,
        snapshot_subq.c.barcode_completed_bis_request_pending_orders,
        snapshot_subq.c.barcode_completed_bis_request_pending_weight,
        snapshot_subq.c.bis_request_completed_hm_issue_pending_orders,
        snapshot_subq.c.bis_request_completed_hm_issue_pending_weight,
        snapshot_subq.c.hm_receipt_return_completed_qc_issue_pending,
        snapshot_subq.c.hm_receipt_return_completed_qc_issue_pending_weight,
        snapshot_subq.c.invoice_generated_invoice_approve_pending,
        snapshot_subq.c.invoice_generated_invoice_approve_pending_weight,
        snapshot_subq.c.invoice_approved_not_synched_to_muziris,
        snapshot_subq.c.invoice_approved_not_synched_to_muziris_weight,
        snapshot_subq.c.total_pieces,
        snapshot_subq.c.total_weight
    ]
    
    for subq in f_subqs:
        selection.extend([
            subq.c.feedback_text.label(f'f{f_subqs.index(subq)+1}_text'),
            subq.c.feedback_category.label(f'f{f_subqs.index(subq)+1}_category'),
            subq.c.username.label(f'f{f_subqs.index(subq)+1}_username'),
            subq.c.created_at.label(f'f{f_subqs.index(subq)+1}_date')
        ])
    
    query = db.session.query(*selection)
    for subq in f_subqs:
        query = query.outerjoin(subq, snapshot_subq.c.party == subq.c.party)
        
    # Apply feedback filter
    if feedback_filter == 'with_feedback':
        query = query.filter(or_(*(subq.c.feedback_text.isnot(None) for subq in f_subqs)))
    elif feedback_filter == 'without_feedback':
        query = query.filter(and_(*(subq.c.feedback_text.is_(None) for subq in f_subqs)))
    elif feedback_filter.startswith('category_'):
        cat_val = feedback_filter[len('category_'):]
        query = query.filter(or_(*(subq.c.feedback_category == cat_val for subq in f_subqs)))

    rows = query.order_by(snapshot_subq.c.party).all()
    
    processed_rows = []
    for r in rows:
        summary_dict = {
            'party': r[0],
            'party_code': r[1],
            'party_address': r[2],
            'invited_pending_orders': r[3] or 0,
            'invited_pending_weight': float(r[4] or 0),
            'process_pending_orders': r[5] or 0,
            'process_pending_weight': float(r[6] or 0),
            'process_completed_barcode_pending_orders': r[7] or 0,
            'process_completed_barcode_pending_weight': float(r[8] or 0),
            'barcode_completed_bis_request_pending_orders': r[9] or 0,
            'barcode_completed_bis_request_pending_weight': float(r[10] or 0),
            'bis_request_completed_hm_issue_pending_orders': r[11] or 0,
            'bis_request_completed_hm_issue_pending_weight': float(r[12] or 0),
            'hm_receipt_return_completed_qc_issue_pending': r[13] or 0,
            'hm_receipt_return_completed_qc_issue_pending_weight': float(r[14] or 0),
            'invoice_generated_invoice_approve_pending': r[15] or 0,
            'invoice_generated_invoice_approve_pending_weight': float(r[16] or 0),
            'invoice_approved_not_synched_to_muziris': r[17] or 0,
            'invoice_approved_not_synched_to_muziris_weight': float(r[18] or 0),
            'total_pieces': r[19] or 0,
            'total_weight': float(r[20] or 0)
        }
        
        feedbacks = {}
        for i in range(1, 9):
            idx = 21 + (i-1)*4
            f_t, f_c, f_u, f_d = r[idx], r[idx+1], r[idx+2], r[idx+3]
            feedbacks[f'segment{i}'] = {
                'feedback_text': f_t, 
                'category': f_c, 
                'username': f_u, 
                'date': f_d.strftime("%Y-%m-%d %H:%M") if f_d else ''
            }
        
        processed_rows.append({
            'summary': summary_dict,
            'feedbacks': feedbacks
        })

    return render_template(
        'partials/_view_party_delay_management.html',
        rows=processed_rows
    )

@dashboard_bp.route('/api/party-delay-management/feedback', methods=['POST'])
@jwt_required()
def save_party_delay_feedback():
    data = request.json
    party = data.get('party')
    segment_id = data.get('segment_id')
    feedback_text = data.get('feedback_text')
    category = data.get('category')
    username = session.get('username')

    if not all([party, segment_id, feedback_text]):
        return jsonify({"status": "error", "message": "Missing required fields"}), 400

    feedback = PartyDelayManagementFeedback(
        party=party,
        segment_id=segment_id,
        feedback_text=feedback_text,
        feedback_category=category,
        username=username
    )
    db.session.add(feedback)
    db.session.commit()

    return jsonify({"status": "success", "message": "Feedback saved successfully"})

@dashboard_bp.route('/api/party-delay-management/details/<int:segment_id>')
@jwt_required()
def get_party_delay_details(segment_id):
    party = request.args.get('party')
    delay = request.args.get('delay', type=int)
    
    models = {
        1: PartyAcceptPendingSnapshot,
        2: PartyProcessPendingSnapshot,
        3: PartyBarcodePendingSnapshot,
        4: PartyBarcodeCompletedBISRequestPendingSnapshot,
        5: PartyBISRequestCompletedHMIssuePendingSnapshot,
        6: PartyHMReceiptCompletedQCIssuePendingSnapshot,
        7: PartyInvoiceGeneratedInvoiceApprovePendingSnapshot,
        8: PartyInvoiceApprovedNotSynchedToMuzirisSnapshot
    }
    
    model = models.get(segment_id)
    if not model:
        return jsonify({"status": "error", "message": "Invalid segment"}), 400

    query = model.query.filter(model.party == party)
    # Get latest date for the detail model
    latest_date = db.session.query(func.max(model.snapshot_date)).scalar()
    if latest_date:
        query = query.filter(model.snapshot_date == latest_date)
        
    if delay is not None:
        if segment_id == 1:
            query = query.filter((func.current_date() - func.date(model.po_date)) >= delay)
        elif segment_id == 2:
            query = query.filter((func.current_date() - func.date(model.po_date)) >= delay)
        elif segment_id == 3:
            query = query.filter((func.current_date() - func.date(model.po_date)) >= delay)
        elif segment_id == 4:
            query = query.filter((func.current_date() - func.date(model.barcode_completion_date)) >= delay)
        elif segment_id == 5:
            query = query.filter((func.current_date() - func.date(model.barcode_completion_date)) >= delay)
        elif segment_id == 6:
            query = query.filter((func.current_date() - func.date(model.hm_completed_at)) >= delay)
        elif segment_id == 7:
            query = query.filter((func.current_date() - func.date(model.invoice_generated_date)) >= delay)
        elif segment_id == 8:
            query = query.filter((func.current_date() - func.date(model.invoice_approved_date)) >= delay)

    # Apply user-based filtering
    roles = [r.upper() for r in session.get('roles', [])]
    is_admin = 'ADMIN' in roles
    is_manager_2 = 'MANAGER_2' in roles or 'MANAGER-BIC' in roles
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

@dashboard_bp.route('/api/party-delay-management/feedback-info')
@jwt_required()
def get_party_feedback_info():
    party = request.args.get('party')
    segment_id = request.args.get('segment_id', type=int)
    
    feedback = PartyDelayManagementFeedback.query.filter_by(
        party=party, 
        segment_id=segment_id
    ).order_by(PartyDelayManagementFeedback.created_at.desc()).first()
    
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
