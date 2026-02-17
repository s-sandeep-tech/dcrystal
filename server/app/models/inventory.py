from app.extensions import db
from datetime import datetime

class LocationWiseStockSnapshot(db.Model):
    __tablename__ = "location_wise_stock_snapshot"

    # Snapshot info
    snapshot_date = db.Column(db.Date, primary_key=True)
    
    # Location hierarchy
    location = db.Column(db.String(150), primary_key=True)   # location (branch / store / site)
    zone = db.Column(db.String(120))
    state = db.Column(db.String(120))

    # Ownership / business
    business_head = db.Column(db.String(150))

    # Provision
    provision_pieces = db.Column(db.Integer, default=0, nullable=False)
    provision_weight = db.Column(db.Numeric(14, 3), default=0, nullable=False)

    # Stock
    stock_pieces = db.Column(db.Integer, default=0, nullable=False)
    stock_weight = db.Column(db.Numeric(14, 3), default=0, nullable=False)

    # Short
    short_pieces = db.Column(db.Integer, default=0, nullable=False)
    short_weight = db.Column(db.Numeric(14, 3), default=0, nullable=False)

    # Excess (not in provision)
    excess_not_in_provision_pieces = db.Column(db.Integer, default=0, nullable=False)
    excess_not_in_provision_weight = db.Column(db.Numeric(14, 3), default=0, nullable=False)

    # Max allocation / refill to other branches
    max_pieces_allocate_other_branches = db.Column(db.Integer, default=0, nullable=False)
    max_weight_allocate_other_branches = db.Column(db.Numeric(14, 3), default=0, nullable=False)

    max_refill_pieces_other_branches = db.Column(db.Integer, default=0, nullable=False)
    max_refill_qty_other_branches = db.Column(db.Numeric(14, 3), default=0, nullable=False)

    # Final computed outputs
    final_excess_not_in_provision_pieces = db.Column(db.Integer, default=0, nullable=False)
    final_excess_not_in_provision_qty = db.Column(db.Numeric(14, 3), default=0, nullable=False)

    final_short_pieces = db.Column(db.Integer, default=0, nullable=False)
    final_short_qty = db.Column(db.Numeric(14, 3), default=0, nullable=False)

    def to_dict(self):
        return {
            "snapshot_date": self.snapshot_date.isoformat() if self.snapshot_date else None,
            "location": self.location,
            "zone": self.zone,
            "state": self.state,
            "business_head": self.business_head,
            "provision_pieces": self.provision_pieces,
            "provision_weight": float(self.provision_weight or 0),
            "stock_pieces": self.stock_pieces,
            "stock_weight": float(self.stock_weight or 0),
            "short_pieces": self.short_pieces,
            "short_weight": float(self.short_weight or 0),
            "excess_not_in_provision_pieces": self.excess_not_in_provision_pieces,
            "excess_not_in_provision_weight": float(self.excess_not_in_provision_weight or 0),
            "max_pieces_allocate_other_branches": self.max_pieces_allocate_other_branches,
            "max_weight_allocate_other_branches": float(self.max_weight_allocate_other_branches or 0),
            "max_refill_pieces_other_branches": self.max_refill_pieces_other_branches,
            "max_refill_qty_other_branches": float(self.max_refill_qty_other_branches or 0),
            "final_excess_not_in_provision_pieces": self.final_excess_not_in_provision_pieces,
            "final_excess_not_in_provision_qty": float(self.final_excess_not_in_provision_qty or 0),
            "final_short_pieces": self.final_short_pieces,
            "final_short_qty": float(self.final_short_qty or 0),
        }

class AllocatedBarcodesSnapshot(db.Model):
    __tablename__ = 'allocated_barcodes_snapshot'

    batch_id = db.Column(db.BigInteger, primary_key=True)
    barcode = db.Column(db.BigInteger, primary_key=True)
    collection = db.Column(db.Text)
    section = db.Column(db.Text)
    barcode_weight = db.Column(db.Numeric(14, 3))
    source_location = db.Column(db.Text)
    source_zone = db.Column(db.Text)
    source_state = db.Column(db.Text)
    source_business_head = db.Column(db.Text)
    target_zone = db.Column(db.Text)
    target_state = db.Column(db.Text)
    target_location = db.Column(db.Text)
    target_business_head = db.Column(db.Text)

    def to_dict(self):
        return {
            'barcode': str(self.barcode),
            'collection': self.collection,
            'section': self.section,
            'barcode_weight': float(self.barcode_weight or 0),
            'source_location': self.source_location,
            'target_location': self.target_location
        }
