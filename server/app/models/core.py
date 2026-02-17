from app.extensions import db
from datetime import datetime

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
