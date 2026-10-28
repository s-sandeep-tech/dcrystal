"""Dated barcode balances for NIP stock trend reporting."""
from datetime import datetime
from app.extensions import db

TEXT_FIELDS = ('location', 'division', 'group_name', 'purity', 'classification',
               'sub_classification', 'make', 'master_collection', 'collection',
               'sub_section', 'section', 'type', 'gender', 'wide_range',
               'barcode_no', 'prov_type', 'design_no', 'branch_type')
ID_FIELDS = ('prov_type_filter', 'branch_id', 'division_id', 'group_id', 'purity_id',
             'classification_id', 'sub_classification_id', 'make_id', 'master_collection_id',
             'collection_id', 'sub_section_id', 'section_id', 'type_id', 'gender_id',
             'wide_range_id', 'design_id', 'item_definition_id')
BOOL_FIELDS = ('is_nip', 'is_excess', 'is_franchise', 'is_to_be_replaced')


class NIPStockTrendSnapshot(db.Model):
    __tablename__ = 'nip_stock_trend_snapshots'
    id = db.Column(db.BigInteger().with_variant(db.Integer, 'sqlite'), primary_key=True)
    date = db.Column(db.Date, nullable=False, index=True)
    uid = db.Column(db.String(36), nullable=False)
    weight = db.Column(db.Numeric)
    gross_wt = db.Column(db.Numeric)
    pieces = db.Column(db.Integer)
    last_updated_at = db.Column(db.DateTime)
    synced_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    for field in TEXT_FIELDS:
        locals()[field] = db.Column(db.Text)
    for field in ID_FIELDS:
        locals()[field] = db.Column(db.Integer)
    for field in BOOL_FIELDS:
        locals()[field] = db.Column(db.Boolean)
    del field
    __table_args__ = (db.UniqueConstraint('date', 'uid', name='uq_nip_trend_date_uid'),
                     db.Index('ix_nip_trend_scope', 'is_nip', 'branch_id', 'date'))


SOURCE_COLUMNS = TEXT_FIELDS + ID_FIELDS + BOOL_FIELDS + ('date', 'uid', 'weight', 'gross_wt', 'pieces', 'last_updated_at')
