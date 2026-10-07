from datetime import datetime
from app.extensions import db


class CustomerOrderFulfilmentSummarySnapshot(db.Model):
    """
    SQLAlchemy model representing the local snapshot table customer_order_fulfilment_summary_snapshot.
    Stores data synced from ext_view.vw_customer_order_tracking.
    """
    __tablename__ = 'customer_order_fulfilment_summary_snapshot'
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # Core identification & Hierarchy
    location = db.Column('location', db.String(100), index=True, nullable=True)
    state = db.Column('state', db.String(50), nullable=True)
    business_head_name = db.Column('business_head_name', db.Text, index=True, nullable=True)
    order_ro = db.Column('order_ro', db.String(250), index=True, nullable=True)
    branch_type = db.Column('branch_type', db.String(250), nullable=True)
    classification_owner = db.Column('classification_owner', db.String(250), nullable=True)
    make_owner = db.Column('make_owner', db.String(250), nullable=True)
    collection_owner = db.Column('collection_owner', db.Text, nullable=True)
    shop_manger = db.Column('shop_manger', db.Text, nullable=True)

    # Product taxonomy
    division = db.Column('division', db.String(100), nullable=True)
    group_category = db.Column('group_category', db.String(100), nullable=True)
    group_name = db.Column('group', db.String(100), nullable=True)
    section = db.Column('section', db.String(50), index=True, nullable=True)
    purity = db.Column('purity', db.Text, nullable=True)
    gender = db.Column('gender', db.String(200), nullable=True)
    classification = db.Column('classification', db.String(100), nullable=True)
    collection = db.Column('collection', db.String(100), index=True, nullable=True)
    make = db.Column('make', db.String(100), index=True, nullable=True)
    refrerence_make = db.Column('refrerence_make', db.String(50), nullable=True)
    wide_range = db.Column('wide_range', db.String(100), index=True, nullable=True)

    # Weights and Specs
    weight = db.Column('weight', db.Numeric(18, 3), nullable=True, default=0)
    size = db.Column('size', db.Text, nullable=True)
    gross_weight = db.Column('gross_weight', db.Numeric(18, 3), nullable=True, default=0)
    stone_weight = db.Column('stone_weight', db.Numeric(18, 3), nullable=True, default=0)
    other_weight = db.Column('other_weight', db.Numeric(18, 3), nullable=True, default=0)
    net_weight = db.Column('net_weight', db.Numeric(18, 3), nullable=True, default=0)

    # Order Details & Status
    request_no = db.Column('request_no', db.Text, index=True, nullable=True)
    sooc_no = db.Column('sooc_no', db.Text, nullable=True)
    order_request_type = db.Column('order_request_type', db.String(250), nullable=True)
    order_item_type = db.Column('order_item_type', db.Text, nullable=True)
    order_status = db.Column('order_status', db.Text, nullable=True)
    advance_no = db.Column('advance_no', db.Text, nullable=True)
    party_name = db.Column('party_name', db.String(150), index=True, nullable=True)
    party_code = db.Column('party_code', db.Text, nullable=True)
    party_type = db.Column('party_type', db.Text, nullable=True)
    customer_name = db.Column('customer_name', db.Text, nullable=True)
    customer_contact_number = db.Column('customer_contact_number', db.Text, nullable=True)
    customer_order_request_type = db.Column('customer_order_request_type', db.Text, nullable=True)
    with_reference = db.Column('with_reference', db.Boolean, nullable=True, default=False)

    # Quantities & Weights
    total_order = db.Column('total_order', db.Integer, nullable=True, default=0)
    order_generated_wt = db.Column('order_generated_wt', db.Numeric(18, 3), nullable=True, default=0)

    approved_pcs = db.Column('approved_pcs', db.Integer, nullable=True, default=0)
    approved_wt = db.Column('approved_wt', db.Numeric(18, 3), nullable=True, default=0)

    accepted_pcs = db.Column('accepted_pcs', db.Integer, nullable=True, default=0)
    accepted_wt = db.Column('accepted_wt', db.Numeric(18, 3), nullable=True, default=0)

    cancelled_pcs = db.Column('cancelled_pcs', db.Integer, nullable=True, default=0)
    cancelled_wt = db.Column('cancelled_wt', db.Numeric(18, 3), nullable=True, default=0)

    rejected_pcs = db.Column('rejected_pcs', db.Integer, nullable=True, default=0)
    rejected_wt = db.Column('rejected_wt', db.Numeric(18, 3), nullable=True, default=0)

    barcoded_pcs = db.Column('barcoded_pcs', db.Integer, nullable=True, default=0)
    barcoded_wt = db.Column('barcoded_wt', db.Numeric(18, 3), nullable=True, default=0)

    hallmarked_pcs = db.Column('hallmarked_pcs', db.Integer, nullable=True, default=0)
    hallmarked_wt = db.Column('hallmarked_wt', db.Numeric(18, 3), nullable=True, default=0)

    qc_passed_pcs = db.Column('qc_passed_pcs', db.Integer, nullable=True, default=0)
    qc_passed_wt = db.Column('qc_passed_wt', db.Numeric(18, 3), nullable=True, default=0)

    invoiced_pcs = db.Column('invoiced_pcs', db.Integer, nullable=True, default=0)
    invoiced_wt = db.Column('invoiced_wt', db.Numeric(18, 3), nullable=True, default=0)

    received_in_office = db.Column('received_in_office', db.Boolean, nullable=True, default=False)
    received_in_office_pcs = db.Column('received_in_office_pcs', db.Integer, nullable=True, default=0)
    received_in_office_wt = db.Column('received_in_office_wt', db.Numeric(18, 3), nullable=True, default=0)

    delivered_to_shop = db.Column('delivered_to_shop', db.Boolean, nullable=True, default=False)
    delivered_to_shop_pcs = db.Column('delivered_to_shop_pcs', db.Integer, nullable=True, default=0)
    delivered_to_shop_wt = db.Column('delivered_to_shop_wt', db.Numeric(18, 3), nullable=True, default=0)

    delivered_to_customer = db.Column('delivered_to_customer', db.Boolean, nullable=True, default=False)
    delivered_to_customer_pcs = db.Column('delivered_to_customer_pcs', db.Integer, nullable=True, default=0)
    delivered_to_customer_wt = db.Column('delivered_to_customer_wt', db.Numeric(18, 3), nullable=True, default=0)

    delivered_pcs = db.Column('delivered_pcs', db.Integer, nullable=True, default=0)
    delivered_wt = db.Column('delivered_wt', db.Numeric(18, 3), nullable=True, default=0)

    pending_to_delivered_pcs = db.Column('pending_to_delivered_pcs', db.Integer, nullable=True, default=0)
    pending_to_delivered_wt = db.Column('pending_to_delivered_wt', db.Numeric(18, 3), nullable=True, default=0)
    pending_to_be_delivered_pcs = db.Column('pending_to_be_delivered_pcs', db.Integer, nullable=True, default=0)
    pending_to_be_delivered_wt = db.Column('pending_to_be_delivered_wt', db.Numeric(18, 3), nullable=True, default=0)

    # Dates
    manager_approve_date = db.Column('manager_approve_date', db.Date, nullable=True)
    collection_owner_approve_date = db.Column('collection_owner_approve_date', db.Date, nullable=True)
    customer_approve_date = db.Column('customer_approve_date', db.Date, nullable=True)
    request_date = db.Column('request_date', db.DateTime, nullable=True)
    order_creation_date = db.Column('order_creation_date', db.Date, nullable=True)
    party_accepted_date = db.Column('party_accepted_date', db.Date, nullable=True)
    office_delivery_date = db.Column('office_delivery_date', db.DateTime, nullable=True)
    shop_delivery_date = db.Column('shop_delivery_date', db.Date, nullable=True)
    customer_delivery_date = db.Column('customer_delivery_date', db.Date, nullable=True)
    expected_delivery_date = db.Column('expected_delivery_date', db.DateTime, nullable=True)
    advance_date = db.Column('advance_date', db.DateTime, nullable=True)

    # Derived Analytics / Filter Dimensions
    report_month = db.Column('report_month', db.String(20), index=True, nullable=True)
    report_date = db.Column('report_date', db.Date, index=True, nullable=True)
    current_stage = db.Column('current_stage', db.String(100), index=True, nullable=True)
    order_ageing_days = db.Column('order_ageing_days', db.Integer, index=True, nullable=True)
    delivery_delay_days = db.Column('delivery_delay_days', db.Integer, index=True, nullable=True)
    delay_status = db.Column('delay_status', db.String(50), index=True, nullable=True)
    delay_bucket = db.Column('delay_bucket', db.String(50), index=True, nullable=True)
    manager_approval_tat = db.Column('manager_approval_tat', db.Integer, nullable=True)
    collection_owner_approval_tat = db.Column('collection_owner_approval_tat', db.Integer, nullable=True)
    customer_approval_tat = db.Column('customer_approval_tat', db.Integer, nullable=True)
    party_acceptance_tat = db.Column('party_acceptance_tat', db.Integer, nullable=True)
    office_delivery_tat = db.Column('office_delivery_tat', db.Integer, nullable=True)
    shop_delivery_tat = db.Column('shop_delivery_tat', db.Integer, nullable=True)
    overall_order_tat = db.Column('overall_order_tat', db.Integer, nullable=True)
    expected_vs_actual_delivery_days = db.Column('expected_vs_actual_delivery_days', db.Integer, nullable=True)
    days_to_expected_delivery = db.Column('days_to_expected_delivery', db.Integer, nullable=True)
    delivery_status = db.Column('delivery_status', db.String(100), index=True, nullable=True)
    with_reference_status = db.Column('with_reference_status', db.String(50), index=True, nullable=True)

    created_at = db.Column('created_at', db.DateTime, default=datetime.utcnow)
    updated_at = db.Column('updated_at', db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
