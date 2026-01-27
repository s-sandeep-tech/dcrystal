from flask import render_template
from app.dashboard import dashboard_bp
from app.models import Order, DashboardStats, Notification
from app.extensions import db
from datetime import datetime, timedelta

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
