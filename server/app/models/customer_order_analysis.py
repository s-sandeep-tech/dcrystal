import os
from datetime import datetime, date
from app.extensions import db


class CustomerOrderAnalysisSnapshot(db.Model):
    """
    SQLAlchemy model representing the local snapshot table customer_order_analysis_snapshot.
    Stores data synced from ext_view.vw_customer_order.
    """
    __tablename__ = 'customer_order_analysis_snapshot'
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # Order identifiers
    request_no = db.Column('request_no', db.Text, index=True, nullable=True)
    sooc = db.Column('sooc', db.Text, nullable=True)

    # Location & Organizational Hierarchy
    state = db.Column('state', db.String(50), nullable=True)
    location = db.Column('location', db.String(100), index=True, nullable=True)
    request_date = db.Column('request_date', db.Date, nullable=True)
    request_type = db.Column('request_type', db.Text, nullable=True)
    division = db.Column('division', db.String(50), nullable=True)
    group_category = db.Column('group_category', db.String(50), nullable=True)
    group = db.Column('group', db.String(50), nullable=True)
    classification = db.Column('classification', db.String(50), nullable=True)
    sub_classification = db.Column('sub_classification', db.String(50), nullable=True)
    make = db.Column('make', db.String(50), index=True, nullable=True)
    section = db.Column('section', db.String(50), index=True, nullable=True)
    collection = db.Column('collection', db.String(50), nullable=True)
    purity = db.Column('purity', db.Text, nullable=True)
    gender = db.Column('gender', db.String(200), nullable=True)

    # Product Weights & Spec
    weight = db.Column('weight', db.Numeric(18, 3), nullable=True)
    size = db.Column('size', db.Text, nullable=True)
    gross_weight = db.Column('gross_weight', db.Numeric(18, 3), nullable=True)
    stone_weight = db.Column('stone_weight', db.Numeric(18, 3), nullable=True)
    other_weight = db.Column('other_weight', db.Numeric(18, 3), nullable=True)
    net_weight = db.Column('net_weight', db.Numeric(18, 3), nullable=True)

    # Advance & Order Info
    advance_no = db.Column('advance_no', db.Text, nullable=True)
    advance_date = db.Column('advance_date', db.DateTime, nullable=True)
    party_name = db.Column('party_name', db.String(150), index=True, nullable=True)
    party_code = db.Column('party_code', db.Text, nullable=True)
    party_type = db.Column('party_type', db.Text, nullable=True)
    customer_name = db.Column('customer_name', db.Text, nullable=True)
    customer_phone_number = db.Column('customer_phone_number', db.Text, nullable=True)
    order_status = db.Column('order_status', db.Text, nullable=True)
    expected_delivery_date = db.Column('expected_delivery_date', db.DateTime, nullable=True)

    # Ownership & Management
    classification_owner = db.Column('classification_owner', db.String, nullable=True)
    make_owner = db.Column('make_owner', db.String, nullable=True)
    collection_wner = db.Column('collection_wner', db.String, nullable=True)
    shop_manger = db.Column('shop_manger', db.Text, nullable=True)
    customer_order_type = db.Column('customer_order_type', db.Text, nullable=True)
    branch_type = db.Column('branch_type', db.Text, nullable=True)
    is_msme = db.Column('is_msme', db.Boolean, nullable=True)
    re_order = db.Column('re_order', db.Boolean, nullable=True)
    order_ro = db.Column('order_ro', db.String(250), nullable=True)

    # Employee Codes
    collection_owner_emp_code = db.Column('collection_owner_emp_code', db.String(256), nullable=True)
    make_owner_emp_code = db.Column('make_owner_emp_code', db.String(256), nullable=True)
    classification_owner_emp_code = db.Column('classification_owner_emp_code', db.String(256), nullable=True)
    business_head_name = db.Column('business_head_name', db.Text, nullable=True)
    bh_emp_code = db.Column('bh_emp_code', db.String(256), nullable=True)

    # Stage Pending Metrics
    pending_to_accepted_pcs = db.Column('pending_to_accepted_pcs', db.BigInteger, nullable=True, default=0)
    pending_to_accepted_wt = db.Column('pending_to_accepted_wt', db.Numeric(18, 3), nullable=True, default=0)
    process_pending_pcs = db.Column('process_pending_pcs', db.BigInteger, nullable=True, default=0)
    process_pending_wt = db.Column('process_pending_wt', db.Numeric(18, 3), nullable=True, default=0)
    barcode_pending_pcs = db.Column('barcode_pending_pcs', db.BigInteger, nullable=True, default=0)
    barcode_pending_wt = db.Column('barcode_pending_wt', db.Numeric(18, 3), nullable=True, default=0)
    hallmark_pending_pcs = db.Column('hallmark_pending_pcs', db.BigInteger, nullable=True, default=0)
    hallmark_pending_wt = db.Column('hallmark_pending_wt', db.Numeric(18, 3), nullable=True, default=0)
    qc_issue_pending_pcs = db.Column('qc_issue_pending_pcs', db.BigInteger, nullable=True, default=0)
    qc_issue_pending_wt = db.Column('qc_issue_pending_wt', db.Numeric(18, 3), nullable=True, default=0)
    qc_complete_pending_pcs = db.Column('qc_complete_pending_pcs', db.BigInteger, nullable=True, default=0)
    qc_complete_pending_wt = db.Column('qc_complete_pending_wt', db.Numeric(18, 3), nullable=True, default=0)
    invoice_pending_pcs = db.Column('invoice_pending_pcs', db.BigInteger, nullable=True, default=0)
    invoice_pending_wt = db.Column('invoice_pending_wt', db.Numeric(18, 3), nullable=True, default=0)
    receipt_pending_pcs = db.Column('receipt_pending_pcs', db.BigInteger, nullable=True, default=0)
    receipt_pending_wt = db.Column('receipt_pending_wt', db.Numeric(18, 3), nullable=True, default=0)
    total_pending_pcs = db.Column('total_pending_pcs', db.BigInteger, nullable=True, default=0)
    total_pending_wt = db.Column('total_pending_wt', db.Numeric(18, 3), nullable=True, default=0)
    branch_id = db.Column('branch_id', db.Integer, nullable=True)

    snapshot_date = db.Column(db.Date, nullable=False, default=db.func.current_date())
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    @property
    def collection_owner(self):
        return self.collection_wner

    @property
    def shop_manager(self):
        return self.shop_manger

    @property
    def supplier(self):
        return self.party_name

    def to_dict(self):
        return {
            c.name: getattr(self, c.name).isoformat()
            if isinstance(getattr(self, c.name), (datetime, date))
            else getattr(self, c.name)
            for c in self.__table__.columns
        }


# Alias for backward compatibility
CustomerOrderAnalysis = CustomerOrderAnalysisSnapshot
