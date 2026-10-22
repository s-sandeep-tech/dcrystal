from datetime import datetime
from app.extensions import db


class SalesPredictionSyncRun(db.Model):
    __tablename__ = 'sales_prediction_sync_runs'
    id = db.Column(db.String(36), primary_key=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    cutoff_date = db.Column(db.Date, nullable=False)
    first_date = db.Column(db.Date, nullable=False)
    row_count = db.Column(db.Integer, nullable=False)
    source_count = db.Column(db.BigInteger, nullable=False)
    net_turnover = db.Column(db.Numeric(24, 4), nullable=False)
    diagnostics = db.Column(db.JSON, nullable=False)


class SalesTurnoverDailySnapshot(db.Model):
    __tablename__ = 'sales_turnover_daily_snapshots'
    run_id = db.Column(db.String(36), db.ForeignKey('sales_prediction_sync_runs.id'), primary_key=True)
    sales_date = db.Column(db.Date, primary_key=True)
    branch_id = db.Column(db.Integer, primary_key=True)
    location_name = db.Column(db.String(200), nullable=False)
    invoice_turnover = db.Column(db.Numeric(24, 4), nullable=False)
    return_turnover = db.Column(db.Numeric(24, 4), nullable=False)
    net_turnover = db.Column(db.Numeric(24, 4), nullable=False)
    source_count = db.Column(db.BigInteger, nullable=False)
    source_updated_at = db.Column(db.DateTime)
    __table_args__ = (db.Index('ix_sales_prediction_run_branch_date', 'run_id', 'branch_id', 'sales_date'),)


class SalesTurnoverForecastRun(db.Model):
    __tablename__ = 'sales_turnover_forecast_runs'
    task_id = db.Column(db.String(100), primary_key=True)
    snapshot_run_id = db.Column(db.String(36), db.ForeignKey('sales_prediction_sync_runs.id'), nullable=False)
    branch_id = db.Column(db.Integer)
    requested_by = db.Column(db.Integer, nullable=False)
    include_external = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    result_json = db.Column(db.JSON)
    queued_at = db.Column(db.DateTime)


def create_sales_prediction_tables():
    for model in (SalesPredictionSyncRun, SalesTurnoverDailySnapshot, SalesTurnoverForecastRun):
        model.__table__.create(db.engine, checkfirst=True)
    if db.engine.dialect.name == 'postgresql':
        from sqlalchemy import text
        with db.engine.begin() as conn:
            conn.execute(text('ALTER TABLE sales_turnover_forecast_runs ADD COLUMN IF NOT EXISTS queued_at timestamp'))
