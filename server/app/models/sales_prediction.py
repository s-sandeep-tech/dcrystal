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
    state_name = db.Column(db.String(100))
    invoice_turnover = db.Column(db.Numeric(24, 4), nullable=False)
    return_turnover = db.Column(db.Numeric(24, 4), nullable=False)
    net_turnover = db.Column(db.Numeric(24, 4), nullable=False)
    source_count = db.Column(db.BigInteger, nullable=False)
    source_updated_at = db.Column(db.DateTime)
    __table_args__ = (db.Index('ix_sales_prediction_run_branch_date', 'run_id', 'branch_id', 'sales_date'),)


class SalesTurnoverForecastRun(db.Model):
    __tablename__ = 'sales_turnover_forecast_runs'
    task_id = db.Column(db.String(100), primary_key=True)
    snapshot_run_id = db.Column(db.String(36), nullable=True)
    branch_id = db.Column(db.Integer)
    requested_by = db.Column(db.Integer, nullable=False)
    include_external = db.Column(db.Boolean, nullable=False, default=False)
    allow_gemini_fallback = db.Column(db.Boolean, nullable=False, default=False, server_default=db.false())
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    result_json = db.Column(db.JSON)
    queued_at = db.Column(db.DateTime)


class SalesPrediction(db.Model):
    __tablename__ = 'sales_predictions'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    branch_id = db.Column(db.Integer, index=True, nullable=True)
    sales_date = db.Column(db.Date, index=True, nullable=False)
    predicted_turnover = db.Column(db.Numeric(24, 4), nullable=False)
    yhat_lower = db.Column(db.Numeric(24, 4))
    yhat_upper = db.Column(db.Numeric(24, 4))
    task_id = db.Column(db.String(100), index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)


def create_sales_prediction_tables():
    for model in (SalesPredictionSyncRun, SalesTurnoverDailySnapshot, SalesTurnoverForecastRun, SalesPrediction):
        model.__table__.create(db.engine, checkfirst=True)
    if db.engine.dialect.name == 'postgresql':
        from sqlalchemy import text, inspect
        with db.engine.begin() as conn:
            if 'state_name' not in {column['name'] for column in inspect(conn).get_columns('sales_turnover_daily_snapshots')}:
                conn.execute(text('ALTER TABLE sales_turnover_daily_snapshots ADD COLUMN IF NOT EXISTS state_name varchar(100)'))
            conn.execute(text('ALTER TABLE sales_turnover_forecast_runs ADD COLUMN IF NOT EXISTS queued_at timestamp'))
            conn.execute(text('ALTER TABLE sales_turnover_forecast_runs ADD COLUMN IF NOT EXISTS allow_gemini_fallback boolean NOT NULL DEFAULT false'))
            conn.execute(text('ALTER TABLE sales_turnover_forecast_runs DROP CONSTRAINT IF EXISTS sales_turnover_forecast_runs_snapshot_run_id_fkey'))
            conn.execute(text('ALTER TABLE sales_turnover_forecast_runs ALTER COLUMN snapshot_run_id DROP NOT NULL'))
            conn.execute(text('CREATE UNIQUE INDEX IF NOT EXISTS uq_sales_predictions_branch ON sales_predictions (branch_id, sales_date) WHERE branch_id IS NOT NULL'))
            conn.execute(text('CREATE UNIQUE INDEX IF NOT EXISTS uq_sales_predictions_all ON sales_predictions (sales_date) WHERE branch_id IS NULL'))
