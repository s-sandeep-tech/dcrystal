from flask import render_template, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.dashboard import dashboard_bp
from app.models import Notification
from app.extensions import db, socketio
from sqlalchemy import or_
import time
from datetime import datetime

@dashboard_bp.route('/notifications/list')
@jwt_required()
def get_notifications_list():
    time.sleep(1) # Simulate network/processing delay
    current_user_id = get_jwt_identity()
    
    # Filter: belonging to user OR global (null)
    notifications = Notification.query.filter(
        or_(Notification.user_id == current_user_id, Notification.user_id == None)
    ).order_by(
        Notification.created_at.desc()
    ).limit(20).all()
    
    return render_template('partials/_notifications_list.html', notifications=notifications)

@dashboard_bp.route('/notify', methods=['POST'])
def create_notification():
    data = request.json
    try:
        notification = Notification(
            title=data.get('title'),
            message=data.get('message'),
            notification_type=data.get('type', 'info'),
            icon=data.get('icon', 'notifications'),
            priority=data.get('priority', 'low'),
            related_order_id=data.get('related_order_id'),
            user_id=data.get('user_id'), # New field
            created_at=datetime.utcnow(),
            is_read=False
        )
        db.session.add(notification)
        db.session.commit()

        # Emit to all (targeted via Socket ID if provided in client-side, 
        # but here we rely on the DB filtering for the list)
        socketio.emit('new_notification', {
            'id': notification.id,
            'title': notification.title,
            'message': notification.message,
            'type': notification.notification_type,
            'icon': notification.icon,
            'priority': notification.priority,
            'time': notification.get_time_ago(),
            'related_order_id': notification.related_order_id,
            'user_id': notification.user_id
        })

        return jsonify({'status': 'success', 'message': 'Notification created and broadcasted'}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500
