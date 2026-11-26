"""Independent, staged sync for ext_view.vw_online_sku_stock_details.

Only fields consumed by the report are required from the online source. Source
weight aliases map to the existing snapshot fields without changing report SQL.
"""
import logging
from datetime import datetime
from decimal import Decimal

from psycopg2.extras import RealDictCursor
from sqlalchemy import func, inspect, text

from app.extensions import db
from app.models.online_provision_stock import OnlineProvisionStockRawSnapshot as Snapshot
from app.models.online_provision_stock import OnlineProvisionStockRawStaging as Staging

logger = logging.getLogger(__name__)
SOURCE = 'ext_view.vw_online_sku_stock_details'
TASK = 'online_provision_stock_status'
BATCH_SIZE = 20000


# Keep this projection explicit: the snapshot also contains unused legacy
# columns copied from physical stock, which the online view need not supply.
REPORT_SOURCE_COLUMNS = (
    'location', 'division', 'group', 'purity', 'classification',
    'sub_classification', 'make', 'master_collection', 'collection',
    'section', 'sub_section', 'type', 'gender', 'wide_range', 'screw_type', 'size',
    'provision_weight', 'in_shop_wt', 'in_transit_wt', 'ordered_wt',
    'prov_pieces', 'in_shop_pcs', 'in_transit', 'req_only', 'range_weight',
    'branch_id', 'branch_type', 'branch_status', 'business_head_name',
    'business_head_emp_code', 'state', 'prov_type', 'provision_mode_filter',
    'division_id', 'group_id', 'purity_id', 'classification_id',
    'sub_classification_id', 'section_id', 'type_id', 'make_id',
    'collection_id', 'master_collection_id', 'sub_section_id',
    'wide_range_id', 'gender_id', 'size_id', 'screw_type_id', 'design_no', 'design_uid',
)
SOURCE_TO_SNAPSHOT = {
    'group': 'group_name',
    'provision_weight': 'prov_gr_wt',
    # The source's ordered_wt EXCLUDES req_only; the unchanged report adds it.
    'ordered_wt': 'order_only_wt',
}


def source_columns():
    return list(REPORT_SOURCE_COLUMNS)


def validate_source_columns(description):
    available = {(c.name if hasattr(c, 'name') else c[0]) for c in description}
    missing = sorted(set(REPORT_SOURCE_COLUMNS) - available)
    if missing:
        raise ValueError(
            f'{SOURCE} is missing required report columns: {", ".join(missing)}. '
            f'Available source columns: {", ".join(sorted(available))}'
        )


def map_source_row(row, started_at):
    # Explicit NULLs for unused legacy fields, never fabricated stock metrics.
    mapped = {('group_name' if c.name == 'group' else c.name): None
              for c in Snapshot.__table__.columns if c.name != 'id'}
    for name in REPORT_SOURCE_COLUMNS:
        value = row[name]
        if name.endswith('_id') and value is not None:
            # branch_id is NUMERIC in the source, INTEGER in the snapshot.
            # Reject fractional identifiers rather than rounding to another branch.
            numeric = Decimal(str(value))
            if not numeric.is_finite() or numeric != numeric.to_integral_value():
                raise ValueError(f'Invalid non-integer {name}: {value}')
            value = int(numeric)
        elif name in ('size', 'design_uid') and value is not None:
            value = str(value)
        mapped[SOURCE_TO_SNAPSHOT.get(name, name)] = value
    # Each successful sync gets its own timestamp/cache generation; no source
    # last_updated_at column is required or used to disguise stale snapshots.
    mapped['snapshot_date'] = started_at
    return mapped


def ensure_online_tables():
    """Create/upgrade only online tables without replacing existing stock rows."""
    with db.engine.begin() as connection:
        for model in (Snapshot, Staging):
            model.__table__.create(connection, checkfirst=True)
            existing = {c['name'] for c in inspect(connection).get_columns(model.__tablename__)}
            for column, sql_type in (('design_no', 'VARCHAR(100)'), ('design_uid', 'TEXT')):
                if column not in existing:
                    guard = 'IF NOT EXISTS ' if connection.dialect.name == 'postgresql' else ''
                    connection.execute(text(f'ALTER TABLE {model.__tablename__} ADD COLUMN {guard}{column} {sql_type}'))


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
            cur.execute(f'SELECT COUNT(*), SUM(provision_weight) FROM {SOURCE}')
            expected_count, expected_weight = cur.fetchone()
        # Source checks complete; prepare/upgrade only the online tables.
        ensure_online_tables()
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
