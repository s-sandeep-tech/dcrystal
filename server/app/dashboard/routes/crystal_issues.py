from flask import render_template, request, jsonify
from app.dashboard import dashboard_bp
from app.models import Notification, TicketLogSnapshot
from app.extensions import db
from sqlalchemy import func
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class CrystalIssuesReport:
    @staticmethod
    def get_filter_options():
        try:
            options = {
                'offices': [r[0] for r in db.session.query(TicketLogSnapshot.issue_reported_office.distinct()).order_by(TicketLogSnapshot.issue_reported_office).all() if r[0]],
                'users': [r[0] for r in db.session.query(TicketLogSnapshot.issue_reported_user.distinct()).order_by(TicketLogSnapshot.issue_reported_user).all() if r[0]],
                'statuses': ['Pending', 'Completed']
            }
            return options
        except Exception as e:
            logger.error(f"Error fetching crystal issues options: {str(e)}")
            return None

    @staticmethod
    def get_paginated_data(params):
        try:
            page = params.get('page', 1, type=int)
            per_page = params.get('per_page', 50, type=int)
            search = params.get('search', '').strip()
            office = params.get('office', '')
            user = params.get('user', '')
            status = params.get('status', '')
            
            # Hierarchy params
            parent_level = params.get('parent_level') # 'office' or 'user'
            parent_value = params.get('parent_value')
            parent_office = params.get('parent_office') # Extra context for user level

            # Date filters
            reported_from = params.get('reported_from', '')
            reported_to = params.get('reported_to', '')
            completed_from = params.get('completed_from', '')
            completed_to = params.get('completed_to', '')

            def apply_filters(q):
                if search:
                    q = q.filter(
                        (TicketLogSnapshot.ticket_no.ilike(f"%{search}%")) |
                        (TicketLogSnapshot.party_name.ilike(f"%{search}%")) |
                        (TicketLogSnapshot.issue_description.ilike(f"%{search}%"))
                    )
                if office: q = q.filter(TicketLogSnapshot.issue_reported_office == office)
                if user: q = q.filter(TicketLogSnapshot.issue_reported_user == user)
                if status: q = q.filter(TicketLogSnapshot.crystal_status == status)
                if reported_from:
                    try: q = q.filter(TicketLogSnapshot.issue_reported_date >= datetime.strptime(reported_from, '%Y-%m-%d'))
                    except: pass
                if reported_to:
                    try: q = q.filter(TicketLogSnapshot.issue_reported_date <= datetime.strptime(reported_to, '%Y-%m-%d'))
                    except: pass
                if completed_from:
                    try: q = q.filter(TicketLogSnapshot.crystal_completed_date >= datetime.strptime(completed_from, '%Y-%m-%d'))
                    except: pass
                if completed_to:
                    try: q = q.filter(TicketLogSnapshot.crystal_completed_date <= datetime.strptime(completed_to, '%Y-%m-%d'))
                    except: pass
                return q

            # Calculate Global Stats (ignore parent_level for global stats)
            stats_query = db.session.query(
                func.count().label('total'),
                func.count(func.nullif(TicketLogSnapshot.crystal_status == 'Completed', True)).label('pending'),
                func.count(func.nullif(TicketLogSnapshot.crystal_status == 'Completed', False)).label('completed')
            ).select_from(TicketLogSnapshot)
            stats_query = apply_filters(stats_query)
            stats_res = stats_query.first()
            stats = {
                'total': stats_res.total or 0,
                'pending': stats_res.pending or 0,
                'completed': stats_res.completed or 0
            }

            # Main Query Logic
            if parent_level == 'office':
                # Expanding RO -> Show Users
                group_cols = [TicketLogSnapshot.issue_reported_office, TicketLogSnapshot.issue_reported_user]
                query = db.session.query(
                    TicketLogSnapshot.issue_reported_office,
                    TicketLogSnapshot.issue_reported_user,
                    func.count().label('total'),
                    func.count(func.nullif(TicketLogSnapshot.crystal_status == 'Completed', True)).label('pending'),
                    func.count(func.nullif(TicketLogSnapshot.crystal_status == 'Completed', False)).label('completed')
                ).filter(TicketLogSnapshot.issue_reported_office == parent_value)
                query = apply_filters(query).group_by(*group_cols).order_by(TicketLogSnapshot.issue_reported_user)
                level = 'user'
                
            elif parent_level == 'user':
                # Expanding User -> Show Tickets
                query = TicketLogSnapshot.query.filter(
                    TicketLogSnapshot.issue_reported_office == parent_office,
                    TicketLogSnapshot.issue_reported_user == parent_value
                )
                query = apply_filters(query).order_by(TicketLogSnapshot.issue_reported_date.desc())
                level = 'ticket'
                
            else:
                # Root Level -> Show ROs
                group_cols = [TicketLogSnapshot.issue_reported_office]
                query = db.session.query(
                    TicketLogSnapshot.issue_reported_office,
                    func.count().label('total'),
                    func.count(func.nullif(TicketLogSnapshot.crystal_status == 'Completed', True)).label('pending'),
                    func.count(func.nullif(TicketLogSnapshot.crystal_status == 'Completed', False)).label('completed')
                )
                query = apply_filters(query).group_by(*group_cols).order_by(TicketLogSnapshot.issue_reported_office)
                level = 'office'

            pagination = query.paginate(page=page, per_page=per_page, error_out=False)
            return pagination, stats, level
        except Exception as e:
            logger.error(f"Error fetching crystal issues data: {str(e)}")
            return None, {'total': 0, 'pending': 0, 'completed': 0}, 'office'

@dashboard_bp.route('/crystal_issues')
def crystal_issues():
    unread_count = Notification.query.filter_by(is_read=False).count()
    sync_time = datetime.now().strftime("%H:%M")
    
    per_page = request.args.get('per_page', 50, type=int)
    pagination = {'per_page': per_page, 'page': 1, 'total': 0, 'has_prev': False, 'has_next': False}
    
    stats = {'total': 0, 'pending': 0, 'completed': 0}
    
    return render_template('crystal_issues.html',
                           unread_count=unread_count,
                           sync_time=sync_time,
                           pagination=pagination,
                           stats=stats)

@dashboard_bp.route('/api/crystal_issues/options')
def crystal_issues_options():
    options = CrystalIssuesReport.get_filter_options()
    if options is None:
        return jsonify({'error': 'Failed to fetch options'}), 500
    return jsonify(options)

@dashboard_bp.route('/partial/crystal_issues')
def get_crystal_issues_partial():
    pagination, stats, level = CrystalIssuesReport.get_paginated_data(request.args)
    
    # Extra context for tree-grid
    parent_level = request.args.get('parent_level')
    parent_value = request.args.get('parent_value')
    parent_office = request.args.get('parent_office')
    is_child_rows = bool(parent_level)
    
    return render_template('partials/_view_crystal_issues.html', 
                         rows=pagination.items if pagination else [], 
                         pagination=pagination,
                         stats=stats,
                         current_level=level,
                         is_child_rows=is_child_rows,
                         parent_level=parent_level,
                         parent_value=parent_value,
                         parent_office=parent_office)
