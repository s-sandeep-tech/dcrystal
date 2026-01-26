from flask import Blueprint, render_template, redirect, url_for
from flask_jwt_extended import jwt_required
from app.models import Order, DashboardStats, Notification
from app.extensions import db
from datetime import datetime, timedelta
import time

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/')
def index():
    # Fetch stats (take the first record or create dummy)
    stats = DashboardStats.query.first()
    if not stats:
        stats = DashboardStats(
            active_orders=2840,
            critical_delay=142,
            sla_compliance=96.8,
            avg_response_time="1.4h"
        )
        db.session.add(stats)
        db.session.commit()

    # Fetch orders (ensure we have the full sample set for demo)
    if Order.query.count() != 5:
        # Clear existing if any to avoid duplicates or incomplete sets
        Order.query.delete()
        dummy_orders = [
            Order(
                order_id="#ORD-82910",
                priority="P1 - Urgent",
                collection_type="Winter Essentials",
                sub_type="Retail / High Volume",
                origin="NYC",
                destination="BER",
                risk_level=80,
                status="In Customs",
                sla_timer="04:22:10"
            ),
            Order(
                order_id="#ORD-82911",
                priority="P3 - Routine",
                collection_type="Spring Footwear",
                sub_type="Apparel / Standard",
                origin="SFO",
                destination="LON",
                risk_level=20,
                status="Cleared",
                sla_timer="00:00:00"
            ),
            Order(
                order_id="#ORD-82912",
                priority="P2 - High",
                collection_type="Summer Trends",
                sub_type="Fashion / Fast Moving",
                origin="PAR",
                destination="TOK",
                risk_level=55,
                status="Logistics",
                sla_timer="12:45:00"
            ),
            Order(
                order_id="#ORD-82913",
                priority="P1 - Urgent",
                collection_type="Tech Gadgets",
                sub_type="Electronics / Fragile",
                origin="SHZ",
                destination="LAX",
                risk_level=92,
                status="Manual Review",
                sla_timer="02:15:30"
            ),
            Order(
                order_id="#ORD-82914",
                priority="P3 - Routine",
                collection_type="Home Decor",
                sub_type="Furniture / Bulk",
                origin="HAM",
                destination="SYD",
                risk_level=15,
                status="Cleared",
                sla_timer="00:00:00"
            )
        ]
        db.session.add_all(dummy_orders)
        db.session.commit()
    
    orders = Order.query.all()

    # Initialize notifications if none exist
    if Notification.query.count() == 0:
        now = datetime.utcnow()
        dummy_notifications = [
            # Success notifications
            Notification(
                title="Order Cleared Successfully",
                message="Order #ORD-82911 has been cleared and is ready for shipment.",
                notification_type="success",
                icon="check_circle",
                priority="low",
                related_order_id="#ORD-82911",
                created_at=now - timedelta(minutes=2),
                is_read=False
            ),
            Notification(
                title="SLA Compliance Achieved",
                message="All orders in the EMEA region met SLA targets this hour.",
                notification_type="success",
                icon="verified",
                priority="medium",
                created_at=now - timedelta(hours=3),
                is_read=True
            ),
            # Warning notifications
            Notification(
                title="Customs Delay on #ORD-82910",
                message="Flagged for manual review in BER. Expected delay: 4-6 hours.",
                notification_type="warning",
                icon="warning",
                priority="high",
                related_order_id="#ORD-82910",
                created_at=now - timedelta(minutes=5),
                is_read=False
            ),
            Notification(
                title="Approaching SLA Deadline",
                message="Order #ORD-82912 has 2 hours remaining before SLA breach.",
                notification_type="warning",
                icon="schedule",
                priority="high",
                related_order_id="#ORD-82912",
                created_at=now - timedelta(minutes=45),
                is_read=False
            ),
            Notification(
                title="Weather Alert - Tokyo",
                message="Severe weather may impact deliveries to TOK region.",
                notification_type="warning",
                icon="cloud",
                priority="medium",
                created_at=now - timedelta(hours=2),
                is_read=True
            ),
            # Error notifications
            Notification(
                title="Manual Review Required",
                message="High risk profile detected on #ORD-82913. Immediate action needed.",
                notification_type="error",
                icon="error",
                priority="high",
                related_order_id="#ORD-82913",
                created_at=now - timedelta(minutes=15),
                is_read=False
            ),
            Notification(
                title="Critical SLA Breach",
                message="Order #ORD-82908 has exceeded SLA by 6 hours.",
                notification_type="error",
                icon="report_problem",
                priority="high",
                created_at=now - timedelta(hours=1),
                is_read=False
            ),
            # Info notifications
            Notification(
                title="System Update Completed",
                message="Dashboard analytics engine upgraded to v2.4.1.",
                notification_type="info",
                icon="info",
                priority="low",
                created_at=now - timedelta(hours=4),
                is_read=True
            ),
            Notification(
                title="Configuration Change",
                message="SLA threshold updated from 18h to 24h for bulk orders.",
                notification_type="info",
                icon="settings",
                priority="medium",
                created_at=now - timedelta(hours=1),
                is_read=True
            ),
            Notification(
                title="New Team Member Added",
                message="Sarah Johnson joined Compliance EMEA team.",
                notification_type="info",
                icon="person_add",
                priority="low",
                created_at=now - timedelta(hours=5),
                is_read=True
            ),
            # Alert notifications
            Notification(
                title="SLA Threshold Peak",
                message="APAC region experiencing response time bottleneck. 12 orders affected.",
                notification_type="alert",
                icon="notifications_active",
                priority="high",
                created_at=now - timedelta(minutes=30),
                is_read=False
            ),
            Notification(
                title="Unusual Activity Detected",
                message="Spike in manual review requests from SHZ origin (3x normal).",
                notification_type="alert",
                icon="security",
                priority="high",
                created_at=now - timedelta(hours=2),
                is_read=False
            ),
        ]
        db.session.add_all(dummy_notifications)
        db.session.commit()

    unread_count = Notification.query.filter_by(is_read=False).count()
    sync_time = datetime.now().strftime("%H:%M")

    return render_template('index.html', 
                         stats=stats, 
                         orders=orders, 
                         unread_count=unread_count,
                         sync_time=sync_time)

@dashboard_bp.route('/login')
def login():
    return render_template('login.html')

@dashboard_bp.route('/notifications/list')
@jwt_required()
def get_notifications_list():
    time.sleep(1) # Simulate network/processing delay
    notifications = Notification.query.order_by(Notification.created_at.desc()).limit(20).all()
    return render_template('partials/_notifications_list.html', notifications=notifications)

@dashboard_bp.route('/inventory')
def inventory():
    from app.models import Notification
    unread_count = Notification.query.filter_by(is_read=False).count()
    sync_time = datetime.now().strftime("%H:%M")
    return render_template('inventory.html', 
                         unread_count=unread_count,
                         sync_time=sync_time,
                         stats={},
                         rows=[],
                         pagination=None,
                         footer_totals={})

@dashboard_bp.route('/shortstatus')
def short_status():
    from flask import request
    from app.models import Notification, ShortStatusReportSnapshot
    from sqlalchemy import func
    
    unread_count = Notification.query.filter_by(is_read=False).count()
    sync_time = datetime.now().strftime("%H:%M")

    # Fetch latest snapshot date
    latest_date_query = db.session.query(func.max(ShortStatusReportSnapshot.snapshot_date)).scalar()
    
    if not latest_date_query:
        return render_template('short_status.html', 
                             unread_count=unread_count, 
                             sync_time=sync_time, 
                             stats={}, 
                             rows=[], 
                             pagination=None,
                             footer_totals={})

    return render_template('short_status.html',
                         unread_count=unread_count,
                         sync_time=sync_time,
                         stats={}, 
                         rows=[],
                         pagination=None,
                         footer_totals={})

@dashboard_bp.route('/shortstatus/partial')
@jwt_required()
def get_short_status_partial():
    from flask import request, jsonify
    from app.models import ShortStatusReportSnapshot
    from sqlalchemy import func

    latest_date_query = db.session.query(func.max(ShortStatusReportSnapshot.snapshot_date)).scalar()
    
    # Filters (mapping requested names to model columns)
    search = request.args.get('search', '').strip()
    division = request.args.get('division', '')
    group = request.args.get('group', '')
    purity = request.args.get('purity', '')
    classification = request.args.get('classification', '')
    make = request.args.get('make', '')
    collection = request.args.get('collection', '')
    section = request.args.get('section', '')
    product_type = request.args.get('product_type', '')

    def apply_filters(query):
        if search:
            query = query.filter(ShortStatusReportSnapshot.division.ilike(f"%{search}%") | 
                                 ShortStatusReportSnapshot.group_name.ilike(f"%{search}%") |
                                 ShortStatusReportSnapshot.classification.ilike(f"%{search}%"))
        if division:
            query = query.filter(ShortStatusReportSnapshot.division == division)
        if group:
            query = query.filter(ShortStatusReportSnapshot.group_name == group)
        if purity:
            query = query.filter(ShortStatusReportSnapshot.purity == purity)
        if classification:
            query = query.filter(ShortStatusReportSnapshot.classification == classification)
        if make:
            query = query.filter(ShortStatusReportSnapshot.make_location == make)
        if collection:
            query = query.filter(ShortStatusReportSnapshot.collection == collection)
        if section:
            query = query.filter(ShortStatusReportSnapshot.section == section)
        if product_type:
            query = query.filter(ShortStatusReportSnapshot.product_type == product_type)
        return query

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    
    pagination = None
    footer_totals = {}
    stats = {}
    
    if latest_date_query:
        # Global Stats for Short Status
        agg_q = db.session.query(
            func.sum(ShortStatusReportSnapshot.total_count).label('total_items'),
            func.sum(ShortStatusReportSnapshot.weight).label('total_weight'),
            func.count(ShortStatusReportSnapshot.product_type.distinct()).label('unique_products'),
            func.avg(ShortStatusReportSnapshot.weight).label('avg_weight')
        ).filter(ShortStatusReportSnapshot.snapshot_date == latest_date_query)
        agg_q = apply_filters(agg_q)
        aggs = agg_q.first()

        stats = {
            'total_items': f"{aggs.total_items or 0:,}",
            'total_weight': f"{round(aggs.total_weight or 0, 3)}",
            'unique_products': f"{aggs.unique_products or 0:,}",
            'avg_weight': f"{round(aggs.avg_weight or 0, 3)}"
        }

        # Footer Totals
        f_agg_q = db.session.query(
            func.sum(ShortStatusReportSnapshot.a_completed_count + ShortStatusReportSnapshot.a_pending_count).label('a'),
            func.sum(ShortStatusReportSnapshot.b_completed_count + ShortStatusReportSnapshot.b_pending_count).label('b'),
            func.sum(ShortStatusReportSnapshot.c_completed_count + ShortStatusReportSnapshot.c_pending_count).label('c'),
            func.sum(ShortStatusReportSnapshot.d_completed_count + ShortStatusReportSnapshot.d_pending_count).label('d'),
            func.sum(ShortStatusReportSnapshot.e_completed_count + ShortStatusReportSnapshot.e_pending_count).label('e'),
            func.sum(ShortStatusReportSnapshot.f_completed_count + ShortStatusReportSnapshot.f_pending_count).label('f'),
            func.sum(ShortStatusReportSnapshot.g_completed_count + ShortStatusReportSnapshot.g_pending_count).label('g'),
            func.sum(ShortStatusReportSnapshot.total_count).label('total')
        ).filter(ShortStatusReportSnapshot.snapshot_date == latest_date_query)
        f_agg_q = apply_filters(f_agg_q)
        f_agg = f_agg_q.first()

        footer_totals = {
            'a': f"{f_agg.a or 0:,}", 'b': f"{f_agg.b or 0:,}", 'c': f"{f_agg.c or 0:,}",
            'd': f"{f_agg.d or 0:,}", 'e': f"{f_agg.e or 0:,}", 'f': f"{f_agg.f or 0:,}",
            'g': f"{f_agg.g or 0:,}", 'total': f"{f_agg.total or 0:,}"
        }

        # Paginate
        main_q = ShortStatusReportSnapshot.query.filter_by(snapshot_date=latest_date_query)
        main_q = apply_filters(main_q)
        pagination = main_q.paginate(page=page, per_page=per_page, error_out=False)

    return render_template('partials/_view_shortstatus.html', 
                         rows=pagination.items if pagination else [], 
                         pagination=pagination, 
                         footer_totals=footer_totals,
                         stats=stats)

@dashboard_bp.route('/orderstatus')
def order_status():
    from flask import request
    from app.models import Notification, OrderStatusReportSnapshot
    from sqlalchemy import func
    
    unread_count = Notification.query.filter_by(is_read=False).count()
    sync_time = datetime.now().strftime("%H:%M")

    # Fetch latest snapshot date
    latest_date_query = db.session.query(func.max(OrderStatusReportSnapshot.snapshot_date)).scalar()
    
    if not latest_date_query:
        return render_template('order_status.html', 
                             unread_count=unread_count, 
                             sync_time=sync_time, 
                             stats={}, 
                             rows=[], 
                             pagination=None,
                             footer_totals={})

    # Filters
    search = request.args.get('search', '').strip()
    division = request.args.get('division', '')
    group = request.args.get('group', '')
    purity = request.args.get('purity', '')
    classification = request.args.get('classification', '')
    make = request.args.get('make', '')
    collection = request.args.get('collection', '')
    party = request.args.get('party', '')
    
    # New Owner Filters
    make_owner = request.args.get('make_owner', '')
    collection_owner = request.args.get('collection_owner', '')
    classification_owner = request.args.get('classification_owner', '')
    business_head = request.args.get('business_head', '')

    def apply_filters(query):
        if search:
            query = query.filter(OrderStatusReportSnapshot.hierarchy_key.ilike(f"%{search}%"))
        if division:
            query = query.filter(OrderStatusReportSnapshot.division == division)
        if group:
            query = query.filter(OrderStatusReportSnapshot.group_name == group)
        if purity:
            query = query.filter(OrderStatusReportSnapshot.purity == purity)
        if classification:
            query = query.filter(OrderStatusReportSnapshot.classification == classification)
        if make:
            query = query.filter(OrderStatusReportSnapshot.make_location == make)
        if collection:
            query = query.filter(OrderStatusReportSnapshot.collection == collection)
        if party:
            query = query.filter(OrderStatusReportSnapshot.party_name == party)
            
        # Apply New Owner Filters
        if make_owner:
            query = query.filter(OrderStatusReportSnapshot.make_owner == make_owner)
        if collection_owner:
            query = query.filter(OrderStatusReportSnapshot.collection_owner == collection_owner)
        if classification_owner:
            query = query.filter(OrderStatusReportSnapshot.classification_owner == classification_owner)
        if business_head:
            query = query.filter(OrderStatusReportSnapshot.business_head == business_head)
            
        return query

    # Global Stats
    agg_q = db.session.query(
        func.sum(OrderStatusReportSnapshot.total_count).label('total_orders'),
        func.sum(OrderStatusReportSnapshot.dispatched_count).label('dispatched'),
        func.sum(OrderStatusReportSnapshot.in_process_count).label('in_process'),
        func.sum(OrderStatusReportSnapshot.delayed_count).label('delayed'),
        func.sum(OrderStatusReportSnapshot.active_slots).label('active_slots'),
        func.avg(OrderStatusReportSnapshot.sla_index_pct).label('sla_index'),
        func.avg(OrderStatusReportSnapshot.avg_quality_score).label('quality_score'),
        func.avg(OrderStatusReportSnapshot.fulfillment_pct).label('fulfillment')
    ).filter(OrderStatusReportSnapshot.snapshot_date == latest_date_query)
    
    agg_q = apply_filters(agg_q)
    aggs = agg_q.first()

    stats = {
        'total_orders': f"{aggs.total_orders or 0:,}",
        'dispatched': f"{aggs.dispatched or 0:,}",
        'in_process': f"{aggs.in_process or 0:,}",
        'delayed': f"{aggs.delayed or 0:,}",
        'active_slots': f"{aggs.active_slots or 0:,}",
        'sla_index': f"{round(aggs.sla_index or 0, 1)}%",
        'quality_score': f"{round(aggs.quality_score or 0, 1)}/5",
        'fulfillment': f"{int(aggs.fulfillment or 0)}%"
    }

    # Footer Totals
    footer_q = db.session.query(
        func.sum(OrderStatusReportSnapshot.a_completed_count + OrderStatusReportSnapshot.a_pending_count).label('a'),
        func.sum(OrderStatusReportSnapshot.b_completed_count + OrderStatusReportSnapshot.b_pending_count).label('b'),
        func.sum(OrderStatusReportSnapshot.c_completed_count + OrderStatusReportSnapshot.c_pending_count).label('c'),
        func.sum(OrderStatusReportSnapshot.d_completed_count + OrderStatusReportSnapshot.d_pending_count).label('d'),
        func.sum(OrderStatusReportSnapshot.e_completed_count + OrderStatusReportSnapshot.e_pending_count).label('e'),
        func.sum(OrderStatusReportSnapshot.f_completed_count + OrderStatusReportSnapshot.f_pending_count).label('f'),
        func.sum(OrderStatusReportSnapshot.g_completed_count + OrderStatusReportSnapshot.g_pending_count).label('g'),
        func.sum(OrderStatusReportSnapshot.total_count).label('total')
    ).filter(OrderStatusReportSnapshot.snapshot_date == latest_date_query)
    
    footer_q = apply_filters(footer_q)
    footer_aggs = footer_q.first()

    footer_totals = {
        'a': f"{footer_aggs.a or 0:,}", 'b': f"{footer_aggs.b or 0:,}", 'c': f"{footer_aggs.c or 0:,}",
        'd': f"{footer_aggs.d or 0:,}", 'e': f"{footer_aggs.e or 0:,}", 'f': f"{footer_aggs.f or 0:,}",
        'g': f"{footer_aggs.g or 0:,}", 'total': f"{footer_aggs.total or 0:,}"
    }
    
    # Pagination
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    
    main_q = OrderStatusReportSnapshot.query.filter_by(snapshot_date=latest_date_query)
    main_q = apply_filters(main_q)
    
    pagination = main_q.paginate(page=page, per_page=per_page, error_out=False)
    
    return render_template('order_status.html', unread_count=unread_count, sync_time=sync_time, stats=stats, rows=pagination.items, pagination=pagination, footer_totals=footer_totals)

@dashboard_bp.route('/provisionstatus')
def provision_status():
    from flask import request
    from app.models import Notification, ShortStatusReportSnapshot
    from sqlalchemy import func
    
    unread_count = Notification.query.filter_by(is_read=False).count()
    sync_time = datetime.now().strftime("%H:%M")

    # Fetch latest snapshot date
    latest_date_query = db.session.query(func.max(ShortStatusReportSnapshot.snapshot_date)).scalar()
    
    if not latest_date_query:
        return render_template('provision_status.html', 
                             unread_count=unread_count, 
                             sync_time=sync_time, 
                             stats={}, 
                             rows=[], 
                             pagination=None,
                             footer_totals={})

    # Filters
    search = request.args.get('search', '').strip()
    division = request.args.get('division', '')
    group = request.args.get('group', '')
    purity = request.args.get('purity', '')
    classification = request.args.get('classification', '')
    make = request.args.get('make', '')
    collection = request.args.get('collection', '')
    section = request.args.get('section', '')
    product_type = request.args.get('product_type', '')

    def apply_filters(query):
        if search:
            query = query.filter(ShortStatusReportSnapshot.division.ilike(f"%{search}%") | 
                                 ShortStatusReportSnapshot.group_name.ilike(f"%{search}%") |
                                 ShortStatusReportSnapshot.classification.ilike(f"%{search}%"))
        if division:
            query = query.filter(ShortStatusReportSnapshot.division == division)
        if group:
            query = query.filter(ShortStatusReportSnapshot.group_name == group)
        if purity:
            query = query.filter(ShortStatusReportSnapshot.purity == purity)
        if classification:
            query = query.filter(ShortStatusReportSnapshot.classification == classification)
        if make:
            query = query.filter(ShortStatusReportSnapshot.make_location == make)
        if collection:
            query = query.filter(ShortStatusReportSnapshot.collection == collection)
        if section:
            query = query.filter(ShortStatusReportSnapshot.section == section)
        if product_type:
            query = query.filter(ShortStatusReportSnapshot.product_type == product_type)
        return query

    # Global Stats for Provision Status
    agg_q = db.session.query(
        func.sum(ShortStatusReportSnapshot.total_count).label('total_items'),
        func.sum(ShortStatusReportSnapshot.weight).label('total_weight'),
        func.count(ShortStatusReportSnapshot.product_type.distinct()).label('unique_products'),
        func.avg(ShortStatusReportSnapshot.weight).label('avg_weight')
    ).filter(ShortStatusReportSnapshot.snapshot_date == latest_date_query)
    
    agg_q = apply_filters(agg_q)
    aggs = agg_q.first()

    stats = {
        'total_items': f"{aggs.total_items or 0:,}",
        'total_weight': f"{round(aggs.total_weight or 0, 3)}",
        'unique_products': f"{aggs.unique_products or 0:,}",
        'avg_weight': f"{round(aggs.avg_weight or 0, 3)}"
    }

    # Footer Totals
    footer_q = db.session.query(
        func.sum(ShortStatusReportSnapshot.total_count).label('total')
    ).filter(ShortStatusReportSnapshot.snapshot_date == latest_date_query)
    
    footer_q = apply_filters(footer_q)
    footer_aggs = footer_q.first()

    footer_totals = {
        'total': f"{footer_aggs.total or 0:,}"
    }
    
    # Pagination
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    
    main_q = ShortStatusReportSnapshot.query.filter_by(snapshot_date=latest_date_query)
    main_q = apply_filters(main_q)
    
    pagination = main_q.paginate(page=page, per_page=per_page, error_out=False)
    
    return render_template('provision_status.html', 
                         unread_count=unread_count, 
                         sync_time=sync_time, 
                         stats=stats, 
                         rows=pagination.items if pagination else [], 
                         pagination=pagination, 
                         footer_totals=footer_totals)

@dashboard_bp.route('/partial/<view_type>')
@jwt_required()
def get_dashboard_partial(view_type):
    from flask import request, jsonify
    from app.models import OrderStatusReportSnapshot
    from sqlalchemy import func

    if view_type not in ['make', 'collection', 'party']:
        return "Invalid view type", 400
        
    latest_date_query = db.session.query(func.max(OrderStatusReportSnapshot.snapshot_date)).scalar()
    
    # Filters
    search = request.args.get('search', '').strip()
    division = request.args.get('division', '')
    group = request.args.get('group', '')
    purity = request.args.get('purity', '')
    classification = request.args.get('classification', '')
    make = request.args.get('make', '')
    collection = request.args.get('collection', '')
    party = request.args.get('party', '')
    
    # New Owner Filters
    make_owner = request.args.get('make_owner', '')
    collection_owner = request.args.get('collection_owner', '')
    classification_owner = request.args.get('classification_owner', '')
    business_head = request.args.get('business_head', '')

    def apply_filters(query):
        if search:
            query = query.filter(OrderStatusReportSnapshot.hierarchy_key.ilike(f"%{search}%"))
        if division:
            query = query.filter(OrderStatusReportSnapshot.division == division)
        if group:
            query = query.filter(OrderStatusReportSnapshot.group_name == group)
        if purity:
            query = query.filter(OrderStatusReportSnapshot.purity == purity)
        if classification:
            query = query.filter(OrderStatusReportSnapshot.classification == classification)
        if make:
            query = query.filter(OrderStatusReportSnapshot.make_location == make)
        if collection:
            query = query.filter(OrderStatusReportSnapshot.collection == collection)
        if party:
            query = query.filter(OrderStatusReportSnapshot.party_name == party)
            
        # Apply New Owner Filters
        if make_owner:
            query = query.filter(OrderStatusReportSnapshot.make_owner == make_owner)
        if collection_owner:
            query = query.filter(OrderStatusReportSnapshot.collection_owner == collection_owner)
        if classification_owner:
            query = query.filter(OrderStatusReportSnapshot.classification_owner == classification_owner)
        if business_head:
            query = query.filter(OrderStatusReportSnapshot.business_head == business_head)
            
        return query

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    
    pagination = None
    footer_totals = {}
    stats = {}
    
    if latest_date_query:
        # Global Stats (Updated for filters)
        agg_q = db.session.query(
            func.sum(OrderStatusReportSnapshot.total_count).label('total_orders'),
            func.sum(OrderStatusReportSnapshot.dispatched_count).label('dispatched'),
            func.sum(OrderStatusReportSnapshot.in_process_count).label('in_process'),
            func.sum(OrderStatusReportSnapshot.delayed_count).label('delayed'),
            func.sum(OrderStatusReportSnapshot.active_slots).label('active_slots'),
            func.avg(OrderStatusReportSnapshot.sla_index_pct).label('sla_index'),
            func.avg(OrderStatusReportSnapshot.avg_quality_score).label('quality_score'),
            func.avg(OrderStatusReportSnapshot.fulfillment_pct).label('fulfillment')
        ).filter(OrderStatusReportSnapshot.snapshot_date == latest_date_query)
        agg_q = apply_filters(agg_q)
        aggs = agg_q.first()

        stats = {
            'total_orders': f"{aggs.total_orders or 0:,}",
            'dispatched': f"{aggs.dispatched or 0:,}",
            'in_process': f"{aggs.in_process or 0:,}",
            'delayed': f"{aggs.delayed or 0:,}",
            'active_slots': f"{aggs.active_slots or 0:,}",
            'sla_index': f"{round(aggs.sla_index or 0, 1)}%",
            'quality_score': f"{round(aggs.quality_score or 0, 1)}/5",
            'fulfillment': f"{int(aggs.fulfillment or 0)}%"
        }

        # Footer Totals
        f_agg_q = db.session.query(
            func.sum(OrderStatusReportSnapshot.a_completed_count + OrderStatusReportSnapshot.a_pending_count).label('a'),
            func.sum(OrderStatusReportSnapshot.b_completed_count + OrderStatusReportSnapshot.b_pending_count).label('b'),
            func.sum(OrderStatusReportSnapshot.c_completed_count + OrderStatusReportSnapshot.c_pending_count).label('c'),
            func.sum(OrderStatusReportSnapshot.d_completed_count + OrderStatusReportSnapshot.d_pending_count).label('d'),
            func.sum(OrderStatusReportSnapshot.e_completed_count + OrderStatusReportSnapshot.e_pending_count).label('e'),
            func.sum(OrderStatusReportSnapshot.f_completed_count + OrderStatusReportSnapshot.f_pending_count).label('f'),
            func.sum(OrderStatusReportSnapshot.g_completed_count + OrderStatusReportSnapshot.g_pending_count).label('g'),
            func.sum(OrderStatusReportSnapshot.total_count).label('total')
        ).filter(OrderStatusReportSnapshot.snapshot_date == latest_date_query)
        f_agg_q = apply_filters(f_agg_q)
        f_agg = f_agg_q.first()

        footer_totals = {
            'a': f"{f_agg.a or 0:,}", 'b': f"{f_agg.b or 0:,}", 'c': f"{f_agg.c or 0:,}",
            'd': f"{f_agg.d or 0:,}", 'e': f"{f_agg.e or 0:,}", 'f': f"{f_agg.f or 0:,}",
            'g': f"{f_agg.g or 0:,}", 'total': f"{f_agg.total or 0:,}"
        }

        # Paginate
        main_q = OrderStatusReportSnapshot.query.filter_by(snapshot_date=latest_date_query)
        main_q = apply_filters(main_q)
        pagination = main_q.paginate(page=page, per_page=per_page, error_out=False)

    return render_template(f'partials/_view_{view_type}.html', 
                         rows=pagination.items if pagination else [], 
                         pagination=pagination, 
                         footer_totals=footer_totals,
                         stats=stats)

@dashboard_bp.route('/notify', methods=['POST'])
def create_notification():
    from flask import request, jsonify
    from app.extensions import socketio

    data = request.json
    try:
        notification = Notification(
            title=data.get('title'),
            message=data.get('message'),
            notification_type=data.get('type', 'info'),
            icon=data.get('icon', 'notifications'),
            priority=data.get('priority', 'low'),
            related_order_id=data.get('related_order_id'),
            created_at=datetime.utcnow(),
            is_read=False
        )
        db.session.add(notification)
        db.session.commit()

        # Emit to all connected clients
        socketio.emit('new_notification', {
            'id': notification.id,
            'title': notification.title,
            'message': notification.message,
            'type': notification.notification_type,
            'icon': notification.icon,
            'priority': notification.priority,
            'time': notification.get_time_ago(),
            'related_order_id': notification.related_order_id
        })

        return jsonify({'status': 'success', 'message': 'Notification created and broadcasted'}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500
