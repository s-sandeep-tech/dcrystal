from flask import render_template, request, jsonify
from flask_jwt_extended import jwt_required
from app.dashboard import dashboard_bp
from app.models.snapshots import ProvisionAllocationSummarySnapshot
from app.extensions import db, redis_client
from app.utils.sync_manager import sync_provision_allocation_data
from sqlalchemy import func
from datetime import datetime
from zoneinfo import ZoneInfo
import logging
import json

logger = logging.getLogger(__name__)

class CachedPagination:
    def __init__(self, items, page, per_page, total):
        self.items = items
        self.page = page
        self.per_page = per_page
        self.total = total
        self.has_prev = page > 1
        self.has_next = (page * per_page) < total
        self.prev_num = page - 1
        self.next_num = page + 1
        self.pages = (total + per_page - 1) // per_page if per_page else 0

def generate_cache_key(prefix, snapshot_date=None, **kwargs):
    sorted_kwargs = dict(sorted(kwargs.items()))
    args_str = ":".join(f"{k}={v}" for k, v in sorted_kwargs.items() if v)
    date_str = snapshot_date.strftime("%Y%m%d%H%M%S") if snapshot_date else "latest"
    return f"{prefix}:{date_str}:{args_str}"

@dashboard_bp.route('/provision-allocation-summary')
@jwt_required()
def provision_allocation_summary():
    try:
        sync_time = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%I:%M %p")
        return render_template('provision_allocation_summary.html', sync_time=sync_time)
    except Exception as e:
        logger.error(f"Error in provision_allocation_summary: {str(e)}")
        return f"Error: {str(e)}", 500

@dashboard_bp.route('/api/provision-allocation/options')
@jwt_required()
def provision_allocation_options():
    try:
        locations = [r[0] for r in db.session.query(ProvisionAllocationSummarySnapshot.location.distinct()).order_by(ProvisionAllocationSummarySnapshot.location).all() if r[0]]
        return jsonify({'locations': locations})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@dashboard_bp.route('/partial/provision-allocation')
@jwt_required()
def get_provision_allocation_partial():
    try:
        latest_date = db.session.query(func.max(ProvisionAllocationSummarySnapshot.snapshot_date)).scalar()
        
        search = request.args.get('search', '').strip()
        location = request.args.get('location', '')
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 2000, type=int)

        cache_key = generate_cache_key('prov_alloc_partial', latest_date, 
                                     search=search, location=location, 
                                     page=page, per_page=per_page)
        
        cached_data = redis_client.get(cache_key)
        if cached_data:
            data = json.loads(cached_data)
            pagination = CachedPagination(data['rows'], page, per_page, data['total'])
            return render_template('partials/_view_provision_allocation_summary.html', 
                                 rows=data['rows'], pagination=pagination)

        query = db.session.query(ProvisionAllocationSummarySnapshot)
        
        if latest_date:
            query = query.filter(ProvisionAllocationSummarySnapshot.snapshot_date == latest_date)
        
        if search:
            query = query.filter(ProvisionAllocationSummarySnapshot.location.ilike(f"%{search}%") | 
                                 ProvisionAllocationSummarySnapshot.report_label.ilike(f"%{search}%"))
        
        if location:
            query = query.filter(ProvisionAllocationSummarySnapshot.location == location)
            
        query = query.order_by(ProvisionAllocationSummarySnapshot.location, ProvisionAllocationSummarySnapshot.sort_order, ProvisionAllocationSummarySnapshot.report_label)
        
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        
        rows = [r.to_dict() for r in pagination.items]
        
        cache_payload = {
            'rows': rows,
            'total': pagination.total
        }
        redis_client.setex(cache_key, 3600, json.dumps(cache_payload))

        return render_template('partials/_view_provision_allocation_summary.html', 
                             rows=rows, pagination=pagination)
    except Exception as e:
        logger.error(f"Error in get_provision_allocation_partial: {str(e)}")
        return f'<div class="p-8 text-center text-red-500 font-bold">Backend Error: {str(e)}</div>', 200

@dashboard_bp.route('/api/sync/provision_allocation', methods=['POST'])
@jwt_required()
def sync_provision_allocation():
    return jsonify(sync_provision_allocation_data())
