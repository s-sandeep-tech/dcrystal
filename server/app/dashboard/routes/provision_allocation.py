from flask import render_template, request, jsonify
from flask_jwt_extended import jwt_required
from app.dashboard import dashboard_bp
from app.models.snapshots import ProvisionAllocationSummarySnapshot
from app.extensions import db, redis_client
from app.utils.sync_manager import sync_provision_allocation_data
from sqlalchemy import func, case
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

        cache_key = generate_cache_key('prov_alloc_partial_v3', latest_date, 
                                     search=search, location=location, 
                                     page=page, per_page=per_page)
        
        cached_data = redis_client.get(cache_key)
        if cached_data:
            data = json.loads(cached_data)
            pagination = CachedPagination(data['rows'], page, per_page, data['total'])
            return render_template('partials/_view_provision_allocation_summary.html', 
                                 rows=data['rows'], pagination=pagination)

        if not location:
            # Aggregate across all locations in Python for reliability
            all_rows = db.session.query(
                ProvisionAllocationSummarySnapshot
            ).filter(ProvisionAllocationSummarySnapshot.snapshot_date == latest_date).all()
            
            if search:
                s = search.lower()
                all_rows = [r for r in all_rows if (s in (r.report_label or '').lower() or s in (r.report_section or '').lower())]
            
            # Aggregate rows
            aggr = {} # key: (section_normalized, label_normalized)
            for r in all_rows:
                # Robust normalization
                section_raw = (r.report_section or "").strip()
                label_raw = (r.report_label or "").strip()
                
                if section_raw.lower() == 'location summary':
                    section = 'Location Summary'
                    label = 'ALL'
                else:
                    section = section_raw
                    label = label_raw
                
                key = (section, label)
                
                if key not in aggr:
                    aggr[key] = {
                        'location': 'ALL',
                        'report_section': section,
                        'report_label': label,
                        'pcs': 0.0,
                        'grossweight': 0.0,
                        'sort_order': r.sort_order if r.sort_order is not None else 999
                    }
                
                aggr[key]['pcs'] += float(r.pcs or 0)
                aggr[key]['grossweight'] += float(r.grossweight or 0)
                # Keep the minimum sort order for the group
                if r.sort_order is not None and r.sort_order < aggr[key]['sort_order']:
                    aggr[key]['sort_order'] = r.sort_order
            
            # Calculate section totals for percent calculation
            # We must group by section ONLY for the denominator
            section_totals = {}
            for key, val in aggr.items():
                sec = val['report_section']
                if sec not in section_totals:
                    section_totals[sec] = 0.0
                section_totals[sec] += val['grossweight']
            
            # Final list and recalculate percent
            final_rows = []
            for key, val in aggr.items():
                sec = val['report_section']
                total_wt = section_totals.get(sec, 0.0)
                
                if sec == 'Location Summary':
                    val['percent'] = 100.0
                elif sec == 'Provision Mode Count':
                    val['percent'] = 0.0
                else:
                    val['percent'] = round((val['grossweight'] * 100.0 / total_wt), 2) if total_wt > 0 else 0.0
                
                final_rows.append(val)
            
            # Sort by sort_order
            final_rows.sort(key=lambda x: (x['sort_order'], x['report_label']))
            
            pagination = CachedPagination(final_rows, 1, per_page, len(final_rows))
            
            cache_payload = {
                'rows': final_rows,
                'total': len(final_rows)
            }
            redis_client.setex(cache_key, 3600, json.dumps(cache_payload))

            return render_template('partials/_view_provision_allocation_summary.html', 
                                 rows=final_rows, pagination=pagination)

        # Non-aggregated (Single Location) logic
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
