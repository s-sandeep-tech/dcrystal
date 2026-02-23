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
    order_type = db.Column('order_type', db.Text, primary_key=True)
    
    classification_owner = db.Column('Classification Owner', db.Text)
    collection_owner = db.Column('Collection Owner', db.Text)
    make_owner = db.Column('Make Owner', db.Text)
    
    ordered_pcs = db.Column('Ordered Pcs', db.Numeric(18, 3))
    ordered_wt = db.Column('Ordered Wt', db.Numeric(18, 3))
    accepted_pcs = db.Column('Accepted Pcs', db.Numeric(18, 3))
    accepted_wt = db.Column('Accepted Wt', db.Numeric(18, 3))
    rejected_pcs = db.Column('Rejected Pcs', db.Numeric(18, 3))
    rejected_wt = db.Column('Rejected Wt', db.Numeric(18, 3))
    barcoded_pcs = db.Column('Barcoded Pcs', db.Numeric(18, 3))
    barcoded_wt = db.Column('Barcoded Wt', db.Numeric(18, 3))
    not_barcoded_pcs = db.Column('Not Barcod Pcs', db.Numeric(18, 3))
    not_barcoded_wt = db.Column('Not Barcode Wt', db.Numeric(18, 3))
    
    hm_processed_pcs = db.Column('Hm Processed Pcs', db.Numeric(18, 3))
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

