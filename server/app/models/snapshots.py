from app.extensions import db
from datetime import datetime

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

    total_count = db.Column(db.Integer, default=0, nullable=False)
    dispatched_count = db.Column(db.Integer, default=0, nullable=False)
    in_process_count = db.Column(db.Integer, default=0, nullable=False)
    delayed_count = db.Column(db.Integer, default=0, nullable=False)
    active_slots = db.Column(db.Integer, default=0, nullable=False)

    sla_index_pct = db.Column(db.Numeric(5, 2))
    avg_quality_score = db.Column(db.Numeric(3, 2))
    fulfillment_pct = db.Column(db.Numeric(5, 2))

    updated_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

class LocationWiseOrderSnapshot(db.Model):
    __tablename__ = 'location_wise_order_snapshot'

    snapshot_id = db.Column(db.BigInteger, primary_key=True)
    snapshot_date = db.Column(db.Date, nullable=False)
    location = db.Column(db.String(150))
    division = db.Column(db.String(100))
    group_name = db.Column(db.String(100))
    purity = db.Column(db.String(50))
    classification = db.Column(db.String(150))
    make_location = db.Column(db.String(120))
    collection = db.Column(db.String(150))
    
    # Owners
    make_owner = db.Column(db.String(100))
    collection_owner = db.Column(db.String(100))
    classification_owner = db.Column(db.String(100))
    business_head = db.Column(db.String(100))

    # Stage Counts
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
    dispatched_count = db.Column(db.Integer, default=0, nullable=False)
    in_process_count = db.Column(db.Integer, default=0, nullable=False)
    delayed_count = db.Column(db.Integer, default=0, nullable=False)
    sla_index_pct = db.Column(db.Numeric(5, 2))
    fulfillment_pct = db.Column(db.Numeric(5, 2))

    updated_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

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

class OrderProvisionSummaryReport(db.Model):
    __tablename__ = 'order_provision_summary_report_snapshot'

    po_number = db.Column(db.String(100), primary_key=True)
    location = db.Column(db.Text)
    party = db.Column(db.Text)
    party_type = db.Column(db.Text)
    division = db.Column(db.Text)
    group_name = db.Column(db.Text)
    classification = db.Column(db.Text)
    section = db.Column(db.Text)
    make = db.Column(db.Text)
    purity = db.Column(db.Text)
    master_collection = db.Column(db.Text)
    collection = db.Column(db.Text)
    pieces = db.Column(db.Text) # Stored as text in DB
    gr_wt = db.Column(db.Text)  # Stored as text in DB
    total = db.Column(db.Text)
    business_head = db.Column(db.Text)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self):
        return {
            'location': self.location,
            'party': self.party,
            'party_type': self.party_type,
            'po_number': self.po_number,
            'division': self.division,
            'group_name': self.group_name,
            'classification': self.classification,
            'section': self.section,
            'make_location': self.make,
            'purity': self.purity,
            'product_type': self.master_collection,
            'collection': self.collection,
            'total_count': self.pieces,
            'weight': self.gr_wt,
            'total': self.total
        }

class OwnerWiseOrderSummarySnapshot(db.Model):
    __tablename__ = 'owner_wise_order_summary_snapshot'

    supplier = db.Column('Supplier', db.Text, primary_key=True)
    batch = db.Column('Batch', db.Text, primary_key=True)
    division = db.Column('Division', db.Text, primary_key=True)
    group_name = db.Column('Group', db.Text, primary_key=True)
    purity = db.Column('Purity', db.Numeric(10, 2), primary_key=True)
    classification = db.Column('Classification', db.Text, primary_key=True)
    make = db.Column('Make', db.Text, primary_key=True)
    collection = db.Column('Collection', db.Text, primary_key=True)
    order_request_type = db.Column('order_request_type', db.Text, primary_key=True)
    order_type = db.Column('order_type', db.Text, primary_key=True)
    order_date = db.Column('order_date', db.Date, primary_key=True)
    order_ro = db.Column('order_ro', db.Text, primary_key=True)
    provision_type = db.Column('provision_type', db.Text, primary_key=True)
    branch_provision_type = db.Column('branch_provision_type', db.Text, primary_key=True)
    
    classification_owner = db.Column('Classification Owner', db.Text, primary_key=True)
    collection_owner = db.Column('Collection Owner', db.Text, primary_key=True)
    make_owner = db.Column('Make Owner', db.Text, primary_key=True)
    
    ordered_pcs = db.Column('Ordered Pcs', db.Numeric(18, 3))
    ordered_wt = db.Column('Ordered Wt', db.Numeric(18, 3))
    accepted_pcs = db.Column('Accepted Pcs', db.Numeric(18, 3))
    accepted_wt = db.Column('Accepted Wt', db.Numeric(18, 3))
    rejected_pcs = db.Column('Rejected Pcs', db.Numeric(18, 3))
    rejected_wt = db.Column('Rejected Wt', db.Numeric(18, 3))
    cancelled_pcs = db.Column('Cancelled Pcs', db.Numeric(18, 3))
    cancelled_wt = db.Column('Cancelled Wt', db.Numeric(18, 3))
    barcoded_pcs = db.Column('Barcoded Pcs', db.Numeric(18, 3))
    barcoded_wt = db.Column('Barcoded Wt', db.Numeric(18, 3))
    not_barcoded_pcs = db.Column('Not Barcod Pcs', db.Numeric(18, 3))
    not_barcoded_wt = db.Column('Not Barcode Wt', db.Numeric(18, 3))
    
    hm_processed_pcs = db.Column('Hm Processed Pcs', db.Numeric(18, 3))
    hm_testcut_pcs = db.Column('Hm Testcut Pcs', db.Integer)
    hm_testcut_wt = db.Column('Hm Testcut Wt', db.Numeric(18, 3))
    hm_passed_pcs = db.Column('Hm Passed Pcs', db.Numeric(18, 3))
    hm_passed_wt = db.Column('Hm Passed Wt', db.Numeric(18, 3))
    hm_failed_pcs = db.Column('Hm Failed Pcs', db.Numeric(18, 3))
    hm_failed_wt = db.Column('Hm Failed Wt', db.Numeric(18, 3))
    
    qc_processed_pcs = db.Column('Qc Processed Pcs', db.Numeric(18, 3))
    qc_pending_pcs = db.Column('Qc Pending Pcs', db.Numeric(18, 3))
    qc_pending_wt = db.Column('Qc Pending Wt', db.Numeric(18, 3))
    qc_rejected_pcs = db.Column('Qc Rejected Pcs', db.Numeric(18, 3))
    qc_rejected_wt = db.Column('Qc Rejected Wt', db.Numeric(18, 3))
    qc_passed_pcs = db.Column('Qc Passed Pcs', db.Numeric(18, 3))
    qc_passed_wt = db.Column('Qc Passed Wt', db.Numeric(18, 3))
    
    invoiced_pcs = db.Column('Invoiced Pcs', db.Numeric(18, 3))
    invoiced_wt = db.Column('Invoiced Wt', db.Numeric(18, 3))
    delivered_pcs = db.Column('Delivered Pcs', db.Numeric(18, 3))
    delivered_wt = db.Column('Delivered Wt', db.Numeric(18, 3))
    pending_to_be_delv_pcs = db.Column('Pending To Be Delv. Pcs', db.Numeric(18, 3))
    pending_to_be_delv_wt = db.Column('Pending To Be Delv. Wt', db.Numeric(18, 3))
    
    pending_to_accepted_pcs = db.Column('Pending To Accepted Pcs', db.Numeric(18, 3))
    pending_to_accepted_wt = db.Column('Pending To Accepted Wt', db.Numeric(18, 3))
    

class TicketLogSnapshot(db.Model):
    __tablename__ = 'ticket_log_snapshot'

    ticket_no = db.Column('ticket_no', db.String(50), primary_key=True)
    issue_reported_office = db.Column('issue_reported_office', db.String(150))
    issue_reported_user = db.Column('issue_reported_user', db.String(150))
    ticket_date = db.Column('ticket_date', db.DateTime)
    transaction_type = db.Column('transaction_type', db.String(100))
    party_name = db.Column('party_name', db.String(200))
    trans_dt = db.Column('trans_dt', db.DateTime)
    transaction_no = db.Column('transaction_no', db.String(100))
    issue_description = db.Column('issue_description', db.Text)
    issue_reported_date = db.Column('issue_reported_date', db.DateTime)
    assigned_to_crystal_poc = db.Column('assigned_to_crystal_poc', db.String(150))
    crystal_status = db.Column('crystal_status', db.String(50))
    crystal_completed_date = db.Column('crystal_completed_date', db.DateTime)
    crystal_remarks = db.Column('crystal_remarks', db.Text)

    def to_dict(self):
        return {
            'ticket_no': self.ticket_no,
            'issue_reported_office': self.issue_reported_office,
            'issue_reported_user': self.issue_reported_user,
            'ticket_date': self.ticket_date.strftime('%Y-%m-%d %H:%M:%S') if self.ticket_date else None,
            'transaction_type': self.transaction_type,
            'party_name': self.party_name,
            'trans_dt': self.trans_dt.strftime('%Y-%m-%d %H:%M:%S') if self.trans_dt else None,
            'transaction_no': self.transaction_no,
            'issue_description': self.issue_description,
            'issue_reported_date': self.issue_reported_date.strftime('%Y-%m-%d %H:%M:%S') if self.issue_reported_date else None,
            'assigned_to_crystal_poc': self.assigned_to_crystal_poc,
            'crystal_status': self.crystal_status,
            'crystal_completed_date': self.crystal_completed_date.strftime('%Y-%m-%d %H:%M:%S') if self.crystal_completed_date else None,
            'crystal_remarks': self.crystal_remarks
        }


class PartyProcessAgeingSnapshot(db.Model):
    __tablename__ = 'party_process_ageing_snapshot'

    id = db.Column(db.Integer, primary_key=True)
    party_name = db.Column(db.Text, nullable=False)
    completed_process_level = db.Column(db.Text, nullable=False)
    completed_quantity = db.Column(db.Integer, nullable=False)
    next_process_level = db.Column(db.Text, nullable=False)
    time_window_1_2_days = db.Column(db.Integer, nullable=False, default=0)
    time_window_2_4_days = db.Column(db.Integer, nullable=False, default=0)
    time_window_5_10_days = db.Column(db.Integer, nullable=False, default=0)
    time_window_more_than_10_days = db.Column(db.Integer, nullable=False, default=0)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    report_date = db.Column(db.Date, nullable=False, default=db.func.current_date())
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self):
        return {
            'party_name': self.party_name,
            'completed_process_level': self.completed_process_level,
            'completed_quantity': self.completed_quantity,
            'next_process_level': self.next_process_level,
            'time_window_1_2_days': self.time_window_1_2_days,
            'time_window_2_4_days': self.time_window_2_4_days,
            'time_window_5_10_days': self.time_window_5_10_days,
            'time_window_more_than_10_days': self.time_window_more_than_10_days,
            'sort_order': self.sort_order,
            'report_date': self.report_date.isoformat() if self.report_date else None
        }

class OutstandingPurchaseOrderStatusSnapshot(db.Model):
    __tablename__ = 'outstanding_purchase_order_status_snapshot'

    id = db.Column(db.Integer, primary_key=True)
    classification_owner = db.Column('classification_owner', db.Text)
    make_owner = db.Column('make_owner', db.Text)
    collection_owner = db.Column('collection_owner', db.Text)
    party = db.Column('party', db.Text)
    order_number = db.Column('order_number', db.Text)
    order_date = db.Column('order_date', db.Date)
    classification = db.Column('classification', db.Text)
    make = db.Column('make', db.Text)
    collection = db.Column('collection', db.Text)
    section = db.Column('section', db.Text)
    division = db.Column('division', db.Text)
    group = db.Column('group', db.Text)
    purity = db.Column('purity', db.Text)
    purchase_ro = db.Column('purchase_ro', db.Text)
    receipt_present = db.Column('receipt_present', db.Text)
    order_pieces = db.Column('order_pieces', db.Numeric(18, 3))
    order_weight = db.Column('order_weight', db.Numeric(18, 3))
    accepted_pieces = db.Column('accepted_pieces', db.Numeric(18, 3))
    accepted_weight = db.Column('accepted_weight', db.Numeric(18, 3))
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self):
        return {
            'classification_owner': self.classification_owner,
            'make_owner': self.make_owner,
            'collection_owner': self.collection_owner,
            'party': self.party,
            'order_number': self.order_number,
            'order_date': self.order_date.isoformat() if self.order_date else None,
            'classification': self.classification,
            'make': self.make,
            'collection': self.collection,
            'section': self.section,
            'division': self.division,
            'group': self.group,
            'purity': self.purity,
            'purchase_ro': self.purchase_ro,
            'receipt_present': self.receipt_present,
            'order_pieces': float(self.order_pieces or 0),
            'order_weight': float(self.order_weight or 0),
            'accepted_pieces': float(self.accepted_pieces or 0),
            'accepted_weight': float(self.accepted_weight or 0),
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class StageLevelDelaySnapshot(db.Model):
    __tablename__ = 'party_process_ageing_snapshot_V2'

    id = db.Column(db.Integer, primary_key=True)
    classification_owner = db.Column(db.Text)
    make_owner = db.Column(db.Text)
    collection_owner = db.Column(db.Text)
    division = db.Column(db.Text)
    group = db.Column('group', db.Text)
    purity = db.Column(db.Text)
    purchase_ro = db.Column(db.Text)
    order_number = db.Column(db.String(20))
    order_date = db.Column(db.Date)
    barcode_number = db.Column(db.Text)
    barcode_last_step_date = db.Column(db.Date)
    party = db.Column(db.Text)
    completed_process_level = db.Column(db.Text)
    next_process_level = db.Column(db.Text)
    seq = db.Column(db.Integer)
    
    time_window_1_2_days = db.Column(db.Integer, default=0)
    time_window_3_4_days = db.Column(db.Integer, default=0)
    time_window_5_10_days = db.Column(db.Integer, default=0)
    time_window_more_than_10_days = db.Column(db.Integer, default=0)
    
    snapshot_date = db.Column(db.Date, nullable=False, default=db.func.current_date())
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'classification_owner': self.classification_owner,
            'make_owner': self.make_owner,
            'collection_owner': self.collection_owner,
            'division': self.division,
            'group': self.group,
            'purity': self.purity,
            'purchase_ro': self.purchase_ro,
            'order_number': self.order_number,
            'order_date': self.order_date.isoformat() if self.order_date else None,
            'barcode_number': self.barcode_number,
            'barcode_last_step_date': self.barcode_last_step_date.isoformat() if self.barcode_last_step_date else None,
            'party': self.party,
            'completed_process_level': self.completed_process_level,
            'next_process_level': self.next_process_level,
            'seq': self.seq,
            'time_window_1_2_days': self.time_window_1_2_days,
            'time_window_3_4_days': self.time_window_3_4_days,
            'time_window_5_10_days': self.time_window_5_10_days,
            'time_window_more_than_10_days': self.time_window_more_than_10_days,
            'snapshot_date': self.snapshot_date.isoformat() if self.snapshot_date else None
        }

class OrderDelayTrackingSnapshot(db.Model):
    __tablename__ = 'order_delay_tracking_snapshot'

    id = db.Column(db.Integer, primary_key=True)
    classification_owner = db.Column(db.Text)
    make_owner = db.Column(db.Text)
    collection_owner = db.Column(db.Text)
    delay_1_2_days = db.Column(db.Integer, default=0)
    delay_3_4_days = db.Column(db.Integer, default=0)
    delay_5_10_days = db.Column(db.Integer, default=0)
    delay_more_than_10_days = db.Column(db.Integer, default=0)
    supplier = db.Column(db.Text)
    po_id = db.Column(db.Text)
    order_id = db.Column(db.Text)
    po_number = db.Column(db.Text)
    po_date = db.Column(db.Date)
    delivery_target_date = db.Column(db.Date)
    qc_target_date = db.Column(db.Date)
    hm_requested_at = db.Column(db.DateTime)
    hm_out_date = db.Column(db.DateTime)
    qc_date = db.Column(db.DateTime)
    qc_completed_at = db.Column(db.DateTime)
    invoice_date = db.Column(db.Date)
    order_receipt_created_at = db.Column(db.DateTime)
    delay_days = db.Column(db.Integer)
    make = db.Column(db.Text)
    collection = db.Column(db.Text)
    
    # QC Delay Fields
    qc_delay_1_2_days = db.Column(db.Integer, default=0)
    qc_delay_3_4_days = db.Column(db.Integer, default=0)
    qc_delay_5_10_days = db.Column(db.Integer, default=0)
    qc_delay_more_than_10_days = db.Column(db.Integer, default=0)
    qc_delay_days = db.Column(db.Integer)
    
    snapshot_date = db.Column(db.Date, nullable=False, default=db.func.current_date())
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'classification_owner': self.classification_owner,
            'make_owner': self.make_owner,
            'collection_owner': self.collection_owner,
            'delay_1_2_days': self.delay_1_2_days,
            'delay_3_4_days': self.delay_3_4_days,
            'delay_5_10_days': self.delay_5_10_days,
            'delay_more_than_10_days': self.delay_more_than_10_days,
            'qc_delay_1_2_days': self.qc_delay_1_2_days,
            'qc_delay_3_4_days': self.qc_delay_3_4_days,
            'qc_delay_5_10_days': self.qc_delay_5_10_days,
            'qc_delay_more_than_10_days': self.qc_delay_more_than_10_days,
            'qc_delay_days': self.qc_delay_days,
            'supplier': self.supplier,
            'po_id': self.po_id,
            'order_id': self.order_id,
            'po_number': self.po_number,
            'po_date': self.po_date.isoformat() if self.po_date else None,
            'delivery_target_date': self.delivery_target_date.isoformat() if self.delivery_target_date else None,
            'qc_target_date': self.qc_target_date.isoformat() if self.qc_target_date else None,
            'hm_requested_at': self.hm_requested_at.isoformat() if self.hm_requested_at else None,
            'hm_out_date': self.hm_out_date.isoformat() if self.hm_out_date else None,
            'qc_date': self.qc_date.isoformat() if self.qc_date else None,
            'qc_completed_at': self.qc_completed_at.isoformat() if self.qc_completed_at else None,
            'invoice_date': self.invoice_date.isoformat() if self.invoice_date else None,
            'order_receipt_created_at': self.order_receipt_created_at.isoformat() if self.order_receipt_created_at else None,
            'delay_days': self.delay_days,
            'make': self.make,
            'collection': self.collection,
            'snapshot_date': self.snapshot_date.isoformat() if self.snapshot_date else None
        }

class PendingAcceptanceSnapshot(db.Model):
    __tablename__ = 'pending_acceptance_feedback_snapshot'

    id = db.Column(db.Integer, primary_key=True)
    collection_owner = db.Column(db.Text)
    make_owner = db.Column(db.Text)
    supplier = db.Column(db.Text)
    collection = db.Column(db.Text)
    classification = db.Column(db.Text)
    po_number = db.Column(db.Text)
    po_date = db.Column(db.Date)
    total_weight = db.Column(db.Numeric(18, 3))
    order_piece = db.Column(db.Numeric(18, 3))
    order_wt = db.Column(db.Numeric(18, 3))
    accepted_wt = db.Column(db.Numeric(18, 3))
    pending_to_accepted_wt = db.Column(db.Numeric(18, 3))
    pending_to_deliver_pcs = db.Column(db.Numeric(18, 3))
    pending_to_deliver_wt = db.Column(db.Numeric(18, 3))
    not_barcoded_pcs = db.Column(db.Numeric(18, 3))
    not_barcoded_wt = db.Column(db.Numeric(18, 3))
    order_type = db.Column(db.Text)
    order_request_type = db.Column(db.Text)
    order_date = db.Column(db.Date)
    delivery_target_date = db.Column(db.Date)
    branch_type = db.Column(db.Text)
    snapshot_date = db.Column(db.Date, nullable=False, default=db.func.current_date())
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'collection_owner': self.collection_owner,
            'make_owner': self.make_owner,
            'supplier': self.supplier,
            'collection': self.collection,
            'po_number': self.po_number,
            'po_date': self.po_date.isoformat() if self.po_date else '',
            'total_weight': float(self.total_weight or 0),
            'order_piece': float(self.order_piece or 0),
            'order_wt': float(self.order_wt or 0),
            'accepted_wt': float(self.accepted_wt or 0),
            'pending_to_accepted_wt': float(self.pending_to_accepted_wt or 0),
            'pending_to_deliver_pcs': float(self.pending_to_deliver_pcs or 0),
            'pending_to_deliver_wt': float(self.pending_to_deliver_wt or 0),
            'not_barcoded_pcs': float(self.not_barcoded_pcs or 0),
            'not_barcoded_wt': float(self.not_barcoded_wt or 0),
            'order_type': self.order_type or '',
            'order_request_type': self.order_request_type or '',
            'order_date': self.order_date.isoformat() if self.order_date else '',
            'delivery_target_date': self.delivery_target_date.isoformat() if self.delivery_target_date else '',
            'branch_type': self.branch_type or '',
            'snapshot_date': self.snapshot_date.isoformat() if self.snapshot_date else None
        }

class RejectedWeightSnapshot(db.Model):
    __tablename__ = 'rejection_weight_and_feedback_snapshot'

    id = db.Column(db.Integer, primary_key=True)
    collection_owner = db.Column(db.Text)
    make_owner = db.Column(db.Text)
    supplier = db.Column(db.Text)
    collection = db.Column(db.Text)
    po_number = db.Column(db.Text)
    po_date = db.Column(db.Date)
    total_weight = db.Column(db.Numeric(18, 3))
    order_piece = db.Column(db.Numeric(18, 3))
    order_wt = db.Column(db.Numeric(18, 3))
    accepted_wt = db.Column(db.Numeric(18, 3))
    rejected_wt = db.Column(db.Numeric(18, 3))
    order_type = db.Column(db.Text)
    order_request_type = db.Column(db.Text)
    order_date = db.Column(db.Date)
    snapshot_date = db.Column(db.Date, nullable=False, default=db.func.current_date())
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'collection_owner': self.collection_owner,
            'make_owner': self.make_owner,
            'supplier': self.supplier,
            'collection': self.collection,
            'po_number': self.po_number,
            'po_date': self.po_date.isoformat() if self.po_date else '',
            'total_weight': float(self.total_weight or 0),
            'order_piece': float(self.order_piece or 0),
            'order_wt': float(self.order_wt or 0),
            'accepted_wt': float(self.accepted_wt or 0),
            'rejected_wt': float(self.rejected_wt or 0),
            'order_type': self.order_type or '',
            'order_request_type': self.order_request_type or '',
            'order_date': self.order_date.isoformat() if self.order_date else '',
            'snapshot_date': self.snapshot_date.isoformat() if self.snapshot_date else None
        }

class ReportFeedback(db.Model):
    __tablename__ = 'report_feedback'

    id = db.Column(db.Integer, primary_key=True)
    collection_owner = db.Column(db.Text)
    make_owner = db.Column(db.Text)
    supplier = db.Column(db.Text)
    collection = db.Column(db.Text)
    feedback_text = db.Column(db.Text)
    feedback_category = db.Column(db.String(100))
    username = db.Column(db.String(80))
    page_code = db.Column(db.String(20)) # 'PA', 'RW', 'HD'
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'collection_owner': self.collection_owner,
            'make_owner': self.make_owner,
            'supplier': self.supplier,
            'collection': self.collection,
            'feedback_text': self.feedback_text,
            'feedback_category': self.feedback_category,
            'username': self.username,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class HallmarkingDelayedFeedback(db.Model):
    __tablename__ = 'hallmarking_delayed_feedback'

    id = db.Column(db.Integer, primary_key=True)
    collection_owner = db.Column(db.Text)
    make_owner = db.Column(db.Text)
    supplier = db.Column(db.Text)
    collection = db.Column(db.Text)
    office = db.Column(db.Text)
    hm_agent = db.Column(db.Text)
    feedback_text = db.Column(db.Text)
    feedback_category = db.Column(db.String(100))
    username = db.Column(db.String(80))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'collection_owner': self.collection_owner,
            'make_owner': self.make_owner,
            'supplier': self.supplier,
            'collection': self.collection,
            'office': self.office,
            'hm_agent': self.hm_agent,
            'feedback_text': self.feedback_text,
            'feedback_category': self.feedback_category,
            'username': self.username,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class PendingAcceptanceAction(db.Model):
    __tablename__ = 'pending_acceptance_action'

    id = db.Column(db.Integer, primary_key=True)
    collection_owner = db.Column(db.Text)
    make_owner = db.Column(db.Text)
    supplier = db.Column(db.Text)
    collection = db.Column(db.Text)
    status_filter = db.Column(db.String(50))
    action_type = db.Column(db.String(20)) # 'CONTINUE' or 'CANCEL'
    reason = db.Column(db.Text)
    action_data = db.Column(db.JSON) # Array of {po, weight, delivery_date} for continue or array of POs for cancel
    username = db.Column(db.String(80))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'collection_owner': self.collection_owner,
            'make_owner': self.make_owner,
            'supplier': self.supplier,
            'collection': self.collection,
            'status_filter': self.status_filter,
            'action_type': self.action_type,
            'reason': self.reason,
            'action_data': self.action_data,
            'username': self.username,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }





class ShowroomWiseOrderSummarySnapshot(db.Model):
    __tablename__ = 'showroom_wise_order_summary_snapshot'

    # Primary Key
    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)

    # Columns (Previously Composite Keys)
    po_id = db.Column(db.BigInteger)
    location = db.Column(db.Text)
    supplier = db.Column(db.Text)
    order_type = db.Column(db.Text)
    order_request_type = db.Column(db.Text)
    order_date = db.Column(db.Date)
    po_number = db.Column(db.Text)
    division = db.Column(db.Text)
    group_name = db.Column('group', db.Text)
    purity = db.Column(db.Text)
    classification = db.Column(db.Text)
    make = db.Column(db.Text)
    collection = db.Column(db.Text)

    business_head = db.Column(db.Text)
    party = db.Column(db.Text)
    purchase_ro = db.Column(db.Text)
    provision_type = db.Column(db.Text)
    branch_provision_type = db.Column(db.Text)
    classification_owner = db.Column(db.Text)
    make_owner = db.Column(db.Text)
    collection_owner = db.Column(db.Text)
    order_ro = db.Column(db.Text)
    batch = db.Column(db.Text)
    branch_type = db.Column(db.Text)
    bh_emp_code = db.Column(db.Text)

    order_qty = db.Column(db.Numeric(18, 3))
    order_wt = db.Column(db.Numeric(18, 3))
    cancelled_pcs = db.Column(db.Numeric(18, 3))
    cancelled_wt = db.Column(db.Numeric(18, 3))
    accepted_pcs = db.Column(db.Numeric(18, 3))
    accepted_wt = db.Column(db.Numeric(18, 3))
    pending_to_accepted_pcs = db.Column(db.Numeric(18, 3))
    pending_to_accepted_wt = db.Column(db.Numeric(18, 3))
    rejected_pcs = db.Column(db.Numeric(18, 3))
    rejected_wt = db.Column(db.Numeric(18, 3))
    barcoded_pcs = db.Column(db.Numeric(18, 3))
    barcoded_wt = db.Column(db.Numeric(18, 3))
    not_barcoded_pcs = db.Column(db.Numeric(18, 3))
    not_barcoded_wt = db.Column(db.Numeric(18, 3))

    hm_processed_pcs = db.Column(db.Numeric(18, 3))
    hm_passed_pcs = db.Column(db.Numeric(18, 3))
    hm_passed_wt = db.Column(db.Numeric(18, 3))
    hm_failed_pcs = db.Column(db.Numeric(18, 3))
    hm_failed_wt = db.Column(db.Numeric(18, 3))
    hm_testcut_pcs = db.Column(db.Numeric(18, 3))
    hm_testcut_wt = db.Column(db.Numeric(18, 3))

    qc_processed_pcs = db.Column(db.Numeric(18, 3))
    qc_pending_pcs = db.Column(db.Numeric(18, 3))
    qc_pending_wt = db.Column(db.Numeric(18, 3))
    qc_reject_pcs = db.Column(db.Numeric(18, 3))
    qc_reject_wt = db.Column(db.Numeric(18, 3))
    qc_passed_pcs = db.Column(db.Numeric(18, 3))
    qc_passed_wt = db.Column(db.Numeric(18, 3))

    invoice_pcs = db.Column(db.Numeric(18, 3))
    invoiced_wt = db.Column(db.Numeric(18, 3))
    delivered_pcs = db.Column(db.Numeric(18, 3))
    delivered_wt = db.Column(db.Numeric(18, 3))
    pending_to_deliver_pcs = db.Column(db.Numeric(18, 3))
    pending_to_deliver_wt = db.Column(db.Numeric(18, 3))

    snapshot_date = db.Column(db.Date, nullable=False, default=db.func.current_date())
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'po_id': self.po_id,
            'location': self.location,
            'supplier': self.supplier,
            'order_type': self.order_type,
            'order_request_type': self.order_request_type,
            'order_date': self.order_date.isoformat() if self.order_date else '',
            'po_number': self.po_number,
            'division': self.division,
            'group_name': self.group_name,
            'purity': self.purity,
            'classification': self.classification,
            'make': self.make,
            'collection': self.collection,
            'business_head': self.business_head,
            'party': self.party,
            'purchase_ro': self.purchase_ro,
            'provision_type': self.provision_type,
            'branch_provision_type': self.branch_provision_type,
            'classification_owner': self.classification_owner,
            'make_owner': self.make_owner,
            'collection_owner': self.collection_owner,
            'order_ro': self.order_ro,
            'batch': self.batch,
            'branch_type': self.branch_type or '',
            'bh_emp_code': self.bh_emp_code or '',
            'order_qty': float(self.order_qty or 0),
            'order_wt': float(self.order_wt or 0),
            'cancelled_pcs': float(self.cancelled_pcs or 0),
            'cancelled_wt': float(self.cancelled_wt or 0),
            'accepted_pcs': float(self.accepted_pcs or 0),
            'accepted_wt': float(self.accepted_wt or 0),
            'pending_to_accepted_pcs': float(self.pending_to_accepted_pcs or 0),
            'pending_to_accepted_wt': float(self.pending_to_accepted_wt or 0),
            'rejected_pcs': float(self.rejected_pcs or 0),
            'rejected_wt': float(self.rejected_wt or 0),
            'barcoded_pcs': float(self.barcoded_pcs or 0),
            'barcoded_wt': float(self.barcoded_wt or 0),
            'not_barcoded_pcs': float(self.not_barcoded_pcs or 0),
            'not_barcoded_wt': float(self.not_barcoded_wt or 0),
            'hm_processed_pcs': float(self.hm_processed_pcs or 0),
            'hm_passed_pcs': float(self.hm_passed_pcs or 0),
            'hm_passed_wt': float(self.hm_passed_wt or 0),
            'hm_failed_pcs': float(self.hm_failed_pcs or 0),
            'hm_failed_wt': float(self.hm_failed_wt or 0),
            'hm_testcut_pcs': float(self.hm_testcut_pcs or 0),
            'hm_testcut_wt': float(self.hm_testcut_wt or 0),
            'qc_processed_pcs': float(self.qc_processed_pcs or 0),
            'qc_pending_pcs': float(self.qc_pending_pcs or 0),
            'qc_pending_wt': float(self.qc_pending_wt or 0),
            'qc_reject_pcs': float(self.qc_reject_pcs or 0),
            'qc_reject_wt': float(self.qc_reject_wt or 0),
            'qc_passed_pcs': float(self.qc_passed_pcs or 0),
            'qc_passed_wt': float(self.qc_passed_wt or 0),
            'invoice_pcs': float(self.invoice_pcs or 0),
            'invoiced_wt': float(self.invoiced_wt or 0),
            'delivered_pcs': float(self.delivered_pcs or 0),
            'delivered_wt': float(self.delivered_wt or 0),
            'pending_to_deliver_pcs': float(self.pending_to_deliver_pcs or 0),
            'pending_to_deliver_wt': float(self.pending_to_deliver_wt or 0),
            'snapshot_date': self.snapshot_date.isoformat() if self.snapshot_date else None
        }

class ProvisionStockRawSnapshot(db.Model):
    __tablename__ = 'provision_stock_raw_snapshot'

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    
    # Text / String Identifiers
    division = db.Column(db.String(50))
    group_name = db.Column('group', db.String(50))
    location = db.Column(db.String(100))
    branch_type = db.Column(db.String(100))
    branch_status = db.Column(db.String(100))
    business_head_name = db.Column(db.String(100))
    business_head_emp_code = db.Column(db.String(100))

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
    
    snapshot_date = db.Column(db.Date, nullable=False, default=db.func.current_date())

class HallmarkingDelayedSnapshot(db.Model):
    __tablename__ = 'hallmarking_delayed_snapshot'

    id = db.Column(db.Integer, primary_key=True)
    office = db.Column(db.Text) # hm_ro
    make_owner = db.Column(db.Text)
    collection_owner = db.Column(db.Text)
    collection = db.Column(db.Text)
    hm_agent = db.Column(db.Text)
    supplier = db.Column(db.Text) # Supplier
    challan_date = db.Column(db.Date) # hm.challan_date
    challan_no = db.Column(db.Text) # hm.requested_delivery_challan
    pieces = db.Column(db.Numeric(18, 3)) # 1 Pieces
    weight = db.Column(db.Numeric(18, 3)) # weight
    receipt_date = db.Column(db.Date) # hm.agent_received_on
    receipt_no = db.Column(db.Text) # hm.receipt_no
    hm_status = db.Column(db.Text)
    snapshot_date = db.Column(db.Date, nullable=False, default=db.func.current_date())
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'office': self.office,
            'make_owner': self.make_owner,
            'collection_owner': self.collection_owner,
            'collection': self.collection,
            'hm_agent': self.hm_agent,
            'supplier': self.supplier,
            'challan_date': self.challan_date.isoformat() if self.challan_date else '',
            'challan_no': self.challan_no,
            'pieces': float(self.pieces or 0),
            'weight': float(self.weight or 0),
            'receipt_date': self.receipt_date.isoformat() if self.receipt_date else '',
            'receipt_no': self.receipt_no,
            'hm_status': self.hm_status,
            'snapshot_date': self.snapshot_date.isoformat() if self.snapshot_date else None
        }
