from flask import render_template, session, redirect, url_for, current_app
from app.dashboard import dashboard_bp
from app.models import Notification
from datetime import datetime
from zoneinfo import ZoneInfo

@dashboard_bp.route('/admin/roles')
def admin_roles():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('dashboard.login'))
        
    unread_count = Notification.query.filter_by(is_read=False).count()
    sync_time = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%I:%M %p")
    
    return render_template('admin/roles.html',
                         unread_count=unread_count,
                         sync_time=sync_time)

@dashboard_bp.route('/admin/menus')
def admin_menus():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('dashboard.login'))
        
    unread_count = Notification.query.filter_by(is_read=False).count()
    sync_time = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%I:%M %p")
    
    return render_template('admin/menus.html',
                         unread_count=unread_count,
                         sync_time=sync_time)

@dashboard_bp.route('/admin/mappings')
def admin_mappings():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('dashboard.login'))
        
    unread_count = Notification.query.filter_by(is_read=False).count()
    sync_time = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%I:%M %p")
    
    return render_template('admin/mappings.html',
                         unread_count=unread_count,
                         sync_time=sync_time)
