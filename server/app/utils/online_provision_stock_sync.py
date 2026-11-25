"""Independent, staged sync for ext_view.vw_online_sku_stock_details.

Field mapping is identical to the physical-stock snapshot. Missing fields fail
validation rather than silently substituting physical-stock data or zeroes.
"""
import logging
from datetime import datetime
from decimal import Decimal

from psycopg2.extras import RealDictCursor
from sqlalchemy import func, text

from app.extensions import db
from app.models.online_provision_stock import OnlineProvisionStockRawSnapshot as Snapshot
from app.models.online_provision_stock import OnlineProvisionStockRawStaging as Staging

logger = logging.getLogger(__name__)
SOURCE = 'ext_view.vw_online_sku_stock_details'
TASK = 'online_provision_stock_status'
BATCH_SIZE = 20000


def source_columns():
    return ['last_updated_at' if c.name == 'snapshot_date' else c.name
            for c in Snapshot.__table__.columns if c.name != 'id']


def validate_source_columns(description):
    available = {(c.name if hasattr(c, 'name') else c[0]) for c in description}
    missing = sorted(set(source_columns()) - available)
    if missing:
        raise ValueError(
            f'{SOURCE} is missing required columns: {", ".join(missing)}. '
            'The online source needs an explicit field mapping. '
            f'Available source columns: {", ".join(sorted(available))}'
        )


def map_source_row(row, started_at):
    # Attribute `group_name` deliberately maps the external SQL column `group`.
    return {('group_name' if c.name == 'group' else c.name):
            ((row.get('last_updated_at') or started_at) if c.name == 'snapshot_date' else row[c.name])
            for c in Snapshot.__table__.columns if c.name != 'id'}


def publish_staging(expected_count, expected_weight):
    """Validate before replacement; snapshot replacement is one transaction."""
    local_count, local_weight = db.session.query(
        func.count(Staging.id), func.sum(Staging.prov_gr_wt)).one()
    if local_count != expected_count or abs(Decimal(local_weight or 0) - Decimal(expected_weight or 0)) >= Decimal('0.001'):
        raise ValueError('Online stock staging validation failed; previous snapshot retained')
    # DELETE is transactional on both PostgreSQL and the SQLite regression DB.
    # Only online tables participate; readers keep the last committed snapshot.
    db.session.query(Snapshot).delete(synchronize_session=False)
    columns = [c.name for c in Snapshot.__table__.columns if c.name != 'id']
    quoted = ', '.join('"' + name + '"' for name in columns)
    db.session.execute(text(
        f'INSERT INTO {Snapshot.__tablename__} ({quoted}) SELECT {quoted} FROM {Staging.__tablename__}'))
    db.session.query(Staging).delete(synchronize_session=False)
    db.session.commit()


def sync_online_provision_stock_status_data_task():
    # Lazy imports avoid importing the large shared sync module at report startup.
    from app.utils.sync_tasks import get_external_db_connection, emit_sync_update

    conn = None
    lock = None
    locked = False
    started_at = datetime.utcnow()
    try:
        # Serialize independent online refreshes, including direct/manual calls.
        if db.engine.dialect.name == 'postgresql':
            lock = db.engine.connect()
            locked = bool(lock.execute(text('SELECT pg_try_advisory_lock(731402811)')).scalar())
            if not locked:
                raise RuntimeError('An Online Provision Stock status sync is already running')
        emit_sync_update('processing', 'Preparing Online Provision Stock status sync...', 5, TASK)
        conn = get_external_db_connection()
        conn.set_session(readonly=True, isolation_level='REPEATABLE READ')
        with conn.cursor() as cur:
            cur.execute("SET LOCAL statement_timeout = '300s'")
            cur.execute(f'SELECT * FROM {SOURCE} LIMIT 0')
            validate_source_columns(cur.description)
            cur.execute(f'SELECT COUNT(*), SUM(prov_gr_wt) FROM {SOURCE}')
            expected_count, expected_weight = cur.fetchone()
        # Complete the metadata/count checks before clearing the staging table.
        db.session.query(Staging).delete(synchronize_session=False)
        db.session.commit()
        total = 0
        columns = ', '.join('"' + c + '"' for c in source_columns())
        with conn.cursor(name='online_provision_stock_rows', cursor_factory=RealDictCursor) as cur:
            cur.itersize = BATCH_SIZE
            cur.execute(f'SELECT {columns} FROM {SOURCE}')
            while True:
                rows = cur.fetchmany(BATCH_SIZE)
                if not rows:
                    break
                db.session.bulk_insert_mappings(Staging, [map_source_row(row, started_at) for row in rows])
                db.session.commit()
                total += len(rows)
                progress = 10 + min(80, int(total * 80 / max(1, expected_count)))
                emit_sync_update('processing', f'Online stock: {total:,} / {expected_count:,} records...', progress, TASK)
        emit_sync_update('processing', 'Validating and publishing online stock...', 95, TASK)
        publish_staging(expected_count, expected_weight)
        snapshot_date = db.session.query(func.max(Snapshot.snapshot_date)).scalar()
        metadata = {
            'snapshot_version': snapshot_date.isoformat() if snapshot_date else started_at.isoformat(),
            'sync_time': (snapshot_date or started_at).strftime('%d, %I:%M %p'),
            'validation_passed': True,
        }
        emit_sync_update('success', f'Online Provision Stock status synced and validated: {total:,} records.', 100, TASK, metadata=metadata)
        return {'status': 'success', 'count': total, 'validation': {'match': True}}
    except Exception as exc:
        db.session.rollback()
        logger.exception('Online Provision Stock status sync failed')
        emit_sync_update('error', f'Online Provision Stock status sync failed: {exc}', 0, TASK)
        return {'status': 'error', 'message': str(exc)}
    finally:
        if conn is not None:
            conn.close()
        if lock is not None:
            try:
                if locked:
                    lock.execute(text('SELECT pg_advisory_unlock(731402811)'))
                    lock.commit()
            finally:
                lock.close()
