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

    query = db.session.query(PartyDelayManagementSnapshot)
    for i, subq in enumerate(f_subqs):
        query = query.outerjoin(subq, PartyDelayManagementSnapshot.party == subq.c.party)

    # Re-build selection to include feedback columns
    selection = [PartyDelayManagementSnapshot]
    for subq in f_subqs:
        selection.extend([
            subq.c.feedback_text.label(f'f{f_subqs.index(subq)+1}_text'),
            subq.c.feedback_category.label(f'f{f_subqs.index(subq)+1}_category'),
            subq.c.username.label(f'f{f_subqs.index(subq)+1}_username'),
            subq.c.created_at.label(f'f{f_subqs.index(subq)+1}_date')
        ])
    
    query = db.session.query(*selection)
    for subq in f_subqs:
        query = query.outerjoin(subq, PartyDelayManagementSnapshot.party == subq.c.party)

    if latest_date:
        query = query.filter(PartyDelayManagementSnapshot.snapshot_date == latest_date)
    
    if search:
        query = query.filter(PartyDelayManagementSnapshot.party.ilike(f"%{search}%"))
    
    if party_filter:
        query = query.filter(PartyDelayManagementSnapshot.party == party_filter)

    if makes_selected:
        query = query.filter(PartyDelayManagementSnapshot.make.in_(makes_selected))

    rows = query.order_by(PartyDelayManagementSnapshot.party).all()
    
    processed_rows = []
    for r in rows:
        snapshot = r[0]
        feedbacks = {}
        for i in range(1, 9):
            idx = 1 + (i-1)*4
            f_t, f_c, f_u, f_d = r[idx], r[idx+1], r[idx+2], r[idx+3]
            feedbacks[f'segment{i}'] = {
                'feedback_text': f_t, 
                'category': f_c, 
                'username': f_u, 
                'date': f_d.strftime("%Y-%m-%d %H:%M") if f_d else ''
            }
        
        processed_rows.append({
            'summary': snapshot.to_dict(),
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
