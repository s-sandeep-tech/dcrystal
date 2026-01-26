from app.extensions import db
from datetime import datetime
from passlib.hash import bcrypt

class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = bcrypt.hash(password)

    def check_password(self, password):
        return bcrypt.verify(password, self.password_hash)

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'created_at': self.created_at
        }

class Order(db.Model):
    __tablename__ = 'orders'

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.String(50), unique=True, nullable=False)
    priority = db.Column(db.String(50))
    collection_type = db.Column(db.String(100))
    sub_type = db.Column(db.String(100))
    origin = db.Column(db.String(50))
    destination = db.Column(db.String(50))
    risk_level = db.Column(db.Integer)  # Percentage
    status = db.Column(db.String(50))
    sla_timer = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'order_id': self.order_id,
            'priority': self.priority,
            'collection_type': self.collection_type,
            'sub_type': self.sub_type,
            'origin': self.origin,
            'destination': self.destination,
            'risk_level': self.risk_level,
            'status': self.status,
            'sla_timer': self.sla_timer
        }

class DashboardStats(db.Model):
    __tablename__ = 'dashboard_stats'

    id = db.Column(db.Integer, primary_key=True)
    active_orders = db.Column(db.Integer, default=0)
    critical_delay = db.Column(db.Integer, default=0)
    sla_compliance = db.Column(db.Float, default=0.0)
    avg_response_time = db.Column(db.String(20), default="0h")
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Notification(db.Model):
    __tablename__ = 'notifications'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.String(500), nullable=False)
    notification_type = db.Column(db.String(50), nullable=False)  # success, warning, error, info, alert
    icon = db.Column(db.String(50), nullable=False)  # Material icon name
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    priority = db.Column(db.String(20), default='medium')  # high, medium, low
    related_order_id = db.Column(db.String(50), db.ForeignKey('orders.order_id'), nullable=True)

    # Relationship to Order
    order = db.relationship('Order', backref='notifications', foreign_keys=[related_order_id])

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'message': self.message,
            'notification_type': self.notification_type,
            'icon': self.icon,
            'is_read': self.is_read,
            'created_at': self.created_at,
            'priority': self.priority,
            'related_order_id': self.related_order_id
        }
    

    def get_time_ago(self):
        """Return human-readable time difference"""
        diff = datetime.utcnow() - self.created_at
        seconds = diff.total_seconds()
        
        if seconds < 60:
            return "just now"
        elif seconds < 3600:
            minutes = int(seconds / 60)
            return f"{minutes}m ago"
        elif seconds < 86400:
            hours = int(seconds / 3600)
            return f"{hours}h ago"
        else:
            days = int(seconds / 86400)
            return f"{days}d ago"

class OrderStatusReportSnapshot(db.Model):
    __tablename__ = 'order_status_report_snapshot'

    snapshot_id = db.Column(db.BigInteger, primary_key=True)
    snapshot_date = db.Column(db.Date, nullable=False)
    division = db.Column(db.String(100))
    group_name = db.Column(db.String(100))
    purity = db.Column(db.String(50))
    classification = db.Column(db.String(150))
    make_location = db.Column(db.String(120))
    collection = db.Column(db.String(150))
    party_name = db.Column(db.String(200))
    
    # Owners
    make_owner = db.Column(db.String(100))
    collection_owner = db.Column(db.String(100))
    classification_owner = db.Column(db.String(100))
    business_head = db.Column(db.String(100))

    # Stage Counts (Completed and Pending for each stage)
    a_completed_count = db.Column(db.Integer, default=0, nullable=False)
    a_pending_count = db.Column(db.Integer, default=0, nullable=False)
    
    b_completed_count = db.Column(db.Integer, default=0, nullable=False)
    b_pending_count = db.Column(db.Integer, default=0, nullable=False)
    
    c_completed_count = db.Column(db.Integer, default=0, nullable=False)
    c_pending_count = db.Column(db.Integer, default=0, nullable=False)
    
    d_completed_count = db.Column(db.Integer, default=0, nullable=False)
    d_pending_count = db.Column(db.Integer, default=0, nullable=False)
    
    e_completed_count = db.Column(db.Integer, default=0, nullable=False)
    e_pending_count = db.Column(db.Integer, default=0, nullable=False)
    
    f_completed_count = db.Column(db.Integer, default=0, nullable=False)
    f_pending_count = db.Column(db.Integer, default=0, nullable=False)
    
    g_completed_count = db.Column(db.Integer, default=0, nullable=False)
    g_pending_count = db.Column(db.Integer, default=0, nullable=False)

    # Metrics
    total_count = db.Column(db.Integer, default=0, nullable=False)
    dispatched_count = db.Column(db.Integer, default=0, nullable=False)
    in_process_count = db.Column(db.Integer, default=0, nullable=False)
    delayed_count = db.Column(db.Integer, default=0, nullable=False)
    active_slots = db.Column(db.Integer, default=0, nullable=False)

    sla_index_pct = db.Column(db.Numeric(5, 2))
    avg_quality_score = db.Column(db.Numeric(3, 2))
    fulfillment_pct = db.Column(db.Numeric(5, 2))

    updated_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Note: Generated columns like hierarchy_key are not always directly supported by plain SQLAlchemy models
    # without specific dialect options or plain SQL execution. 
    # For simplicity in this ORM definition, we omit the generated column definition 
    # but the actual table creation via SQL will handle it if we run the provided SQL.
    # However, if we rely on db.create_all(), we need to approximate or skip the generated column 
    # or define it using DDL. 
    # For this task, we will create the table using the SQL provided by the user manually 
    # or via a script, so the model definition here is just for querying.

class ShortStatusReportSnapshot(db.Model):
    __tablename__ = 'short_status_report_snapshot'

    snapshot_id = db.Column(db.BigInteger, primary_key=True)
    snapshot_date = db.Column(db.Date, nullable=False)
    division = db.Column(db.String(100))
    group_name = db.Column(db.String(100))
    purity = db.Column(db.String(50))
    classification = db.Column(db.String(150))
    make_location = db.Column(db.String(120))
    collection = db.Column(db.String(150))
    section = db.Column(db.String(100))
    product_type = db.Column(db.String(100))
    weight = db.Column(db.Numeric(10, 3))
    
    # Stage Counts (Standard stages A-G)
    a_completed_count = db.Column(db.Integer, default=0, nullable=False)
    a_pending_count = db.Column(db.Integer, default=0, nullable=False)
    b_completed_count = db.Column(db.Integer, default=0, nullable=False)
    b_pending_count = db.Column(db.Integer, default=0, nullable=False)
    c_completed_count = db.Column(db.Integer, default=0, nullable=False)
    c_pending_count = db.Column(db.Integer, default=0, nullable=False)
    d_completed_count = db.Column(db.Integer, default=0, nullable=False)
    d_pending_count = db.Column(db.Integer, default=0, nullable=False)
    e_completed_count = db.Column(db.Integer, default=0, nullable=False)
    e_pending_count = db.Column(db.Integer, default=0, nullable=False)
    f_completed_count = db.Column(db.Integer, default=0, nullable=False)
    f_pending_count = db.Column(db.Integer, default=0, nullable=False)
    g_completed_count = db.Column(db.Integer, default=0, nullable=False)
    g_pending_count = db.Column(db.Integer, default=0, nullable=False)

    total_count = db.Column(db.Integer, default=0, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self):
        return {
            'snapshot_id': self.snapshot_id,
            'division': self.division,
            'group_name': self.group_name,
            'purity': self.purity,
            'classification': self.classification,
            'make_location': self.make_location,
            'collection': self.collection,
            'section': self.section,
            'product_type': self.product_type,
            'weight': float(self.weight or 0),
            'total_count': self.total_count,
            'a': self.a_completed_count + self.a_pending_count,
            'b': self.b_completed_count + self.b_pending_count,
            'c': self.c_completed_count + self.c_pending_count,
            'd': self.d_completed_count + self.d_pending_count,
            'e': self.e_completed_count + self.e_pending_count,
            'f': self.f_completed_count + self.f_pending_count,
            'g': self.g_completed_count + self.g_pending_count
        }
