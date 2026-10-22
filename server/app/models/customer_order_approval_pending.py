import os
from datetime import datetime, date
from app.extensions import db


class CustomerOrderApprovalPendingSnapshot(db.Model):
    """
    SQLAlchemy model representing the local snapshot table customer_order_approval_pending_snapshot.
    Stores data synced from ext_view.vw_customer_order_approval_pending_details.
    """
    __tablename__ = 'customer_order_approval_pending_snapshot'
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # Location & Hierarchy
    state = db.Column('state', db.String(50), nullable=True)
    location = db.Column('location', db.String(100), index=True, nullable=True)
    business_head_name = db.Column('business_head_name', db.Text, index=True, nullable=True)
    classification_owner = db.Column('classification_owner', db.String, index=True, nullable=True)
    classification_owner_emp_code = db.Column('classification_owner_emp_code', db.String(256), nullable=True)
    make_owner = db.Column('make_owner', db.String, index=True, nullable=True)
    make_owner_emp_code = db.Column('make_owner_emp_code', db.String(256), nullable=True)
    collection_owner = db.Column('collection_owner', db.Text, index=True, nullable=True)
    collection_owner_emp_code = db.Column('collection_owner_emp_code', db.String(256), nullable=True)

    # Order identifiers
    request_no = db.Column('request_no', db.Text, index=True, nullable=True)
    request_date = db.Column('request_date', db.Date, nullable=True)
    request_type = db.Column('request_type', db.Text, nullable=True)
    order_item_type = db.Column('order_item_type', db.Text, nullable=True)
    order_ro = db.Column('order_ro', db.String(250), nullable=True)
    po_number = db.Column('po_number', db.String(50), nullable=True)
    po_date = db.Column('po_date', db.Date, nullable=True)
    sooc = db.Column('sooc', db.Text, nullable=True)
    barcode = db.Column('barcode', db.Text, nullable=True)

    # Taxonomy & Classification
    division = db.Column('division', db.String(50), nullable=True)
    group_category = db.Column('group_category', db.String(50), nullable=True)
    group = db.Column('group', db.String(50), nullable=True)
    classification = db.Column('classification', db.String(50), nullable=True)
    sub_classification = db.Column('sub_classification', db.String(50), nullable=True)
    make = db.Column('make', db.String(50), index=True, nullable=True)
    refrerence_make = db.Column('refrerence_make', db.String(50), nullable=True)
    section = db.Column('section', db.String(50), index=True, nullable=True)
    collection = db.Column('collection', db.String(50), nullable=True)
    reference_collection = db.Column('reference_collection', db.String(50), nullable=True)
    purity = db.Column('purity', db.Text, nullable=True)
    gender = db.Column('gender', db.String(200), nullable=True)

    # Product Weights & Spec
    weight = db.Column('weight', db.Numeric(18, 3), nullable=True)
    size = db.Column('size', db.Text, nullable=True)
    gross_weight = db.Column('gross_weight', db.Numeric(18, 3), nullable=True)
    stone_weight = db.Column('stone_weight', db.Numeric(18, 3), nullable=True)
    other_weight = db.Column('other_weight', db.Numeric(18, 3), nullable=True)
    net_weight = db.Column('net_weight', db.Numeric(18, 3), nullable=True)

    # Advance & Party Info
    advance_no = db.Column('advance_no', db.Text, nullable=True)
    advance_date = db.Column('advance_date', db.DateTime, nullable=True)
    party_name = db.Column('party_name', db.String(150), index=True, nullable=True)
    party_code = db.Column('party_code', db.Text, nullable=True)
    party_type = db.Column('party_type', db.Text, nullable=True)
    customer_name = db.Column('customer_name', db.Text, nullable=True)
    customer_phone_number = db.Column('customer_phone_number', db.Text, nullable=True)
    reorder = db.Column('reorder', db.Text, nullable=True)
    supplier_expected_delivery_date = db.Column('supplier_expected_delivery_date', db.Date, nullable=True)
    customer_expected_delivery_date = db.Column('customer_expected_delivery_date', db.Date, nullable=True)
    combine_order_status = db.Column('combine_order_status', db.Text, nullable=True)
    shop_manger = db.Column('shop_manger', db.Text, nullable=True)

    # Verification Team
    verifying_team = db.Column('verifying_team', db.Text, nullable=True)
    verifying_team_emp_code = db.Column('verifying_team_emp_code', db.String(256), nullable=True)

    # Pending Approval Metrics (Pcs and Wt)
    composition_pending_pcs = db.Column('composition_pending_pcs', db.Integer, nullable=True, default=0)
    composition_pending_wt = db.Column('composition_pending_wt', db.Numeric(18, 3), nullable=True, default=0)
    verifying_team_approval_pending_pcs = db.Column('verifying_team_approval_pending_pcs', db.Integer, nullable=True, default=0)
    verifying_team_approval_pending_wt = db.Column('verifying_team_approval_pending_wt', db.Numeric(18, 3), nullable=True, default=0)
    estimation_and_advance_pending_pcs = db.Column('estimation_and_advance_pending_pcs', db.Integer, nullable=True, default=0)
    estimation_and_advance_pending_wt = db.Column('estimation_and_advance_pending_wt', db.Numeric(18, 3), nullable=True, default=0)
    manager_approval_pending_pcs = db.Column('manager_approval_pending_pcs', db.Integer, nullable=True, default=0)
    manager_approval_pending_wt = db.Column('manager_approval_pending_wt', db.Numeric(18, 3), nullable=True, default=0)
    advance_verification_pending_pcs = db.Column('advance_verification_pending_pcs', db.Integer, nullable=True, default=0)
    advance_verification_pending_wt = db.Column('advance_verification_pending_wt', db.Numeric(18, 3), nullable=True, default=0)
    collection_owner_approval_pending_pcs = db.Column('collection_owner_approval_pending_pcs', db.Integer, nullable=True, default=0)
    collection_owner_approval_pending_wt = db.Column('collection_owner_approval_pending_wt', db.Numeric(18, 3), nullable=True, default=0)
    customer_approval_pending_pcs = db.Column('customer_approval_pending_pcs', db.Integer, nullable=True, default=0)
    customer_approval_pending_wt = db.Column('customer_approval_pending_wt', db.Numeric(18, 3), nullable=True, default=0)
    party_order_creation_pending_pcs = db.Column('party_order_creation_pending_pcs', db.Integer, nullable=True, default=0)
    party_order_creation_pending_wt = db.Column('party_order_creation_pending_wt', db.Numeric(18, 3), nullable=True, default=0)

    # Total calculated columns
    total_pending_pcs = db.Column('total_pending_pcs', db.Integer, nullable=True, default=0)
    total_pending_wt = db.Column('total_pending_wt', db.Numeric(18, 3), nullable=True, default=0)

    snapshot_date = db.Column(db.Date, nullable=False, default=db.func.current_date())
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

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


# Convenient alias
CustomerOrderApprovalPending = CustomerOrderApprovalPendingSnapshot
