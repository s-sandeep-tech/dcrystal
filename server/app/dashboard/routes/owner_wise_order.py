from flask import render_template, request, jsonify, session
from flask_jwt_extended import jwt_required
from app.dashboard import dashboard_bp
from app.models import Notification, OwnerWiseOrderSummarySnapshot
from app.extensions import db
from sqlalchemy import func
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

@dashboard_bp.route('/ownerwiseordersummary')
def owner_wise_order_summary():
    try:
        unread_count = Notification.query.filter_by(is_read=False).count()
        sync_time = datetime.now().strftime("%H:%M")

        # Filters
        search = request.args.get('search', '').strip()
        division = request.args.get('division', '')
        group_name = request.args.get('group', '')
        purity = request.args.get('purity', '')
        supplier = request.args.get('supplier', '')
        classification_owner = request.args.get('classification_owner', '')
        collection_owner = request.args.get('collection_owner', '')
        make_owner = request.args.get('make_owner', '')
        classification = request.args.get('classification', '')
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)

        def apply_filters(query):
            if search:
                query = query.filter(
                    (OwnerWiseOrderSummarySnapshot.classification_owner.ilike(f"%{search}%")) |
                    (OwnerWiseOrderSummarySnapshot.collection_owner.ilike(f"%{search}%")) |
                    (OwnerWiseOrderSummarySnapshot.make_owner.ilike(f"%{search}%")) |
                    (OwnerWiseOrderSummarySnapshot.collection.ilike(f"%{search}%"))
                )
            if division:
                query = query.filter(OwnerWiseOrderSummarySnapshot.division == division)
            if group_name:
                query = query.filter(OwnerWiseOrderSummarySnapshot.group_name == group_name)
            if purity:
                query = query.filter(OwnerWiseOrderSummarySnapshot.purity == purity)
            if supplier:
                query = query.filter(OwnerWiseOrderSummarySnapshot.supplier == supplier)
            if classification_owner:
                query = query.filter(OwnerWiseOrderSummarySnapshot.classification_owner == classification_owner)
            if collection_owner:
                query = query.filter(OwnerWiseOrderSummarySnapshot.collection_owner == collection_owner)
            if make_owner:
                query = query.filter(OwnerWiseOrderSummarySnapshot.make_owner == make_owner)
            if classification:
                query = query.filter(OwnerWiseOrderSummarySnapshot.classification == classification)
            
            # User-based filtering: Restrict to make_owner = username if not admin
            if not session.get('is_admin', False) and session.get('username'):
                query = query.filter(OwnerWiseOrderSummarySnapshot.make_owner == session.get('username'))
                
            return query

        # Fetch filter options
        filter_options = {
            'divisions': [r[0] for r in db.session.query(OwnerWiseOrderSummarySnapshot.division).distinct().order_by(OwnerWiseOrderSummarySnapshot.division).all() if r[0]],
            'groups': [r[0] for r in db.session.query(OwnerWiseOrderSummarySnapshot.group_name).distinct().order_by(OwnerWiseOrderSummarySnapshot.group_name).all() if r[0]],
            'purities': [str(r[0]) for r in db.session.query(OwnerWiseOrderSummarySnapshot.purity).distinct().order_by(OwnerWiseOrderSummarySnapshot.purity).all() if r[0]],
            'suppliers': [r[0] for r in db.session.query(OwnerWiseOrderSummarySnapshot.supplier).distinct().order_by(OwnerWiseOrderSummarySnapshot.supplier).all() if r[0]],
            'classification_owners': [r[0] for r in db.session.query(OwnerWiseOrderSummarySnapshot.classification_owner).distinct().order_by(OwnerWiseOrderSummarySnapshot.classification_owner).all() if r[0]],
            'collection_owners': [r[0] for r in db.session.query(OwnerWiseOrderSummarySnapshot.collection_owner).distinct().order_by(OwnerWiseOrderSummarySnapshot.collection_owner).all() if r[0]],
            'make_owners': [r[0] for r in db.session.query(OwnerWiseOrderSummarySnapshot.make_owner).distinct().order_by(OwnerWiseOrderSummarySnapshot.make_owner).all() if r[0]],
            'classifications': [r[0] for r in db.session.query(OwnerWiseOrderSummarySnapshot.classification).distinct().order_by(OwnerWiseOrderSummarySnapshot.classification).all() if r[0]]
        }

        # Global Stats (Using Weights primarily)
        agg_cols = [
            func.sum(OwnerWiseOrderSummarySnapshot.ordered_pcs).label('total_ordered_pcs'),
            func.sum(OwnerWiseOrderSummarySnapshot.ordered_wt).label('total_ordered_wt'),
            func.sum(OwnerWiseOrderSummarySnapshot.accepted_pcs).label('total_accepted_pcs'),
            func.sum(OwnerWiseOrderSummarySnapshot.accepted_wt).label('total_accepted_wt'),
            func.sum(OwnerWiseOrderSummarySnapshot.rejected_pcs).label('total_rejected_pcs'),
            func.sum(OwnerWiseOrderSummarySnapshot.rejected_wt).label('total_rejected_wt'),
            func.sum(OwnerWiseOrderSummarySnapshot.barcoded_pcs).label('total_barcoded_pcs'),
            func.sum(OwnerWiseOrderSummarySnapshot.barcoded_wt).label('total_barcoded_wt'),
            func.sum(OwnerWiseOrderSummarySnapshot.hm_passed_pcs).label('total_hm_passed_pcs'),
            func.sum(OwnerWiseOrderSummarySnapshot.hm_passed_wt).label('total_hm_passed_wt'),
            func.sum(OwnerWiseOrderSummarySnapshot.qc_passed_pcs).label('total_qc_passed_pcs'),
            func.sum(OwnerWiseOrderSummarySnapshot.qc_passed_wt).label('total_qc_passed_wt'),
            func.sum(OwnerWiseOrderSummarySnapshot.invoiced_pcs).label('total_invoiced_pcs'),
            func.sum(OwnerWiseOrderSummarySnapshot.invoiced_wt).label('total_invoiced_wt'),
            func.sum(OwnerWiseOrderSummarySnapshot.delivered_pcs).label('total_delivered_pcs'),
            func.sum(OwnerWiseOrderSummarySnapshot.delivered_wt).label('total_delivered_wt'),
            func.sum(OwnerWiseOrderSummarySnapshot.pending_to_be_delv_pcs).label('total_pending_to_be_delv_pcs'),
            func.sum(OwnerWiseOrderSummarySnapshot.pending_to_be_delv_wt).label('total_pending_to_be_delv_wt')
        ]
        
        agg_q = db.session.query(*agg_cols)
        agg_q = apply_filters(agg_q)
        aggs = agg_q.first()

        total_wt = float(aggs.total_ordered_wt or 0)
        def get_perc(val):
            if total_wt <= 0: return 0
            return min(100, round((float(val or 0) / total_wt) * 100, 1))

        stats = {
            'ordered_wt': f"{float(aggs.total_ordered_wt or 0):,.3f}", 'ordered_pcs': f"{int(aggs.total_ordered_pcs or 0):,}",
            'accepted_wt': f"{float(aggs.total_accepted_wt or 0):,.3f}", 'accepted_pcs': f"{int(aggs.total_accepted_pcs or 0):,}", 'accepted_perc': get_perc(aggs.total_accepted_wt),
            'rejected_wt': f"{float(aggs.total_rejected_wt or 0):,.3f}", 'rejected_pcs': f"{int(aggs.total_rejected_pcs or 0):,}", 'rejected_perc': get_perc(aggs.total_rejected_wt),
            'barcoded_wt': f"{float(aggs.total_barcoded_wt or 0):,.3f}", 'barcoded_pcs': f"{int(aggs.total_barcoded_pcs or 0):,}", 'barcoded_perc': get_perc(aggs.total_barcoded_wt),
            'hallmarked_wt': f"{float(aggs.total_hm_passed_wt or 0):,.3f}", 'hallmarked_pcs': f"{int(aggs.total_hm_passed_pcs or 0):,}", 'hallmarked_perc': get_perc(aggs.total_hm_passed_wt),
            'qc_passed_wt': f"{float(aggs.total_qc_passed_wt or 0):,.3f}", 'qc_passed_pcs': f"{int(aggs.total_qc_passed_pcs or 0):,}", 'qc_passed_perc': get_perc(aggs.total_qc_passed_wt),
            'invoiced_wt': f"{float(aggs.total_invoiced_wt or 0):,.3f}", 'invoiced_pcs': f"{int(aggs.total_invoiced_pcs or 0):,}", 'invoiced_perc': get_perc(aggs.total_invoiced_wt),
            'delivered_wt': f"{float(aggs.total_delivered_wt or 0):,.3f}", 'delivered_pcs': f"{int(aggs.total_delivered_pcs or 0):,}", 'delivered_perc': get_perc(aggs.total_delivered_wt),
            'pending_to_be_delv_wt': f"{float(aggs.total_pending_to_be_delv_wt or 0):,.3f}", 'pending_to_be_delv_pcs': f"{int(aggs.total_pending_to_be_delv_pcs or 0):,}", 'pending_to_be_delv_perc': get_perc(aggs.total_pending_to_be_delv_wt)
        }

        # Drill-down level
        if not classification_owner:
            group_cols = [OwnerWiseOrderSummarySnapshot.classification_owner]
            level = 'classification_owner'
        elif classification_owner and not make_owner:
            group_cols = [OwnerWiseOrderSummarySnapshot.classification_owner, OwnerWiseOrderSummarySnapshot.make_owner]
            level = 'make_owner'
        else:
            group_cols = [OwnerWiseOrderSummarySnapshot.classification_owner, OwnerWiseOrderSummarySnapshot.make_owner, OwnerWiseOrderSummarySnapshot.collection_owner]
            level = 'collection_owner'

        # Row Aggregates
        row_agg_cols = [
            func.sum(OwnerWiseOrderSummarySnapshot.ordered_pcs).label('ord_pcs'),
            func.sum(OwnerWiseOrderSummarySnapshot.ordered_wt).label('ord_wt'),
            func.sum(OwnerWiseOrderSummarySnapshot.accepted_pcs).label('acc_pcs'),
            func.sum(OwnerWiseOrderSummarySnapshot.accepted_wt).label('acc_wt'),
            func.sum(OwnerWiseOrderSummarySnapshot.rejected_pcs).label('rej_pcs'),
            func.sum(OwnerWiseOrderSummarySnapshot.rejected_wt).label('rej_wt'),
            func.sum(OwnerWiseOrderSummarySnapshot.barcoded_pcs).label('bar_pcs'),
            func.sum(OwnerWiseOrderSummarySnapshot.barcoded_wt).label('bar_wt'),
            func.sum(OwnerWiseOrderSummarySnapshot.hm_passed_pcs).label('hm_pcs'),
            func.sum(OwnerWiseOrderSummarySnapshot.hm_passed_wt).label('hm_wt'),
            func.sum(OwnerWiseOrderSummarySnapshot.qc_passed_pcs).label('qc_pcs'),
            func.sum(OwnerWiseOrderSummarySnapshot.qc_passed_wt).label('qc_wt'),
            func.sum(OwnerWiseOrderSummarySnapshot.invoiced_pcs).label('inv_pcs'),
            func.sum(OwnerWiseOrderSummarySnapshot.invoiced_wt).label('inv_wt'),
            func.sum(OwnerWiseOrderSummarySnapshot.delivered_pcs).label('del_pcs'),
            func.sum(OwnerWiseOrderSummarySnapshot.delivered_wt).label('del_wt'),
            func.sum(OwnerWiseOrderSummarySnapshot.pending_to_be_delv_pcs).label('pend_del_pcs'),
            func.sum(OwnerWiseOrderSummarySnapshot.pending_to_be_delv_wt).label('pend_del_wt')
        ]

        main_q = db.session.query(*(group_cols + row_agg_cols))
        main_q = apply_filters(main_q)
        main_q = main_q.group_by(*group_cols).order_by(*group_cols)
        
        pagination = main_q.paginate(page=page, per_page=per_page, error_out=False)
        
        processed_rows = []
        for r in pagination.items:
            row_dict = {
                'classification_owner': r[0] or 'Unknown',
                'make_owner': r[1] if level in ['make_owner', 'collection_owner'] else '',
                'collection_owner': r[2] if level == 'collection_owner' else '',
                'ord_pcs': int(r.ord_pcs or 0), 'ord_wt': float(r.ord_wt or 0),
                'acc_pcs': int(r.acc_pcs or 0), 'acc_wt': float(r.acc_wt or 0),
                'rej_pcs': int(r.rej_pcs or 0), 'rej_wt': float(r.rej_wt or 0),
                'bar_pcs': int(r.bar_pcs or 0), 'bar_wt': float(r.bar_wt or 0),
                'hm_pcs': int(r.hm_pcs or 0), 'hm_wt': float(r.hm_wt or 0),
                'qc_pcs': int(r.qc_pcs or 0), 'qc_wt': float(r.qc_wt or 0),
                'inv_pcs': int(r.inv_pcs or 0), 'inv_wt': float(r.inv_wt or 0),
                'del_pcs': int(r.del_pcs or 0), 'del_wt': float(r.del_wt or 0),
                'pend_del_pcs': int(r.pend_del_pcs or 0), 'pend_del_wt': float(r.pend_del_wt or 0),
                'level': level
            }
            processed_rows.append(row_dict)

        return render_template('owner_wise_order.html', 
                             unread_count=unread_count, 
                             sync_time=sync_time, 
                             stats=stats, 
                             rows=processed_rows, 
                             pagination=pagination, 
                             current_level=level,
                             filter_options=filter_options)
    except Exception as e:
        logger.error(f"Error in owner_wise_order_summary: {str(e)}")
        return f"Error: {str(e)}", 500

@dashboard_bp.route('/partial/ownerwise')
@jwt_required()
def get_owner_wise_partial():
    try:
        search = request.args.get('search', '').strip()
        division = request.args.get('division', '')
        group_name = request.args.get('group', '')
        purity = request.args.get('purity', '')
        supplier = request.args.get('supplier', '')
        classification_owner = request.args.get('classification_owner', '')
        collection_owner = request.args.get('collection_owner', '')
        make_owner = request.args.get('make_owner', '')
        classification = request.args.get('classification', '')
        
        parent_level = request.args.get('parent_level')
        parent_value = request.args.get('parent_value')
        grandparent_value = request.args.get('grandparent_value')

        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)
        
        is_child_rows = bool(parent_level)

        def apply_filters(query):
            if search:
                query = query.filter(
                    (OwnerWiseOrderSummarySnapshot.classification_owner.ilike(f"%{search}%")) |
                    (OwnerWiseOrderSummarySnapshot.collection_owner.ilike(f"%{search}%")) |
                    (OwnerWiseOrderSummarySnapshot.make_owner.ilike(f"%{search}%"))
                )
            if division:
                query = query.filter(OwnerWiseOrderSummarySnapshot.division == division)
            if group_name:
                query = query.filter(OwnerWiseOrderSummarySnapshot.group_name == group_name)
            if purity:
                query = query.filter(OwnerWiseOrderSummarySnapshot.purity == purity)
            if supplier:
                query = query.filter(OwnerWiseOrderSummarySnapshot.supplier == supplier)
            if classification_owner:
                query = query.filter(OwnerWiseOrderSummarySnapshot.classification_owner == classification_owner)
            if collection_owner:
                query = query.filter(OwnerWiseOrderSummarySnapshot.collection_owner == collection_owner)
            if make_owner:
                query = query.filter(OwnerWiseOrderSummarySnapshot.make_owner == make_owner)
            if classification:
                query = query.filter(OwnerWiseOrderSummarySnapshot.classification == classification)
            
            # User-based filtering: Restrict to make_owner = username if not admin
            if not session.get('is_admin', False) and session.get('username'):
                query = query.filter(OwnerWiseOrderSummarySnapshot.make_owner == session.get('username'))
                
            return query

        if parent_level == 'classification_owner':
            group_cols = [OwnerWiseOrderSummarySnapshot.classification_owner, OwnerWiseOrderSummarySnapshot.make_owner]
            level = 'make_owner'
            base_query = db.session.query(OwnerWiseOrderSummarySnapshot).filter(OwnerWiseOrderSummarySnapshot.classification_owner == parent_value)
        elif parent_level == 'make_owner':
            group_cols = [OwnerWiseOrderSummarySnapshot.classification_owner, OwnerWiseOrderSummarySnapshot.make_owner, OwnerWiseOrderSummarySnapshot.collection_owner]
            level = 'collection_owner'
            base_query = db.session.query(OwnerWiseOrderSummarySnapshot).filter(OwnerWiseOrderSummarySnapshot.make_owner == parent_value)
            if grandparent_value:
                 base_query = base_query.filter(OwnerWiseOrderSummarySnapshot.classification_owner == grandparent_value)
        else:
            base_query = db.session.query(OwnerWiseOrderSummarySnapshot)
            group_cols = [OwnerWiseOrderSummarySnapshot.classification_owner]
            level = 'classification_owner'

        row_agg_cols = [
            func.sum(OwnerWiseOrderSummarySnapshot.ordered_pcs).label('ord_pcs'),
            func.sum(OwnerWiseOrderSummarySnapshot.ordered_wt).label('ord_wt'),
            func.sum(OwnerWiseOrderSummarySnapshot.accepted_pcs).label('acc_pcs'),
            func.sum(OwnerWiseOrderSummarySnapshot.accepted_wt).label('acc_wt'),
            func.sum(OwnerWiseOrderSummarySnapshot.rejected_pcs).label('rej_pcs'),
            func.sum(OwnerWiseOrderSummarySnapshot.rejected_wt).label('rej_wt'),
            func.sum(OwnerWiseOrderSummarySnapshot.barcoded_pcs).label('bar_pcs'),
            func.sum(OwnerWiseOrderSummarySnapshot.barcoded_wt).label('bar_wt'),
            func.sum(OwnerWiseOrderSummarySnapshot.hm_passed_pcs).label('hm_pcs'),
            func.sum(OwnerWiseOrderSummarySnapshot.hm_passed_wt).label('hm_wt'),
            func.sum(OwnerWiseOrderSummarySnapshot.qc_passed_pcs).label('qc_pcs'),
            func.sum(OwnerWiseOrderSummarySnapshot.qc_passed_wt).label('qc_wt'),
            func.sum(OwnerWiseOrderSummarySnapshot.invoiced_pcs).label('inv_pcs'),
            func.sum(OwnerWiseOrderSummarySnapshot.invoiced_wt).label('inv_wt'),
            func.sum(OwnerWiseOrderSummarySnapshot.delivered_pcs).label('del_pcs'),
            func.sum(OwnerWiseOrderSummarySnapshot.delivered_wt).label('del_wt'),
            func.sum(OwnerWiseOrderSummarySnapshot.pending_to_be_delv_pcs).label('pend_del_pcs'),
            func.sum(OwnerWiseOrderSummarySnapshot.pending_to_be_delv_wt).label('pend_del_wt')
        ]

        main_q = base_query.with_entities(*(group_cols + row_agg_cols))
        main_q = apply_filters(main_q)
        main_q = main_q.group_by(*group_cols).order_by(*group_cols)
        
        pagination = main_q.paginate(page=page, per_page=per_page, error_out=False)

        processed_rows = []
        for r in pagination.items:
            row_dict = {
                'classification_owner': r[0] or 'Unknown',
                'make_owner': r[1] if level in ['make_owner', 'collection_owner'] else '',
                'collection_owner': r[2] if level == 'collection_owner' else '',
                'ord_pcs': int(r.ord_pcs or 0), 'ord_wt': float(r.ord_wt or 0),
                'acc_pcs': int(r.acc_pcs or 0), 'acc_wt': float(r.acc_wt or 0),
                'rej_pcs': int(r.rej_pcs or 0), 'rej_wt': float(r.rej_wt or 0),
                'bar_pcs': int(r.bar_pcs or 0), 'bar_wt': float(r.bar_wt or 0),
                'hm_pcs': int(r.hm_pcs or 0), 'hm_wt': float(r.hm_wt or 0),
                'qc_pcs': int(r.qc_pcs or 0), 'qc_wt': float(r.qc_wt or 0),
                'inv_pcs': int(r.inv_pcs or 0), 'inv_wt': float(r.inv_wt or 0),
                'del_pcs': int(r.del_pcs or 0), 'del_wt': float(r.del_wt or 0),
                'pend_del_pcs': int(r.pend_del_pcs or 0), 'pend_del_wt': float(r.pend_del_wt or 0),
                'level': level
            }
            processed_rows.append(row_dict)

        # Global Stats (Using Weights primarily)
        agg_cols = [
            func.sum(OwnerWiseOrderSummarySnapshot.ordered_pcs).label('total_ordered_pcs'),
            func.sum(OwnerWiseOrderSummarySnapshot.ordered_wt).label('total_ordered_wt'),
            func.sum(OwnerWiseOrderSummarySnapshot.accepted_pcs).label('total_accepted_pcs'),
            func.sum(OwnerWiseOrderSummarySnapshot.accepted_wt).label('total_accepted_wt'),
            func.sum(OwnerWiseOrderSummarySnapshot.rejected_pcs).label('total_rejected_pcs'),
            func.sum(OwnerWiseOrderSummarySnapshot.rejected_wt).label('total_rejected_wt'),
            func.sum(OwnerWiseOrderSummarySnapshot.barcoded_pcs).label('total_barcoded_pcs'),
            func.sum(OwnerWiseOrderSummarySnapshot.barcoded_wt).label('total_barcoded_wt'),
            func.sum(OwnerWiseOrderSummarySnapshot.hm_passed_pcs).label('total_hm_passed_pcs'),
            func.sum(OwnerWiseOrderSummarySnapshot.hm_passed_wt).label('total_hm_passed_wt'),
            func.sum(OwnerWiseOrderSummarySnapshot.qc_passed_pcs).label('total_qc_passed_pcs'),
            func.sum(OwnerWiseOrderSummarySnapshot.qc_passed_wt).label('total_qc_passed_wt'),
            func.sum(OwnerWiseOrderSummarySnapshot.invoiced_pcs).label('total_invoiced_pcs'),
            func.sum(OwnerWiseOrderSummarySnapshot.invoiced_wt).label('total_invoiced_wt'),
            func.sum(OwnerWiseOrderSummarySnapshot.delivered_pcs).label('total_delivered_pcs'),
            func.sum(OwnerWiseOrderSummarySnapshot.delivered_wt).label('total_delivered_wt'),
            func.sum(OwnerWiseOrderSummarySnapshot.pending_to_be_delv_pcs).label('total_pending_to_be_delv_pcs'),
            func.sum(OwnerWiseOrderSummarySnapshot.pending_to_be_delv_wt).label('total_pending_to_be_delv_wt')
        ]
        
        agg_q = db.session.query(*agg_cols)
        agg_q = apply_filters(agg_q)
        aggs = agg_q.first()

        total_wt = float(aggs.total_ordered_wt or 0)
        def get_perc(val):
            if total_wt <= 0: return 0
            return min(100, round((float(val or 0) / total_wt) * 100, 1))

        stats = {
            'ordered_wt': f"{float(aggs.total_ordered_wt or 0):,.3f}", 'ordered_pcs': f"{int(aggs.total_ordered_pcs or 0):,}",
            'accepted_wt': f"{float(aggs.total_accepted_wt or 0):,.3f}", 'accepted_pcs': f"{int(aggs.total_accepted_pcs or 0):,}", 'accepted_perc': get_perc(aggs.total_accepted_wt),
            'rejected_wt': f"{float(aggs.total_rejected_wt or 0):,.3f}", 'rejected_pcs': f"{int(aggs.total_rejected_pcs or 0):,}", 'rejected_perc': get_perc(aggs.total_rejected_wt),
            'barcoded_wt': f"{float(aggs.total_barcoded_wt or 0):,.3f}", 'barcoded_pcs': f"{int(aggs.total_barcoded_pcs or 0):,}", 'barcoded_perc': get_perc(aggs.total_barcoded_wt),
            'hallmarked_wt': f"{float(aggs.total_hm_passed_wt or 0):,.3f}", 'hallmarked_pcs': f"{int(aggs.total_hm_passed_pcs or 0):,}", 'hallmarked_perc': get_perc(aggs.total_hm_passed_wt),
            'qc_passed_wt': f"{float(aggs.total_qc_passed_wt or 0):,.3f}", 'qc_passed_pcs': f"{int(aggs.total_qc_passed_pcs or 0):,}", 'qc_passed_perc': get_perc(aggs.total_qc_passed_wt),
            'invoiced_wt': f"{float(aggs.total_invoiced_wt or 0):,.3f}", 'invoiced_pcs': f"{int(aggs.total_invoiced_pcs or 0):,}", 'invoiced_perc': get_perc(aggs.total_invoiced_wt),
            'delivered_wt': f"{float(aggs.total_delivered_wt or 0):,.3f}", 'delivered_pcs': f"{int(aggs.total_delivered_pcs or 0):,}", 'delivered_perc': get_perc(aggs.total_delivered_wt),
            'pending_to_be_delv_wt': f"{float(aggs.total_pending_to_be_delv_wt or 0):,.3f}", 'pending_to_be_delv_pcs': f"{int(aggs.total_pending_to_be_delv_pcs or 0):,}", 'pending_to_be_delv_perc': get_perc(aggs.total_pending_to_be_delv_wt)
        }

        return render_template('partials/_view_owner_wise.html', 
                             rows=processed_rows, 
                             pagination=pagination if not is_child_rows else None, 
                             current_level=level,
                             is_child_rows=is_child_rows,
                             parent_level=parent_level,
                             parent_value=parent_value,
                             stats=stats)
    except Exception as e:
        logger.error(f"Error in get_owner_wise_partial: {str(e)}")
        return f'<div class="p-8 text-center text-red-500 font-bold">Backend Error: {str(e)}</div>', 200
@dashboard_bp.route('/partial/leaf_detail')
@jwt_required()
def get_leaf_detail():
    try:
        # Get filters to identify the specific leaf node context
        classification_owner = request.args.get('classification_owner', '')
        make_owner = request.args.get('make_owner', '')
        collection_owner = request.args.get('collection_owner', '')
        
        query = db.session.query(OwnerWiseOrderSummarySnapshot)
        
        if classification_owner:
            query = query.filter(OwnerWiseOrderSummarySnapshot.classification_owner == classification_owner)
        if make_owner:
            query = query.filter(OwnerWiseOrderSummarySnapshot.make_owner == make_owner)
        if collection_owner:
            query = query.filter(OwnerWiseOrderSummarySnapshot.collection_owner == collection_owner)
            
        results = query.all()
        
        # Build the 8-level hierarchy
        # Supplier -> Division -> Group -> Purity -> Classification -> Make -> Collection -> Batch
        hierarchy = {}
        
        for r in results:
            s_val = r.supplier or 'Unknown'
            d_val = r.division or 'Unknown'
            g_val = r.group_name or 'Unknown'
            p_val = str(r.purity or 0)
            cl_val = r.classification or 'Unknown'
            m_val = r.make or 'Unknown'
            co_val = r.collection or 'Unknown'
            b_val = r.batch or 'Unknown'
            
            # Helper to navigate/create levels
            def get_or_create_node(parent, key, label):
                if key not in parent:
                    parent[key] = {
                        'label': label,
                        'children': {},
                        'metrics': {
                            'ord_pcs': 0, 'ord_wt': 0,
                            'acc_pcs': 0, 'acc_wt': 0,
                            'rej_pcs': 0, 'rej_wt': 0,
                            'bar_pcs': 0, 'bar_wt': 0,
                            'not_bar_pcs': 0, 'not_bar_wt': 0,
                            'hm_proc_pcs': 0, 'hm_pass_pcs': 0, 'hm_pass_wt': 0,
                            'hm_fail_pcs': 0, 'hm_fail_wt': 0,
                            'qc_proc_pcs': 0, 'qc_pass_pcs': 0, 'qc_pass_wt': 0,
                            'qc_pend_pcs': 0, 'qc_pend_wt': 0,
                            'qc_rej_pcs': 0, 'qc_rej_wt': 0,
                            'inv_pcs': 0, 'inv_wt': 0,
                            'del_pcs': 0, 'del_wt': 0,
                            'pend_del_pcs': 0, 'pend_del_wt': 0
                        }
                    }
                return parent[key]
            
            # Traverse levels
            node = get_or_create_node(hierarchy, s_val, s_val)
            node = get_or_create_node(node['children'], d_val, d_val)
            node = get_or_create_node(node['children'], g_val, g_val)
            node = get_or_create_node(node['children'], p_val, p_val)
            node = get_or_create_node(node['children'], cl_val, cl_val)
            node = get_or_create_node(node['children'], m_val, m_val)
            node = get_or_create_node(node['children'], co_val, co_val)
            node = get_or_create_node(node['children'], b_val, b_val)
            
            # At the leaf (batch) node, but we also need to aggregate backwards? 
            # Actually, easiest is to aggregate at EVERY node as we traverse.
            
            levels = []
            curr = hierarchy[s_val]
            levels.append(curr)
            curr = curr['children'][d_val]
            levels.append(curr)
            curr = curr['children'][g_val]
            levels.append(curr)
            curr = curr['children'][p_val]
            levels.append(curr)
            curr = curr['children'][cl_val]
            levels.append(curr)
            curr = curr['children'][m_val]
            levels.append(curr)
            curr = curr['children'][co_val]
            levels.append(curr)
            curr = curr['children'][b_val]
            levels.append(curr)
            
            for n in levels:
                m = n['metrics']
                m['ord_pcs'] += float(r.ordered_pcs or 0)
                m['ord_wt'] += float(r.ordered_wt or 0)
                m['acc_pcs'] += float(r.accepted_pcs or 0)
                m['acc_wt'] += float(r.accepted_wt or 0)
                m['rej_pcs'] += float(r.rejected_pcs or 0)
                m['rej_wt'] += float(r.rejected_wt or 0)
                m['bar_pcs'] += float(r.barcoded_pcs or 0)
                m['bar_wt'] += float(r.barcoded_wt or 0)
                m['not_bar_pcs'] += float(r.not_barcoded_pcs or 0)
                m['not_bar_wt'] += float(r.not_barcoded_wt or 0)
                m['hm_proc_pcs'] += float(r.hm_processed_pcs or 0)
                m['hm_pass_pcs'] += float(r.hm_passed_pcs or 0)
                m['hm_pass_wt'] += float(r.hm_passed_wt or 0)
                m['hm_fail_pcs'] += float(r.hm_failed_pcs or 0)
                m['hm_fail_wt'] += float(r.hm_failed_wt or 0)
                m['qc_proc_pcs'] += float(r.qc_processed_pcs or 0)
                m['qc_pass_pcs'] += float(r.qc_passed_pcs or 0)
                m['qc_pass_wt'] += float(r.qc_passed_wt or 0)
                m['qc_pend_pcs'] += float(r.qc_pending_pcs or 0)
                m['qc_pend_wt'] += float(r.qc_pending_wt or 0)
                m['qc_rej_pcs'] += float(r.qc_rejected_pcs or 0)
                m['qc_rej_wt'] += float(r.qc_rejected_wt or 0)
                m['inv_pcs'] += float(r.invoiced_pcs or 0)
                m['inv_wt'] += float(r.invoiced_wt or 0)
                m['del_pcs'] += float(r.delivered_pcs or 0)
                m['del_wt'] += float(r.delivered_wt or 0)
                m['pend_del_pcs'] += float(r.pending_to_be_delv_pcs or 0)
                m['pend_del_wt'] += float(r.pending_to_be_delv_wt or 0)

        # Convert nested dicts to sorted lists for template rendering
        def dict_to_list(d, level_idx):
            level_names = ['Supplier', 'Division', 'Group', 'Purity', 'Classification', 'Make', 'Collection', 'Batch']
            l = []
            for key, val in d.items():
                node = {
                    'label': val['label'],
                    'level_name': level_names[level_idx],
                    'metrics': val['metrics'],
                    'children': dict_to_list(val['children'], level_idx + 1) if level_idx < 7 else []
                }
                l.append(node)
            return sorted(l, key=lambda x: x['label'])

        # Calculate Grand Total
        grand_total = {
            'ord_pcs': 0, 'ord_wt': 0,
            'acc_pcs': 0, 'acc_wt': 0,
            'rej_pcs': 0, 'rej_wt': 0,
            'bar_pcs': 0, 'bar_wt': 0,
            'not_bar_pcs': 0, 'not_bar_wt': 0,
            'hm_proc_pcs': 0, 'hm_pass_pcs': 0, 'hm_pass_wt': 0,
            'hm_fail_pcs': 0, 'hm_fail_wt': 0,
            'qc_proc_pcs': 0, 'qc_pass_pcs': 0, 'qc_pass_wt': 0,
            'qc_pend_pcs': 0, 'qc_pend_wt': 0,
            'qc_rej_pcs': 0, 'qc_rej_wt': 0,
            'inv_pcs': 0, 'inv_wt': 0,
            'del_pcs': 0, 'del_wt': 0,
            'pend_del_pcs': 0, 'pend_del_wt': 0
        }

        for r in results:
            grand_total['ord_pcs'] += float(r.ordered_pcs or 0)
            grand_total['ord_wt'] += float(r.ordered_wt or 0)
            grand_total['acc_pcs'] += float(r.accepted_pcs or 0)
            grand_total['acc_wt'] += float(r.accepted_wt or 0)
            grand_total['rej_pcs'] += float(r.rejected_pcs or 0)
            grand_total['rej_wt'] += float(r.rejected_wt or 0)
            grand_total['bar_pcs'] += float(r.barcoded_pcs or 0)
            grand_total['bar_wt'] += float(r.barcoded_wt or 0)
            grand_total['not_bar_pcs'] += float(r.not_barcoded_pcs or 0)
            grand_total['not_bar_wt'] += float(r.not_barcoded_wt or 0)
            grand_total['hm_proc_pcs'] += float(r.hm_processed_pcs or 0)
            grand_total['hm_pass_pcs'] += float(r.hm_passed_pcs or 0)
            grand_total['hm_pass_wt'] += float(r.hm_passed_wt or 0)
            grand_total['hm_fail_pcs'] += float(r.hm_failed_pcs or 0)
            grand_total['hm_fail_wt'] += float(r.hm_failed_wt or 0)
            grand_total['qc_proc_pcs'] += float(r.qc_processed_pcs or 0)
            grand_total['qc_pass_pcs'] += float(r.qc_passed_pcs or 0)
            grand_total['qc_pass_wt'] += float(r.qc_passed_wt or 0)
            grand_total['qc_pend_pcs'] += float(r.qc_pending_pcs or 0)
            grand_total['qc_pend_wt'] += float(r.qc_pending_wt or 0)
            grand_total['qc_rej_pcs'] += float(r.qc_rejected_pcs or 0)
            grand_total['qc_rej_wt'] += float(r.qc_rejected_wt or 0)
            grand_total['inv_pcs'] += float(r.invoiced_pcs or 0)
            grand_total['inv_wt'] += float(r.invoiced_wt or 0)
            grand_total['del_pcs'] += float(r.delivered_pcs or 0)
            grand_total['del_wt'] += float(r.delivered_wt or 0)
            grand_total['pend_del_pcs'] += float(r.pending_to_be_delv_pcs or 0)
            grand_total['pend_del_wt'] += float(r.pending_to_be_delv_wt or 0)

        final_data = dict_to_list(hierarchy, 0)

        return render_template('partials/_owner_wise_order_detail.html', 
                             data=final_data, 
                             owner_name=collection_owner or make_owner or classification_owner,
                             grand_total=grand_total)
    except Exception as e:
        logger.error(f"Error in get_leaf_detail: {str(e)}")
        return f'<div class="p-8 text-center text-red-500 font-bold">Detail Error: {str(e)}</div>', 200
