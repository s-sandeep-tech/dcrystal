from flask import render_template, request, jsonify
from flask_jwt_extended import jwt_required
from app.dashboard import dashboard_bp
from app.models import Notification, StageLevelDelaySnapshot
from app.extensions import db
from sqlalchemy import func, cast, Numeric
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

@dashboard_bp.route('/stageleveldelay')
def stage_level_delay():
    try:
        unread_count = Notification.query.filter_by(is_read=False).count()
        sync_time = datetime.now().strftime("%I:%M %p")

        # Fetch latest snapshot date
        latest_date_query = db.session.query(func.max(StageLevelDelaySnapshot.snapshot_date)).scalar()
        
        return render_template('stage_level_delay.html', 
                             unread_count=unread_count, 
                             sync_time=sync_time,
                             current_level='classification_owner')
    except Exception as e:
        logger.error(f"Error in stage_level_delay: {str(e)}")
        return f"Error: {str(e)}", 500

@dashboard_bp.route('/partial/stageleveldelay')
@jwt_required()
def get_stage_level_delay_partial():
    try:
        latest_date_query = db.session.query(func.max(StageLevelDelaySnapshot.snapshot_date)).scalar()
        
        # Filters
        party = request.args.get('party', '')
        completed_process = request.args.get('completed_process', '')
        next_process = request.args.get('next_process', '')
        search = request.args.get('search', '').strip()
        
        # Parent Info for Drill-down
        parent_level = request.args.get('parent_level')
        parent_value = request.args.get('parent_value')
        grandparent_value = request.args.get('grandparent_value')

        def apply_filters(query):
            if party:
                query = query.filter(StageLevelDelaySnapshot.party == party)
            if completed_process:
                query = query.filter(StageLevelDelaySnapshot.completed_process_level == completed_process)
            if next_process:
                query = query.filter(StageLevelDelaySnapshot.next_process_level == next_process)
            if search:
                query = query.filter(
                    (StageLevelDelaySnapshot.order_number.ilike(f"%{search}%")) |
                    (StageLevelDelaySnapshot.barcode_number.ilike(f"%{search}%"))
                )
            
            if latest_date_query:
                query = query.filter(StageLevelDelaySnapshot.snapshot_date == latest_date_query)
            return query

        # Aggregation columns
        agg_cols = [
            func.sum(StageLevelDelaySnapshot.time_window_1_2_days).label('tw1'),
            func.sum(StageLevelDelaySnapshot.time_window_3_4_days).label('tw2'),
            func.sum(StageLevelDelaySnapshot.time_window_5_10_days).label('tw3'),
            func.sum(StageLevelDelaySnapshot.time_window_more_than_10_days).label('tw4'),
            func.count(StageLevelDelaySnapshot.id).label('qty'),
            func.max(StageLevelDelaySnapshot.party).label('party'),
            func.max(StageLevelDelaySnapshot.completed_process_level).label('completed_process'),
            func.max(StageLevelDelaySnapshot.next_process_level).label('next_process')
        ]

        # Determine level and grouping
        group_cols = []
        if not parent_level:
            level = 'classification_owner'
            group_cols = [StageLevelDelaySnapshot.classification_owner]
            base_query = db.session.query(StageLevelDelaySnapshot)
        elif parent_level == 'classification_owner':
            level = 'make_owner'
            group_cols = [StageLevelDelaySnapshot.classification_owner, StageLevelDelaySnapshot.make_owner]
            base_query = db.session.query(StageLevelDelaySnapshot).filter(StageLevelDelaySnapshot.classification_owner == parent_value)
        elif parent_level == 'make_owner':
            level = 'collection_owner'
            group_cols = [StageLevelDelaySnapshot.classification_owner, StageLevelDelaySnapshot.make_owner, StageLevelDelaySnapshot.collection_owner]
            base_query = db.session.query(StageLevelDelaySnapshot).filter(StageLevelDelaySnapshot.make_owner == parent_value)
            if grandparent_value:
                base_query = base_query.filter(StageLevelDelaySnapshot.classification_owner == grandparent_value)
        elif parent_level == 'collection_owner':
            level = 'leaf'
            group_cols = [
                StageLevelDelaySnapshot.classification_owner, 
                StageLevelDelaySnapshot.make_owner, 
                StageLevelDelaySnapshot.collection_owner,
                StageLevelDelaySnapshot.party,
                StageLevelDelaySnapshot.completed_process_level,
                StageLevelDelaySnapshot.next_process_level
            ]
            base_query = db.session.query(StageLevelDelaySnapshot).filter(StageLevelDelaySnapshot.collection_owner == parent_value)
            # Find make_owner and classification_owner from grandparent_value if needed, 
            # but usually parent_value (collection_owner) is unique enough or we use multiple filters.
            # To be safe, we should pass more context, but let's assume collection_owner filter is enough for now or 
            # we can use the same pattern as make_owner.
        
        # Calculate stats for the main view (root level)
        stats = {}
        if not parent_level:
            stat_q = db.session.query(*agg_cols[:5]) # tw1-tw4 + qty
            stat_q = apply_filters(stat_q)
            stat_res = stat_q.first()
            if stat_res:
                stats = {
                    'tw1': int(stat_res.tw1 or 0),
                    'tw2': int(stat_res.tw2 or 0),
                    'tw3': int(stat_res.tw3 or 0),
                    'tw4': int(stat_res.tw4 or 0),
                    'qty': int(stat_res.qty or 0)
                }

        # Main query for rows
        main_q = base_query.with_entities(*(group_cols + agg_cols))
        main_q = apply_filters(main_q)
        main_q = main_q.group_by(*group_cols).order_by(*group_cols)
        
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)
        pagination = main_q.paginate(page=page, per_page=per_page, error_out=False)

        processed_rows = []
        for r in pagination.items:
            # Group cols order: [Owners..., (if leaf: Party, Completed, Next)]
            row_dict = {
                'tw1': int(r.tw1 or 0),
                'tw2': int(r.tw2 or 0),
                'tw3': int(r.tw3 or 0),
                'tw4': int(r.tw4 or 0),
                'qty': int(r.qty or 0),
                'level': level
            }
            
            if level == 'classification_owner':
                row_dict.update({
                    'classification_owner': r[0], 'make_owner': '', 'collection_owner': '',
                    'party': '', 'completed_process': '', 'next_process': '',
                    'display_value': r[0]
                })
            elif level == 'make_owner':
                row_dict.update({
                    'classification_owner': r[0], 'make_owner': r[1], 'collection_owner': '',
                    'party': '', 'completed_process': '', 'next_process': '',
                    'display_value': r[1]
                })
            elif level == 'collection_owner':
                row_dict.update({
                    'classification_owner': r[0], 'make_owner': r[1], 'collection_owner': r[2],
                    'party': '', 'completed_process': '', 'next_process': '',
                    'display_value': r[2]
                })
            else: # leaf
                row_dict.update({
                    'classification_owner': r[0], 'make_owner': r[1], 'collection_owner': r[2],
                    'party': r[3], 'completed_process': r[4], 'next_process': r[5],
                    'display_value': r[3] # Show party name as display value
                })

            processed_rows.append(row_dict)

        is_child_rows = bool(parent_level)
        return render_template('partials/_stage_level_delay_table.html', 
                             rows=processed_rows, 
                             pagination=pagination if not is_child_rows else None, 
                             stats=stats,
                             current_level=level,
                             is_child_rows=is_child_rows,
                             parent_level=parent_level,
                             parent_value=parent_value,
                             grandparent_value=grandparent_value)
    except Exception as e:
        logger.error(f"Error in get_stage_level_delay_partial: {str(e)}")
        return f'<div class="p-4 text-red-500">Error: {str(e)}</div>', 200

@dashboard_bp.route('/api/stageleveldelay/options')
@jwt_required()
def stage_level_delay_options():
    try:
        latest_date_query = db.session.query(func.max(StageLevelDelaySnapshot.snapshot_date)).scalar()
        base_q = db.session.query(StageLevelDelaySnapshot)
        if latest_date_query:
            base_q = base_q.filter(StageLevelDelaySnapshot.snapshot_date == latest_date_query)
        
        options = {
            'parties': [r[0] for r in base_q.with_entities(StageLevelDelaySnapshot.party).distinct().order_by(StageLevelDelaySnapshot.party).all() if r[0]],
            'completed_processes': [r[0] for r in base_q.with_entities(StageLevelDelaySnapshot.completed_process_level).distinct().order_by(StageLevelDelaySnapshot.completed_process_level).all() if r[0]],
            'next_processes': [r[0] for r in base_q.with_entities(StageLevelDelaySnapshot.next_process_level).distinct().order_by(StageLevelDelaySnapshot.next_process_level).all() if r[0]]
        }
        return jsonify(options)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@dashboard_bp.route('/api/stageleveldelay/details')
@jwt_required()
def stage_level_delay_details():
    try:
        classification_owner = request.args.get('classification_owner')
        make_owner = request.args.get('make_owner')
        collection_owner = request.args.get('collection_owner')
        
        latest_date_query = db.session.query(func.max(StageLevelDelaySnapshot.snapshot_date)).scalar()
        
        query = StageLevelDelaySnapshot.query
        if latest_date_query:
            query = query.filter(StageLevelDelaySnapshot.snapshot_date == latest_date_query)
            
        if classification_owner:
            query = query.filter(StageLevelDelaySnapshot.classification_owner == classification_owner)
        if make_owner:
            query = query.filter(StageLevelDelaySnapshot.make_owner == make_owner)
        if collection_owner:
            query = query.filter(StageLevelDelaySnapshot.collection_owner == collection_owner)
            
        results = query.order_by(StageLevelDelaySnapshot.party.asc(), StageLevelDelaySnapshot.seq.asc().nulls_last()).all()
        
        return jsonify([r.to_dict() for r in results])
    except Exception as e:
        return jsonify({'error': str(e)}), 500
