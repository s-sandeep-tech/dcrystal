from flask import render_template, request, jsonify
from flask_jwt_extended import jwt_required
from app.dashboard import dashboard_bp
from app.models import Notification, PartyProcessAgeingSnapshot
from app.extensions import db
from sqlalchemy import func
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

def _get_process_delay_data():
    # Filters
    party_name = request.args.get('party_name', '').strip()
    completed_process = request.args.get('completed_process', '').strip()
    next_process = request.args.get('next_process', '').strip()

    query = PartyProcessAgeingSnapshot.query

    if party_name:
        query = query.filter(PartyProcessAgeingSnapshot.party_name.ilike(f"%{party_name}%"))
    if completed_process:
        query = query.filter(PartyProcessAgeingSnapshot.completed_process_level.ilike(f"%{completed_process}%"))
    if next_process:
        query = query.filter(PartyProcessAgeingSnapshot.next_process_level.ilike(f"%{next_process}%"))

    # Pagination and Sorting
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    
    # Sort by party name and then custom sort order
    query = query.order_by(
        PartyProcessAgeingSnapshot.party_name.asc(),
        PartyProcessAgeingSnapshot.sort_order.asc()
    )
    
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    rows = [r.to_dict() for r in pagination.items]

    # Stats (Totals)
    totals = db.session.query(
        func.sum(PartyProcessAgeingSnapshot.completed_quantity).label('total_qty'),
        func.sum(PartyProcessAgeingSnapshot.time_window_1_2_days).label('total_1_2'),
        func.sum(PartyProcessAgeingSnapshot.time_window_2_4_days).label('total_2_4'),
        func.sum(PartyProcessAgeingSnapshot.time_window_5_10_days).label('total_5_10'),
        func.sum(PartyProcessAgeingSnapshot.time_window_more_than_10_days).label('total_more_10')
    )
    
    if party_name:
        totals = totals.filter(PartyProcessAgeingSnapshot.party_name.ilike(f"%{party_name}%"))
    if completed_process:
        totals = totals.filter(PartyProcessAgeingSnapshot.completed_process_level.ilike(f"%{completed_process}%"))
    if next_process:
        totals = totals.filter(PartyProcessAgeingSnapshot.next_process_level.ilike(f"%{next_process}%"))
        
    stats = totals.first()

    footer_totals = {
        'completed_quantity': int(stats.total_qty or 0),
        'time_window_1_2_days': int(stats.total_1_2 or 0),
        'time_window_2_4_days': int(stats.total_2_4 or 0),
        'time_window_5_10_days': int(stats.total_5_10 or 0),
        'time_window_more_than_10_days': int(stats.total_more_10 or 0)
    }

    return {
        'rows': rows,
        'pagination': pagination,
        'footer_totals': footer_totals
    }

@dashboard_bp.route('/processleveldelay')
def process_level_delay():
    try:
        unread_count = Notification.query.filter_by(is_read=False).count()
        sync_time = datetime.now().strftime("%H:%M")

        data = _get_process_delay_data()

        return render_template('process_level_delay.html',
                             unread_count=unread_count,
                             sync_time=sync_time,
                             **data)
    except Exception as e:
        logger.error(f"Error in process_level_delay: {str(e)}")
        return f"Error: {str(e)}", 500

@dashboard_bp.route('/partial/processleveldelay')
def partial_process_level_delay():
    try:
        data = _get_process_delay_data()
        return render_template('partials/_view_process_level_delay.html', **data)
    except Exception as e:
        logger.error(f"Error in partial_process_level_delay: {str(e)}")
        return f"Error: {str(e)}", 500

@dashboard_bp.route('/api/processleveldelay/options')
@jwt_required()
def process_level_delay_options():
    try:
        options = {
            'party_names': [r[0] for r in db.session.query(PartyProcessAgeingSnapshot.party_name.distinct()).order_by(PartyProcessAgeingSnapshot.party_name).all() if r[0]],
            'completed_processes': [r[0] for r in db.session.query(PartyProcessAgeingSnapshot.completed_process_level.distinct()).order_by(PartyProcessAgeingSnapshot.completed_process_level).all() if r[0]],
            'next_processes': [r[0] for r in db.session.query(PartyProcessAgeingSnapshot.next_process_level.distinct()).order_by(PartyProcessAgeingSnapshot.next_process_level).all() if r[0]]
        }
        return jsonify(options)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
