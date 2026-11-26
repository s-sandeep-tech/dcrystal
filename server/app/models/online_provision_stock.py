from app.extensions import db
from datetime import datetime

class OnlineProvisionStockRawSnapshot(db.Model):
    __tablename__ = 'online_provision_stock_raw_snapshot'
    __table_args__ = (
        db.Index(
            'idx_online_provision_stock_popup_path',
            'section', 'type', 'wide_range', 'range_weight',
        ),
        db.Index('idx_online_provision_stock_location', 'location'),
        db.Index('idx_online_provision_stock_branch_id', 'branch_id'),
        db.Index(
            'idx_online_provision_stock_business_head_emp_code',
            'business_head_emp_code',
        ),
        db.Index('idx_online_provision_stock_collection', 'collection'),
        db.Index('idx_online_provision_stock_make', 'make'),
        db.Index('idx_online_provision_stock_section', 'section'),
        db.Index('idx_online_provision_stock_state', 'state'),
    )

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    
    # Text / String Identifiers
    division = db.Column(db.String(50))
    group_name = db.Column('group', db.String(50))
    location = db.Column(db.String(100))
    branch_id = db.Column(db.Integer)
    branch_type = db.Column(db.String(100))
    branch_status = db.Column(db.String(100))
    business_head_name = db.Column(db.String(100))
    business_head_emp_code = db.Column(db.String(100))
    state = db.Column(db.String(100))

    provision_mode = db.Column(db.Integer)
    provision_mode_filter = db.Column(db.Text)
    classification = db.Column(db.String(50))
    sub_classification = db.Column(db.String(50))
    section = db.Column(db.String(50))
    type = db.Column(db.String(50))
    make = db.Column(db.String(50))
    collection = db.Column(db.String(50))
    master_collection = db.Column(db.String(50))
    sub_section = db.Column(db.String(50))
    gender = db.Column(db.String(200))
    wide_range = db.Column(db.String(200))
    size = db.Column(db.Text)
    screw_type = db.Column(db.String(200))
    prov_type = db.Column(db.Text)
    design_no = db.Column(db.String(100))
    design_uid = db.Column(db.Text)

    # External hierarchy identifiers
    division_id = db.Column(db.BigInteger)
    group_id = db.Column(db.BigInteger)
    purity_id = db.Column(db.BigInteger)
    classification_id = db.Column(db.BigInteger)
    sub_classification_id = db.Column(db.BigInteger)
    section_id = db.Column(db.BigInteger)
    type_id = db.Column(db.BigInteger)
    make_id = db.Column(db.BigInteger)
    collection_id = db.Column(db.BigInteger)
    master_collection_id = db.Column(db.BigInteger)
    sub_section_id = db.Column(db.BigInteger)
    wide_range_id = db.Column(db.BigInteger)
    gender_id = db.Column(db.BigInteger)
    size_id = db.Column(db.BigInteger)
    screw_type_id = db.Column(db.BigInteger)
    
    # Numeric Measures
    purity = db.Column(db.Numeric(10, 2))
    range_weight = db.Column(db.Numeric(18, 3))
    prov_pieces = db.Column(db.Numeric(18, 3))
    prov_gr_wt = db.Column(db.Numeric(18, 3))
    prov_amount = db.Column(db.Numeric(18, 3))
    stock_qty = db.Column(db.Numeric(18, 3))
    stock_gr_wt = db.Column(db.Numeric(18, 3))
    stock_amount = db.Column(db.Numeric(18, 3))
    in_shop_pcs = db.Column(db.Numeric(18, 3))
    in_shop_wt = db.Column(db.Numeric(18, 3))
    in_shop_amt = db.Column(db.Numeric(18, 3))
    not_in_shop = db.Column(db.Numeric(18, 3))
    in_transit = db.Column(db.Numeric(18, 3))
    order_only = db.Column(db.Numeric(18, 3))
    req_only = db.Column(db.Numeric(18, 3))
    in_transit_wt = db.Column(db.Numeric(18, 3))
    order_only_wt = db.Column(db.Numeric(18, 3))
    not_in_shop_wt = db.Column(db.Numeric(18, 3))
    refill_from_qty = db.Column(db.Numeric(18, 3))
    refill_to_qty = db.Column(db.Numeric(18, 3))
    refill_from_wt = db.Column(db.Numeric(18, 3))
    refill_to_wt = db.Column(db.Numeric(18, 3))
    
    # Short / Excess Metrics
    short_pcs = db.Column(db.Numeric(18, 3))
    short_gr_wt = db.Column(db.Numeric(18, 3))
    short_amt = db.Column(db.Numeric(18, 3))
    short_percent = db.Column(db.Numeric(18, 3))
    excess_pcs = db.Column(db.Numeric(18, 3))
    excess_gr_weight = db.Column(db.Numeric(18, 3))
    excess_amt = db.Column(db.Numeric(18, 3))
    not_in_prov_pcs = db.Column(db.Numeric(18, 3))
    not_in_prov_gr_weight = db.Column(db.Numeric(18, 3))
    not_in_prov_amt = db.Column(db.Numeric(18, 3))
    
    # Filter Trackers
    prov_type_filter = db.Column(db.Integer)
    
    snapshot_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class OnlineProvisionStockRawStaging(db.Model):
    __tablename__ = 'online_provision_stock_raw_staging'

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    
    # Text / String Identifiers
    division = db.Column(db.String(50))
    group_name = db.Column('group', db.String(50))
    location = db.Column(db.String(100))
    branch_id = db.Column(db.Integer)
    branch_type = db.Column(db.String(100))
    branch_status = db.Column(db.String(100))
    business_head_name = db.Column(db.String(100))
    business_head_emp_code = db.Column(db.String(100))
    state = db.Column(db.String(100))

    provision_mode = db.Column(db.Integer)
    provision_mode_filter = db.Column(db.Text)
    classification = db.Column(db.String(50))
    sub_classification = db.Column(db.String(50))
    section = db.Column(db.String(50))
    type = db.Column(db.String(50))
    make = db.Column(db.String(50))
    collection = db.Column(db.String(50))
    master_collection = db.Column(db.String(50))
    sub_section = db.Column(db.String(50))
    gender = db.Column(db.String(200))
    wide_range = db.Column(db.String(200))
    size = db.Column(db.Text)
    screw_type = db.Column(db.String(200))
    prov_type = db.Column(db.Text)
    design_no = db.Column(db.String(100))
    design_uid = db.Column(db.Text)

    # External hierarchy identifiers
    division_id = db.Column(db.BigInteger)
    group_id = db.Column(db.BigInteger)
    purity_id = db.Column(db.BigInteger)
    classification_id = db.Column(db.BigInteger)
    sub_classification_id = db.Column(db.BigInteger)
    section_id = db.Column(db.BigInteger)
    type_id = db.Column(db.BigInteger)
    make_id = db.Column(db.BigInteger)
    collection_id = db.Column(db.BigInteger)
    master_collection_id = db.Column(db.BigInteger)
    sub_section_id = db.Column(db.BigInteger)
    wide_range_id = db.Column(db.BigInteger)
    gender_id = db.Column(db.BigInteger)
    size_id = db.Column(db.BigInteger)
    screw_type_id = db.Column(db.BigInteger)
    
    # Numeric Measures
    purity = db.Column(db.Numeric(10, 2))
    range_weight = db.Column(db.Numeric(18, 3))
    prov_pieces = db.Column(db.Numeric(18, 3))
    prov_gr_wt = db.Column(db.Numeric(18, 3))
    prov_amount = db.Column(db.Numeric(18, 3))
    stock_qty = db.Column(db.Numeric(18, 3))
    stock_gr_wt = db.Column(db.Numeric(18, 3))
    stock_amount = db.Column(db.Numeric(18, 3))
    in_shop_pcs = db.Column(db.Numeric(18, 3))
    in_shop_wt = db.Column(db.Numeric(18, 3))
    in_shop_amt = db.Column(db.Numeric(18, 3))
    not_in_shop = db.Column(db.Numeric(18, 3))
    in_transit = db.Column(db.Numeric(18, 3))
    order_only = db.Column(db.Numeric(18, 3))
    req_only = db.Column(db.Numeric(18, 3))
    in_transit_wt = db.Column(db.Numeric(18, 3))
    order_only_wt = db.Column(db.Numeric(18, 3))
    not_in_shop_wt = db.Column(db.Numeric(18, 3))
    refill_from_qty = db.Column(db.Numeric(18, 3))
    refill_to_qty = db.Column(db.Numeric(18, 3))
    refill_from_wt = db.Column(db.Numeric(18, 3))
    refill_to_wt = db.Column(db.Numeric(18, 3))
    
    # Short / Excess Metrics
    short_pcs = db.Column(db.Numeric(18, 3))
    short_gr_wt = db.Column(db.Numeric(18, 3))
    short_amt = db.Column(db.Numeric(18, 3))
    short_percent = db.Column(db.Numeric(18, 3))
    excess_pcs = db.Column(db.Numeric(18, 3))
    excess_gr_weight = db.Column(db.Numeric(18, 3))
    excess_amt = db.Column(db.Numeric(18, 3))
    not_in_prov_pcs = db.Column(db.Numeric(18, 3))
    not_in_prov_gr_weight = db.Column(db.Numeric(18, 3))
    not_in_prov_amt = db.Column(db.Numeric(18, 3))
    
    # Filter Trackers
    prov_type_filter = db.Column(db.Integer)
    
    snapshot_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


