from flask import render_template, request, jsonify, session
from flask_jwt_extended import get_jwt_identity, jwt_required
from app.dashboard import dashboard_bp
from app.models import Notification, PartyDesignAverageDeliveryDaysSnapshot
from app.extensions import db
from sqlalchemy import asc, desc, distinct, func
from datetime import datetime
from zoneinfo import ZoneInfo
import logging

logger = logging.getLogger(__name__)


def split_filter_values(value):
    return [v.strip() for v in (value or '').split(',') if v.strip()]


def apply_multi_filter(query, column, value):
    values = split_filter_values(value)
    if not values:
        return query
    if len(values) == 1:
        return query.filter(column == values[0])
    return query.filter(column.in_(values))


def get_sort_params():
    allowed_columns = {
        'hierarchy',
        'design_count',
        'avg_delivery_days',
    }
    sort_by = request.args.get('sort_by', 'hierarchy').strip().lower()
    sort_dir = request.args.get('sort_dir', 'asc').strip().lower()
    return (
        sort_by if sort_by in allowed_columns else 'hierarchy',
        sort_dir if sort_dir in {'asc', 'desc'} else 'asc',
    )


def apply_sort(query, group_cols, sort_by, sort_dir):
    model = PartyDesignAverageDeliveryDaysSnapshot
    design_count = func.count(distinct(model.design_id))
    sort_columns = {
        'design_count': design_count,
        'avg_delivery_days': func.avg(model.average_delivery_days),
    }
    sort_target = sort_columns.get(sort_by, group_cols[-1])
    sort_expression = desc(sort_target) if sort_dir == 'desc' else asc(sort_target)
    return query.order_by(
        sort_expression,
        *[asc(column) for column in group_cols],
    )


@dashboard_bp.route('/party-design-delivery-performance')
def party_design_delivery_performance():
    try:
        unread_count = Notification.query.filter_by(is_read=False).count()
        sync_time = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%I:%M %p")

        # Filters
        search = request.args.get('search', '').strip()
        party = request.args.get('party', '')
        make_owner = request.args.get('make_owner', '')
        make = request.args.get('make', '')
        classification = request.args.get('classification', '')
        sub_classification = request.args.get('sub_classification', '')
        order_type = request.args.get('order_type', '')
        provision_type = request.args.get('provision_type', '')
        sort_by, sort_dir = get_sort_params()

        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)

        def apply_filters(query):
            if search:
                query = query.filter(
                    (PartyDesignAverageDeliveryDaysSnapshot.party.ilike(f"%{search}%")) |
                    (PartyDesignAverageDeliveryDaysSnapshot.make_owner.ilike(f"%{search}%")) |
                    (PartyDesignAverageDeliveryDaysSnapshot.make.ilike(f"%{search}%")) |
                    (PartyDesignAverageDeliveryDaysSnapshot.classification.ilike(f"%{search}%")) |
                    (PartyDesignAverageDeliveryDaysSnapshot.sub_classification.ilike(f"%{search}%"))
                )
            query = apply_multi_filter(query, PartyDesignAverageDeliveryDaysSnapshot.party, party)
            query = apply_multi_filter(query, PartyDesignAverageDeliveryDaysSnapshot.make_owner, make_owner)
            query = apply_multi_filter(query, PartyDesignAverageDeliveryDaysSnapshot.make, make)
            query = apply_multi_filter(query, PartyDesignAverageDeliveryDaysSnapshot.classification, classification)
            query = apply_multi_filter(query, PartyDesignAverageDeliveryDaysSnapshot.sub_classification, sub_classification)
            query = apply_multi_filter(query, PartyDesignAverageDeliveryDaysSnapshot.order_type, order_type)
            query = apply_multi_filter(query, PartyDesignAverageDeliveryDaysSnapshot.provision_type, provision_type)
            return query

        def get_options(column):
            return [
                r[0] for r in db.session.query(column)
                .filter(column.isnot(None), column != '')
                .distinct().order_by(column).all()
                if r[0]
            ]

        filter_options = {
            'parties': get_options(PartyDesignAverageDeliveryDaysSnapshot.party),
            'make_owners': get_options(PartyDesignAverageDeliveryDaysSnapshot.make_owner),
            'makes': get_options(PartyDesignAverageDeliveryDaysSnapshot.make),
            'classifications': get_options(PartyDesignAverageDeliveryDaysSnapshot.classification),
            'sub_classifications': get_options(PartyDesignAverageDeliveryDaysSnapshot.sub_classification),
            'order_types': get_options(PartyDesignAverageDeliveryDaysSnapshot.order_type),
            'provision_types': get_options(PartyDesignAverageDeliveryDaysSnapshot.provision_type),
        }

        # Overall Grand Stats
        total_filtered_designs_q = db.session.query(
            func.count(distinct(PartyDesignAverageDeliveryDaysSnapshot.design_id)).label('total_designs'),
            func.count(distinct(PartyDesignAverageDeliveryDaysSnapshot.party)).label('total_parties'),
            func.count(distinct(PartyDesignAverageDeliveryDaysSnapshot.make)).label('total_makes'),
            func.avg(PartyDesignAverageDeliveryDaysSnapshot.average_delivery_days).label('avg_delivery_days')
        )
        total_filtered_designs_q = apply_filters(total_filtered_designs_q)
        overall_stats = total_filtered_designs_q.first()

        grand_total_designs = int(overall_stats.total_designs or 0)
        grand_total_parties = int(overall_stats.total_parties or 0)
        grand_total_makes = int(overall_stats.total_makes or 0)
        grand_avg_delivery_days = float(overall_stats.avg_delivery_days or 0.0)

        stats = {
            'total_designs': f"{grand_total_designs:,}",
            'total_parties': f"{grand_total_parties:,}",
            'total_makes': f"{grand_total_makes:,}",
            'avg_delivery_days': f"{grand_avg_delivery_days:.1f}"
        }

        # Determine level hierarchy
        if not party:
            group_cols = [PartyDesignAverageDeliveryDaysSnapshot.party]
            level = 'party'
        elif party and not make:
            group_cols = [
                PartyDesignAverageDeliveryDaysSnapshot.party,
                PartyDesignAverageDeliveryDaysSnapshot.make,
                PartyDesignAverageDeliveryDaysSnapshot.make_owner
            ]
            level = 'make'
        elif party and make and not classification:
            group_cols = [
                PartyDesignAverageDeliveryDaysSnapshot.party,
                PartyDesignAverageDeliveryDaysSnapshot.make,
                PartyDesignAverageDeliveryDaysSnapshot.make_owner,
                PartyDesignAverageDeliveryDaysSnapshot.classification
            ]
            level = 'classification'
        else:
            group_cols = [
                PartyDesignAverageDeliveryDaysSnapshot.party,
                PartyDesignAverageDeliveryDaysSnapshot.make,
                PartyDesignAverageDeliveryDaysSnapshot.make_owner,
                PartyDesignAverageDeliveryDaysSnapshot.classification,
                PartyDesignAverageDeliveryDaysSnapshot.sub_classification
            ]
            level = 'sub_classification'

        main_q = db.session.query(
            *group_cols,
            func.count(distinct(PartyDesignAverageDeliveryDaysSnapshot.design_id)).label('design_count'),
            func.avg(PartyDesignAverageDeliveryDaysSnapshot.average_delivery_days).label('avg_delivery_days')
        )
        main_q = apply_filters(main_q)
        main_q = main_q.group_by(*group_cols)
        main_q = apply_sort(main_q, group_cols, sort_by, sort_dir)

        pagination = main_q.paginate(page=page, per_page=per_page, error_out=False)

        processed_rows = []
        for r in pagination.items:
            design_count = int(r.design_count or 0)
            count_pct = (design_count / grand_total_designs * 100) if grand_total_designs > 0 else 0.0
            avg_days = float(r.avg_delivery_days or 0.0)

            row_dict = {
                'party': r[0] if len(r) > 0 else '',
                'make': r[1] if level in ['make', 'classification', 'sub_classification'] else '',
                'make_owner': r[2] if level in ['make', 'classification', 'sub_classification'] else '',
                'classification': r[3] if level in ['classification', 'sub_classification'] else '',
                'sub_classification': r[4] if level == 'sub_classification' else '',
                'design_count': design_count,
                'design_count_pct': count_pct,
                'avg_delivery_days': avg_days,
                'level': level
            }
            processed_rows.append(row_dict)

        return render_template('party_design_delivery_performance.html',
                             unread_count=unread_count,
                             sync_time=sync_time,
                             stats=stats,
                             rows=processed_rows,
                             pagination=pagination,
                             current_level=level,
                             sort_by=sort_by,
                             sort_dir=sort_dir,
                             filter_options=filter_options)
    except Exception as e:
        logger.error(f"Error in party_design_delivery_performance: {str(e)}")
        return f"Error: {str(e)}", 500


@dashboard_bp.route('/partial/party-design-delivery-performance')
@jwt_required()
def get_party_design_delivery_performance_partial():
    try:
        search = request.args.get('search', '').strip()
        party = request.args.get('party', '')
        make_owner = request.args.get('make_owner', '')
        make = request.args.get('make', '')
        classification = request.args.get('classification', '')
        sub_classification = request.args.get('sub_classification', '')
        order_type = request.args.get('order_type', '')
        provision_type = request.args.get('provision_type', '')
        sort_by, sort_dir = get_sort_params()

        parent_party = request.args.get('parent_party', '')
        parent_make = request.args.get('parent_make', '')
        parent_classification = request.args.get('parent_classification', '')

        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)
        target_level = request.args.get('target_level', '')
        is_child_rows = request.args.get('is_child_rows', 'false') == 'true'

        def apply_filters(query):
            if search:
                query = query.filter(
                    (PartyDesignAverageDeliveryDaysSnapshot.party.ilike(f"%{search}%")) |
                    (PartyDesignAverageDeliveryDaysSnapshot.make_owner.ilike(f"%{search}%")) |
                    (PartyDesignAverageDeliveryDaysSnapshot.make.ilike(f"%{search}%")) |
                    (PartyDesignAverageDeliveryDaysSnapshot.classification.ilike(f"%{search}%")) |
                    (PartyDesignAverageDeliveryDaysSnapshot.sub_classification.ilike(f"%{search}%"))
                )
            query = apply_multi_filter(query, PartyDesignAverageDeliveryDaysSnapshot.party, party)
            query = apply_multi_filter(query, PartyDesignAverageDeliveryDaysSnapshot.make_owner, make_owner)
            query = apply_multi_filter(query, PartyDesignAverageDeliveryDaysSnapshot.make, make)
            query = apply_multi_filter(query, PartyDesignAverageDeliveryDaysSnapshot.classification, classification)
            query = apply_multi_filter(query, PartyDesignAverageDeliveryDaysSnapshot.sub_classification, sub_classification)
            query = apply_multi_filter(query, PartyDesignAverageDeliveryDaysSnapshot.order_type, order_type)
            query = apply_multi_filter(query, PartyDesignAverageDeliveryDaysSnapshot.provision_type, provision_type)
            return query

        # Overall Grand Stats for percentage calculations
        total_filtered_designs_q = db.session.query(
            func.count(distinct(PartyDesignAverageDeliveryDaysSnapshot.design_id)).label('total_designs'),
            func.count(distinct(PartyDesignAverageDeliveryDaysSnapshot.party)).label('total_parties'),
            func.count(distinct(PartyDesignAverageDeliveryDaysSnapshot.make)).label('total_makes'),
            func.avg(PartyDesignAverageDeliveryDaysSnapshot.average_delivery_days).label('avg_delivery_days')
        )
        total_filtered_designs_q = apply_filters(total_filtered_designs_q)
        overall_stats = total_filtered_designs_q.first()

        grand_total_designs = int(overall_stats.total_designs or 0)
        grand_total_parties = int(overall_stats.total_parties or 0)
        grand_total_makes = int(overall_stats.total_makes or 0)
        grand_avg_delivery_days = float(overall_stats.avg_delivery_days or 0.0)

        stats = {
            'total_designs': f"{grand_total_designs:,}",
            'total_parties': f"{grand_total_parties:,}",
            'total_makes': f"{grand_total_makes:,}",
            'avg_delivery_days': f"{grand_avg_delivery_days:.1f}"
        }

        # Hierarchy level logic
        if target_level:
            level = target_level
        elif parent_classification and parent_make and parent_party:
            level = 'sub_classification'
        elif parent_make and parent_party:
            level = 'classification'
        elif parent_party:
            level = 'make'
        elif not party:
            level = 'party'
        elif party and not make:
            level = 'make'
        elif party and make and not classification:
            level = 'classification'
        else:
            level = 'sub_classification'

        if level == 'party':
            group_cols = [PartyDesignAverageDeliveryDaysSnapshot.party]
        elif level == 'make':
            group_cols = [
                PartyDesignAverageDeliveryDaysSnapshot.party,
                PartyDesignAverageDeliveryDaysSnapshot.make,
                PartyDesignAverageDeliveryDaysSnapshot.make_owner
            ]
        elif level == 'classification':
            group_cols = [
                PartyDesignAverageDeliveryDaysSnapshot.party,
                PartyDesignAverageDeliveryDaysSnapshot.make,
                PartyDesignAverageDeliveryDaysSnapshot.make_owner,
                PartyDesignAverageDeliveryDaysSnapshot.classification
            ]
        else:
            group_cols = [
                PartyDesignAverageDeliveryDaysSnapshot.party,
                PartyDesignAverageDeliveryDaysSnapshot.make,
                PartyDesignAverageDeliveryDaysSnapshot.make_owner,
                PartyDesignAverageDeliveryDaysSnapshot.classification,
                PartyDesignAverageDeliveryDaysSnapshot.sub_classification
            ]

        main_q = db.session.query(
            *group_cols,
            func.count(distinct(PartyDesignAverageDeliveryDaysSnapshot.design_id)).label('design_count'),
            func.avg(PartyDesignAverageDeliveryDaysSnapshot.average_delivery_days).label('avg_delivery_days')
        )
        main_q = apply_filters(main_q)

        if parent_party:
            main_q = main_q.filter(PartyDesignAverageDeliveryDaysSnapshot.party == parent_party)
        if parent_make:
            main_q = main_q.filter(PartyDesignAverageDeliveryDaysSnapshot.make == parent_make)
        if parent_classification:
            main_q = main_q.filter(PartyDesignAverageDeliveryDaysSnapshot.classification == parent_classification)

        main_q = main_q.group_by(*group_cols)
        main_q = apply_sort(main_q, group_cols, sort_by, sort_dir)

        if is_child_rows:
            items = main_q.all()
            pagination = None
        else:
            pagination = main_q.paginate(page=page, per_page=per_page, error_out=False)
            items = pagination.items

        processed_rows = []
        for r in items:
            design_count = int(r.design_count or 0)
            count_pct = (design_count / grand_total_designs * 100) if grand_total_designs > 0 else 0.0
            avg_days = float(r.avg_delivery_days or 0.0)

            row_dict = {
                'party': r[0] if len(r) > 0 else '',
                'make': r[1] if level in ['make', 'classification', 'sub_classification'] else '',
                'make_owner': r[2] if level in ['make', 'classification', 'sub_classification'] else '',
                'classification': r[3] if level in ['classification', 'sub_classification'] else '',
                'sub_classification': r[4] if level == 'sub_classification' else '',
                'design_count': design_count,
                'design_count_pct': count_pct,
                'avg_delivery_days': avg_days,
                'level': level
            }
            processed_rows.append(row_dict)

        return render_template('partials/_view_party_design_delivery_performance.html',
                             rows=processed_rows,
                             pagination=pagination,
                             stats=stats,
                             current_level=level,
                             sort_by=sort_by,
                             sort_dir=sort_dir,
                             is_child_rows=is_child_rows)
    except Exception as e:
        logger.error(f"Error in get_party_design_delivery_performance_partial: {str(e)}")
        return f'<div class="p-4 text-red-500">Error: {str(e)}</div>', 500


@dashboard_bp.route('/api/party-design-delivery-performance/options')
@jwt_required()
def get_party_design_delivery_performance_options():
    try:
        def get_opts(column):
            return [
                r[0] for r in db.session.query(column)
                .filter(column.isnot(None), column != '')
                .distinct().order_by(column).all()
                if r[0]
            ]

        return jsonify({
            'status': 'success',
            'options': {
                'parties': get_opts(PartyDesignAverageDeliveryDaysSnapshot.party),
                'make_owners': get_opts(PartyDesignAverageDeliveryDaysSnapshot.make_owner),
                'makes': get_opts(PartyDesignAverageDeliveryDaysSnapshot.make),
                'classifications': get_opts(PartyDesignAverageDeliveryDaysSnapshot.classification),
                'sub_classifications': get_opts(PartyDesignAverageDeliveryDaysSnapshot.sub_classification),
                'order_types': get_opts(PartyDesignAverageDeliveryDaysSnapshot.order_type),
                'provision_types': get_opts(PartyDesignAverageDeliveryDaysSnapshot.provision_type),
            }
        })
    except Exception as e:
        logger.error(f"Error fetching party_design_delivery_performance options: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500
