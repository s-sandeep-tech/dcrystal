"""Read one consistent source snapshot and publish daily totals atomically."""
import logging
import os
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4
from zoneinfo import ZoneInfo

from psycopg2.extras import RealDictCursor
from sqlalchemy import text, func
from app.extensions import db
from app.models.sales_prediction import (
    SalesPredictionSyncRun,
    SalesTurnoverDailySnapshot,
    SalesTurnoverForecastRun,
    create_sales_prediction_tables,
)

logger = logging.getLogger(__name__)
SOURCE = 'ext_view.vw_item_wise_tsk_details_data'


def validate_diagnostics(d, return_sign):
    if not d['source_count']:
        raise ValueError('No completed-day sales history found in source')
    if d['invalid_rows']:
        raise ValueError('Source contains missing dates, branch IDs or turnover; fix before syncing')
    if d.get('date_mismatches'):
        logger.info(f"Source has {d['date_mismatches']} records where date and trans_date differ; COALESCE(trans_date::date, date) used as sales date.")
    if d['duplicate_ids']:
        raise ValueError('Duplicate source IDs found; validate the source view grain')
    if return_sign not in ('signed', 'positive'):
        raise ValueError('SALES_PREDICTION_RETURN_SIGN must be signed or positive')
    if (return_sign == 'signed' and d['positive_returns']) or (return_sign == 'positive' and d['negative_returns']):
        raise ValueError('SR sign does not match SALES_PREDICTION_RETURN_SIGN; verify return amounts')


def sync_sales_prediction_data_task():
    from app.utils.sync_tasks import get_external_db_connection, emit_sync_update
    emit = lambda status, message, progress: emit_sync_update(status, message, progress, 'sales_prediction_data')
    conn = None
    try:
        create_sales_prediction_tables()
        if not db.session.execute(text('SELECT pg_try_advisory_xact_lock(80321642)')).scalar():
            raise ValueError('Sales prediction sync is already running')
        emit('processing', 'Validating daily sales source...', 5)
        cutoff = datetime.now(ZoneInfo('Asia/Kolkata')).date() - timedelta(days=1)
        return_sign = os.getenv('SALES_PREDICTION_RETURN_SIGN', 'signed')
        conn = get_external_db_connection()
        conn.set_session(isolation_level='REPEATABLE READ', readonly=True, autocommit=False)
        # Include invalid undated records in diagnostics rather than silently dropping them.
        where = "trans_type IN ('INVOICE', 'SR') AND (COALESCE(trans_date::date, date) <= %s OR COALESCE(trans_date::date, date) IS NULL)"
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(f"""SELECT COUNT(*) AS source_count,
                COUNT(*) FILTER (WHERE branch_id IS NULL OR turn_over IS NULL OR id IS NULL
                    OR COALESCE(trans_date::date, date) IS NULL) AS invalid_rows,
                COUNT(*) FILTER (WHERE date IS NOT NULL AND trans_date IS NOT NULL AND date <> trans_date::date) AS date_mismatches,
                COUNT(id) - COUNT(DISTINCT id) AS duplicate_ids,
                COUNT(*) FILTER (WHERE trans_type = 'SR' AND turn_over > 0) AS positive_returns,
                COUNT(*) FILTER (WHERE trans_type = 'SR' AND turn_over < 0) AS negative_returns,
                MIN(COALESCE(trans_date::date, date)) AS first_date,
                MAX(COALESCE(trans_date::date, date)) AS last_date,
                SUM(CASE WHEN trans_type = 'INVOICE' THEN turn_over ELSE 0 END) AS invoice_total,
                SUM(CASE WHEN trans_type = 'SR' THEN turn_over ELSE 0 END) AS return_total
                FROM {SOURCE} WHERE {where}""", (cutoff,))
            diagnostics = dict(cur.fetchone())
        validate_diagnostics(diagnostics, return_sign)
        multiplier = -1 if return_sign == 'positive' else 1
        expected = Decimal(diagnostics['invoice_total'] or 0) + multiplier * Decimal(diagnostics['return_total'] or 0)
        run_id = str(uuid4())
        run = SalesPredictionSyncRun(id=run_id, cutoff_date=diagnostics['last_date'], first_date=diagnostics['first_date'],
            row_count=0, source_count=diagnostics['source_count'], net_turnover=expected,
            diagnostics={k: str(v) if isinstance(v, (Decimal, datetime)) or hasattr(v, 'isoformat') else v for k, v in diagnostics.items()})
        run.diagnostics = {**run.diagnostics, 'return_sign': return_sign, 'requested_cutoff': cutoff.isoformat(),
                           'source': SOURCE, 'missing_days_policy': 'Zero within the observed branch history after full-source sync'}
        db.session.add(run)
        db.session.flush()
        rows_count, source_count, total = 0, 0, Decimal(0)
        with conn.cursor(name='sales_prediction_daily', cursor_factory=RealDictCursor) as cur:
            cur.itersize = 20000
            cur.execute(f"""SELECT COALESCE(trans_date::date, date) AS sales_date, branch_id,
                COALESCE(MAX(NULLIF(TRIM(location_name), '')), branch_id::text) AS location_name,
                SUM(CASE WHEN trans_type = 'INVOICE' THEN turn_over ELSE 0 END) AS invoice_turnover,
                SUM(CASE WHEN trans_type = 'SR' THEN turn_over ELSE 0 END) * %s AS return_turnover,
                COUNT(*) AS source_count, MAX(last_updated_at) AS source_updated_at
                FROM {SOURCE} WHERE {where}
                GROUP BY COALESCE(trans_date::date, date), branch_id ORDER BY 1, 2""", (multiplier, cutoff))
            while True:
                batch = cur.fetchmany(20000)
                if not batch:
                    break
                values = []
                for row in batch:
                    item = dict(row)
                    item.update(run_id=run_id, net_turnover=item['invoice_turnover'] + item['return_turnover'])
                    total += item['net_turnover']
                    source_count += item['source_count']
                    values.append(item)
                db.session.execute(SalesTurnoverDailySnapshot.__table__.insert(), values)
                rows_count += len(values)
                emit('processing', f'Loaded {rows_count:,} daily branch totals', 70)
        stored_total = db.session.query(func.sum(SalesTurnoverDailySnapshot.net_turnover)).filter_by(run_id=run_id).scalar()
        if (source_count != diagnostics['source_count'] or abs(total - expected) > Decimal('0.0001')
                or abs(Decimal(stored_total) - expected) > Decimal('0.0001')):
            raise ValueError('Source/local sales reconciliation failed')
        run.row_count = rows_count
        db.session.commit()

        # Do not keep version history: remove older sync runs, snapshots, and forecasts
        try:
            db.session.query(SalesTurnoverDailySnapshot).filter(SalesTurnoverDailySnapshot.run_id != run_id).delete()
            db.session.query(SalesTurnoverForecastRun).filter(SalesTurnoverForecastRun.snapshot_run_id != run_id).delete()
            db.session.query(SalesPredictionSyncRun).filter(SalesPredictionSyncRun.id != run_id).delete()
            db.session.commit()
        except Exception as purge_err:
            logger.warning(f"Could not purge previous prediction versions: {purge_err}")
            db.session.rollback()

        emit('success', f'Sales prediction history synced: {rows_count:,} daily totals through {run.cutoff_date}', 100)
        return {'status': 'success', 'count': rows_count, 'run_id': run_id}
    except Exception as error:
        db.session.rollback()
        logger.exception('Sales prediction sync failed')
        emit('error', str(error), 0)
        return {'status': 'error', 'message': str(error)}
    finally:
        if conn:
            conn.close()
