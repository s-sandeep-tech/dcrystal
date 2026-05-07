from flask import render_template, request, jsonify, session
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.dashboard import dashboard_bp
from app.models.snapshots import (
    QCDelayManagementSnapshot, 
    QCDelayManagementFeedback,
    SupplierQCIssueReceiptPendingSnapshot,
    QCReceiptCompletedQCPendingSnapshot,
    QCCompletedInvoicePendingSnapshot
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

@dashboard_bp.route('/qc-delay-management')
@jwt_required()
def qc_delay_management():
    # Sync time
    sync_time = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%I:%M %p")
    
    # Get filters
    search = request.args.get('search', '')
    office = request.args.get('office', '')
    
    # Get unique offices for filter
    offices_query = db.session.query(QCDelayManagementSnapshot.qc_ro).distinct()
    if latest_date:
        offices_query = offices_query.filter(QCDelayManagementSnapshot.snapshot_date == latest_date)
    offices = [o[0] for o in offices_query.all() if o[0]]

    return render_template(
        'qc_delay_management.html',
        offices=sorted(offices),
        sync_time=sync_time,
        current_username=session.get('username'),
        initial_load=True
    )

@dashboard_bp.route('/partial/qc-delay-management-report')
@jwt_required()
def partial_qc_delay_management_report():
    search = request.args.get('search', '')
    office = request.args.get('office', '')
    
    # Get latest snapshot date
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

    query = db.session.query(
        QCDelayManagementSnapshot,
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
    ).outerjoin(f1_subq, QCDelayManagementSnapshot.qc_ro == f1_subq.c.qc_ro)\
     .outerjoin(f2_subq, QCDelayManagementSnapshot.qc_ro == f2_subq.c.qc_ro)\
     .outerjoin(f3_subq, QCDelayManagementSnapshot.qc_ro == f3_subq.c.qc_ro)

    if latest_date:
        query = query.filter(QCDelayManagementSnapshot.snapshot_date == latest_date)
    
    if search:
        query = query.filter(QCDelayManagementSnapshot.qc_ro.ilike(f"%{search}%"))
    
    if office:
        query = query.filter(QCDelayManagementSnapshot.qc_ro == office)

    rows = query.order_by(QCDelayManagementSnapshot.qc_ro).all()
    
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
        'partials/_view_qc_delay_management.html',
        rows=processed_rows
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
    
    if segment_id == 1:
        model = SupplierQCIssueReceiptPendingSnapshot
    elif segment_id == 2:
        model = QCReceiptCompletedQCPendingSnapshot
    elif segment_id == 3:
        model = QCCompletedInvoicePendingSnapshot
    else:
        return jsonify({"status": "error", "message": "Invalid segment"}), 400

    query = model.query.filter(model.qc_ro == qc_ro)
    # Get latest date for the detail model
    latest_date = db.session.query(func.max(model.snapshot_date)).scalar()
    if latest_date:
        query = query.filter(model.snapshot_date == latest_date)
        
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
