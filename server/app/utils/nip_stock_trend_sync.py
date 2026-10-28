"""Atomic, streaming full-history import; failed imports retain the previous data."""
import logging
from datetime import datetime
from psycopg2.extras import RealDictCursor
from sqlalchemy import text, func
from app.extensions import db
from app.models.nip_stock_trend import NIPStockTrendSnapshot as S, SOURCE_COLUMNS

SOURCE = 'ext_view.vw_weight_level_excess_nip_barcode_data'
logger = logging.getLogger(__name__)


def sync_nip_stock_trend_task():
    from app.utils.sync_tasks import get_external_db_connection, emit_sync_update
    emit = lambda status, message, progress: emit_sync_update(status, message, progress, 'nip_stock_trend')
    conn = None
    try:
        S.__table__.create(db.engine, checkfirst=True)
        if not db.session.execute(text('SELECT pg_try_advisory_xact_lock(80321643)')).scalar():
            raise ValueError('NIP trend sync is already running')
        emit('processing', 'Reading dated NIP barcode history...', 5)
        conn = get_external_db_connection()
        conn.set_session(isolation_level='REPEATABLE READ', readonly=True, autocommit=False)
        with conn.cursor() as cur:
            cur.execute(f'''SELECT COUNT(*), COUNT(*) FILTER (WHERE date IS NULL OR uid IS NULL),
                COUNT(*) - COUNT(DISTINCT (date, uid)), SUM(gross_wt), SUM(pieces) FROM {SOURCE}''')
            count, missing, duplicates, weight, pieces = cur.fetchone()
        if not count or missing or duplicates:
            raise ValueError('Source empty or has missing/duplicate (date, uid) keys; previous snapshot preserved')
        with conn.cursor() as dates_cursor:
            dates_cursor.execute(f'SELECT DISTINCT date FROM {SOURCE}')
            source_dates = [row[0] for row in dates_cursor.fetchall()]
        # Refresh authoritative source dates, retaining older daily balances.
        db.session.query(S).filter(S.date.in_(source_dates)).delete(synchronize_session=False)
        columns = ', '.join('"' + name + '"' for name in SOURCE_COLUMNS)
        loaded, synced_at = 0, datetime.utcnow()
        with conn.cursor(name='nip_stock_trend_sync', cursor_factory=RealDictCursor) as cur:
            cur.itersize = 20000
            cur.execute(f'SELECT {columns} FROM {SOURCE}')
            while True:
                batch = cur.fetchmany(20000)
                if not batch:
                    break
                records = []
                for row in batch:
                    item = dict(row)
                    item.update(uid=str(item['uid']), synced_at=synced_at)
                    records.append(item)
                db.session.execute(S.__table__.insert(), records)
                loaded += len(records)
                emit('processing', f'Loaded {loaded:,} of {count:,} history rows', min(95, 10 + int(loaded / count * 85)))
        local = db.session.query(func.count(S.id), func.sum(S.gross_wt), func.sum(S.pieces)).filter(S.date.in_(source_dates)).one()
        if loaded != count or local[0] != count or (local[1] or 0) != (weight or 0) or (local[2] or 0) != (pieces or 0):
            raise ValueError('Source and local row/weight/pieces reconciliation failed')
        db.session.commit()
        emit('success', f'NIP stock history synced: {loaded:,} rows', 100)
        return {'status': 'success', 'count': loaded}
    except Exception as error:
        db.session.rollback()
        logger.exception('NIP stock trend sync failed')
        emit('error', str(error), 0)
        return {'status': 'error', 'message': str(error)}
    finally:
        if conn:
            conn.close()
