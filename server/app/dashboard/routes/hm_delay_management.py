from flask import render_template, request, jsonify, session
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.dashboard import dashboard_bp
from app.models.snapshots import (
    HallmarkingDelayManagementSnapshot, 
    HallmarkingDelayManagementFeedback,
    SupplierHMIssueReceiptPendingSnapshot,
    HMReceiptCompletedHMPendingSnapshot,
    HMCompletedReturnPendingSnapshot
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

@dashboard_bp.route('/hm-delay-management')
@jwt_required()
def hm_delay_management():
    # Sync time
    sync_time = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%I:%M %p")
    
    # Get filters
    search = request.args.get('search', '')
    center = request.args.get('center', '')
    # Get latest snapshot date
    latest_date = db.session.query(func.max(HallmarkingDelayManagementSnapshot.snapshot_date)).scalar()
    
    # Get unique centers for filter
    centers_query = db.session.query(HallmarkingDelayManagementSnapshot.hallmarking_center).distinct()
    if latest_date:
        centers_query = centers_query.filter(HallmarkingDelayManagementSnapshot.snapshot_date == latest_date)
    centers = [c[0] for c in centers_query.all() if c[0]]

    return render_template(
        'hm_delay_management.html',
        centers=sorted(centers),
        sync_time=sync_time,
        current_username=session.get('username'),
        initial_load=True
    )

@dashboard_bp.route('/partial/hm-delay-management-report')
@jwt_required()
def partial_hm_delay_management_report():
    search = request.args.get('search', '')
    center = request.args.get('center', '')
    
    # Get latest snapshot date
    latest_date = db.session.query(func.max(HallmarkingDelayManagementSnapshot.snapshot_date)).scalar()
    
    # Subquery helper for latest feedback
    def get_latest_feedback_subq(segment_id):
        subq = db.session.query(
            HallmarkingDelayManagementFeedback.hallmark_center,
            func.max(HallmarkingDelayManagementFeedback.created_at).label('max_date')
        ).filter(HallmarkingDelayManagementFeedback.segment_id == segment_id).group_by(
            HallmarkingDelayManagementFeedback.hallmark_center
        ).subquery()
        
        return db.session.query(HallmarkingDelayManagementFeedback).join(
            subq,
            db.and_(
                HallmarkingDelayManagementFeedback.hallmark_center == subq.c.hallmark_center,
                HallmarkingDelayManagementFeedback.created_at == subq.c.max_date
            )
        ).filter(HallmarkingDelayManagementFeedback.segment_id == segment_id).subquery()

    f1_subq = get_latest_feedback_subq(1)
    f2_subq = get_latest_feedback_subq(2)
    f3_subq = get_latest_feedback_subq(3)

    query = db.session.query(
        HallmarkingDelayManagementSnapshot,
        f1_subq.c.feedback_text.label('f1_text'),
        f1_subq.c.feedback_category.label('f1_category'),
        f1_subq.c.username.label('f1_username'),
        f1_subq.c.created_at.label('f1_date'),
        f2_subq.c.feedback_text.label('f2_text'),
        f2_subq.c.feedback_category.label('f2_category'),
        f2_subq.c.username.label('f2_username'),
        f2_subq.c.created_at.label('f2_date'),
        f3_subq.c.feedback_text.label('f3_text'),
        f3_subq.c.feedback_category.label('f3_category'),
        f3_subq.c.username.label('f3_username'),
        f3_subq.c.created_at.label('f3_date')
    ).outerjoin(f1_subq, HallmarkingDelayManagementSnapshot.hallmarking_center == f1_subq.c.hallmark_center)\
     .outerjoin(f2_subq, HallmarkingDelayManagementSnapshot.hallmarking_center == f2_subq.c.hallmark_center)\
     .outerjoin(f3_subq, HallmarkingDelayManagementSnapshot.hallmarking_center == f3_subq.c.hallmark_center)

    if latest_date:
        query = query.filter(HallmarkingDelayManagementSnapshot.snapshot_date == latest_date)
    
    if search:
        query = query.filter(HallmarkingDelayManagementSnapshot.hallmarking_center.ilike(f"%{search}%"))
    
    if center:
        query = query.filter(HallmarkingDelayManagementSnapshot.hallmarking_center == center)

    rows = query.order_by(HallmarkingDelayManagementSnapshot.hallmarking_center).all()
    
    processed_rows = []
    for r, f1_t, f1_c, f1_u, f1_d, f2_t, f2_c, f2_u, f2_d, f3_t, f3_c, f3_u, f3_d in rows:
        processed_rows.append({
            'summary': r.to_dict(),
            'feedbacks': {
                'segment1': {'feedback_text': f1_t, 'category': f1_c, 'username': f1_u, 'date': f1_d.strftime("%Y-%m-%d %H:%M") if f1_d else ''},
                'segment2': {'feedback_text': f2_t, 'category': f2_c, 'username': f2_u, 'date': f2_d.strftime("%Y-%m-%d %H:%M") if f2_d else ''},
                'segment3': {'feedback_text': f3_t, 'category': f3_c, 'username': f3_u, 'date': f3_d.strftime("%Y-%m-%d %H:%M") if f3_d else ''},
            }
        })

    return render_template(
        'partials/_view_hm_delay_management.html',
        rows=processed_rows
    )

@dashboard_bp.route('/api/hm-delay-management/feedback', methods=['POST'])
@jwt_required()
def save_hm_delay_feedback():
    data = request.json
    hallmark_center = data.get('hallmark_center')
    segment_id = data.get('segment_id')
    feedback_text = data.get('feedback_text')
    category = data.get('category')
    username = session.get('username')

    if not all([hallmark_center, segment_id, feedback_text]):
        return jsonify({"status": "error", "message": "Missing required fields"}), 400

    feedback = HallmarkingDelayManagementFeedback(
        hallmark_center=hallmark_center,
        segment_id=segment_id,
        feedback_text=feedback_text,
        feedback_category=category,
        username=username
    )
    db.session.add(feedback)
    db.session.commit()

    return jsonify({"status": "success", "message": "Feedback saved successfully"})

@dashboard_bp.route('/api/hm-delay-management/details/<int:segment_id>')
@jwt_required()
def get_hm_delay_details(segment_id):
    hallmark_center = request.args.get('hallmark_center')
    
    if segment_id == 1:
        model = SupplierHMIssueReceiptPendingSnapshot
    elif segment_id == 2:
        model = HMReceiptCompletedHMPendingSnapshot
    elif segment_id == 3:
        model = HMCompletedReturnPendingSnapshot
    else:
        return jsonify({"status": "error", "message": "Invalid segment"}), 400

    query = model.query.filter(model.hallmark_center == hallmark_center)
    # Get latest date for the detail model
    latest_date = db.session.query(func.max(model.snapshot_date)).scalar()
    if latest_date:
        query = query.filter(model.snapshot_date == latest_date)
        
    rows = query.all()
    return jsonify([r.to_dict() for r in rows])

@dashboard_bp.route('/api/hm-delay-management/feedback-info')
@jwt_required()
def get_hm_feedback_info():
    hallmark_center = request.args.get('hallmark_center')
    segment_id = request.args.get('segment_id', type=int)
    
    feedback = HallmarkingDelayManagementFeedback.query.filter_by(
        hallmark_center=hallmark_center, 
        segment_id=segment_id
    ).order_by(HallmarkingDelayManagementFeedback.created_at.desc()).first()
    
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
