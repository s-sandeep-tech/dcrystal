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
from sqlalchemy import func, case
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
    parties = [p[0] for p in parties_query.all() if p[0]]

    # Get unique makes for filter
    makes_query = db.session.query(PartyDelayManagementSnapshot.make).distinct()
    if latest_date:
        makes_query = makes_query.filter(PartyDelayManagementSnapshot.snapshot_date == latest_date)
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

    # Grouped snapshots subquery to sum metrics and aggregate addresses
    subq_selection = [
        PartyDelayManagementSnapshot.party,
        PartyDelayManagementSnapshot.party_code,
        func.max(PartyDelayManagementSnapshot.party_address).label('party_address'),
        func.sum(PartyDelayManagementSnapshot.invited_pending_orders).label('invited_pending_orders'),
        func.sum(PartyDelayManagementSnapshot.invited_pending_weight).label('invited_pending_weight'),
        func.sum(PartyDelayManagementSnapshot.process_pending_orders).label('process_pending_orders'),
        func.sum(PartyDelayManagementSnapshot.process_pending_weight).label('process_pending_weight'),
        func.sum(PartyDelayManagementSnapshot.process_completed_barcode_pending_orders).label('process_completed_barcode_pending_orders'),
        func.sum(PartyDelayManagementSnapshot.process_completed_barcode_pending_weight).label('process_completed_barcode_pending_weight'),
        func.sum(PartyDelayManagementSnapshot.barcode_completed_bis_request_pending_orders).label('barcode_completed_bis_request_pending_orders'),
        func.sum(PartyDelayManagementSnapshot.barcode_completed_bis_request_pending_weight).label('barcode_completed_bis_request_pending_weight'),
        func.sum(PartyDelayManagementSnapshot.bis_request_completed_hm_issue_pending_orders).label('bis_request_completed_hm_issue_pending_orders'),
        func.sum(PartyDelayManagementSnapshot.bis_request_completed_hm_issue_pending_weight).label('bis_request_completed_hm_issue_pending_weight'),
        func.sum(PartyDelayManagementSnapshot.hm_receipt_return_completed_qc_issue_pending).label('hm_receipt_return_completed_qc_issue_pending'),
        func.sum(PartyDelayManagementSnapshot.hm_receipt_return_completed_qc_issue_pending_weight).label('hm_receipt_return_completed_qc_issue_pending_weight'),
        func.sum(PartyDelayManagementSnapshot.invoice_generated_invoice_approve_pending).label('invoice_generated_invoice_approve_pending'),
        func.sum(PartyDelayManagementSnapshot.invoice_generated_invoice_approve_pending_weight).label('invoice_generated_invoice_approve_pending_weight'),
        func.sum(PartyDelayManagementSnapshot.invoice_approved_not_synched_to_muziris).label('invoice_approved_not_synched_to_muziris'),
        func.sum(PartyDelayManagementSnapshot.invoice_approved_not_synched_to_muziris_weight).label('invoice_approved_not_synched_to_muziris_weight')
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
        snapshot_subq.c.invoice_approved_not_synched_to_muziris_weight
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
            'invoice_approved_not_synched_to_muziris_weight': float(r[18] or 0)
        }
        
        feedbacks = {}
        for i in range(1, 9):
            idx = 19 + (i-1)*4
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
