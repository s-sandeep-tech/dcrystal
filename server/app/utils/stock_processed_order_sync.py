"""Refresh the latest dated processed-order details without publishing partial data."""
import logging
import time

from psycopg2.extras import RealDictCursor
from sqlalchemy import Column, Date, Index, Integer, Numeric, Table, Text, text

from app.extensions import db

SOURCE = 'ext_view.vw_stock_processed_order_details'
TASK = 'stock_processed_order_details'
COMBINED_TASK = 'stock_drilldown_details'
IDENTITY_FIELDS = (
    'division_id', 'group_id', 'purity_id', 'classification_id',
    'sub_classification_id', 'make_id', 'master_collection_id',
    'collection_id', 'sub_section_id', 'section_id', 'type_id',
    'gender_id', 'wide_range_id', 'size_id', 'screw_type_id',
)
TABLE = Table(
    'stock_processed_order_details_snapshot', db.metadata,
    Column('id', Integer, primary_key=True),
    Column('branch_id', Integer),
    *(Column(name, Integer) for name in IDENTITY_FIELDS),
    Column('group_category_id', Integer), Column('order_request_id', Integer),
    *(Column(name, Text) for name in ('location', 'order_no', 'supplier',
                                     'design_no', 'process_status', 'current_status')),
    *(Column(name, Numeric) for name in ('range_weight', 'quantity', 'gross_weight')),
    Column('order_date', Date), Column('date', Date, nullable=False),
    Index('ix_processed_order_location_section', 'location', 'section_id'),
    Index('ix_processed_order_branch_section', 'branch_id', 'section_id'),
)
SOURCE_COLUMNS = tuple(c.name for c in TABLE.columns if c.name != 'id')
logger = logging.getLogger(__name__)


def sync_stock_drilldown_details():
    from app.utils.sync_tasks import emit_sync_update, sync_size_level_nip_barcode_task

    failures = []
    count = 0
    steps = (
        ('Size Level NIP Barcode', sync_size_level_nip_barcode_task),
        ('Stock Processed Order Details', sync_stock_processed_order_details),
    )
    for index, (label, run) in enumerate(steps):
        emit_sync_update('processing', f'Syncing {label} ({index + 1}/2)', 5 + index * 50, COMBINED_TASK)
        try:
            result = run()
            if result.get('status') == 'success':
                count += result.get('count') or 0
            else:
                failures.append(f"{label}: {result.get('message') or 'Sync failed'}")
        except Exception:
            db.session.rollback()
            logger.exception('%s sync failed', label)
            failures.append(f'{label}: Sync failed')
    status = 'error' if failures else 'success'
    message = '; '.join(failures) if failures else 'Barcode and processed order details synced.'
    emit_sync_update(status, message, 0 if failures else 100, COMBINED_TASK)
    return {'status': status, 'message': message, 'count': count}


def sync_stock_processed_order_details():
    from app.utils.sync_tasks import emit_sync_update, get_external_db_connection

    for attempt in range(1, 4):
        conn = None
        try:
            emit_sync_update('processing', f'Reading processed orders (attempt {attempt}/3)', 5, TASK)
            if not db.session.execute(text('SELECT pg_try_advisory_xact_lock(80321644)')).scalar():
                raise ValueError('Processed order details sync is already running.')
            TABLE.create(db.session.connection(), checkfirst=True)
            conn = get_external_db_connection()
            conn.set_session(readonly=True, autocommit=False)
            columns = ', '.join(f'"{name}"' for name in SOURCE_COLUMNS)
            loaded = 0
            with conn.cursor(name='processed_order_details_sync', cursor_factory=RealDictCursor) as cursor:
                cursor.execute(f'SELECT {columns} FROM {SOURCE} WHERE date = (SELECT MAX(date) FROM {SOURCE})')
                batch = cursor.fetchmany(10000)
                if not batch:
                    raise ValueError('No dated processed orders found; previous snapshot preserved.')
                db.session.execute(TABLE.delete())
                while batch:
                    db.session.execute(TABLE.insert(), [dict(row) for row in batch])
                    loaded += len(batch)
                    emit_sync_update('processing', f'Loaded {loaded:,} processed order records', 80, TASK)
                    batch = cursor.fetchmany(10000)
            db.session.commit()
        except Exception as error:
            db.session.rollback()
            logger.exception('Processed order details sync failed')
            if attempt == 3 or isinstance(error, ValueError):
                emit_sync_update('error', str(error), 0, TASK)
                return {'status': 'error', 'message': str(error)}
        else:
            emit_sync_update('success', f'Synced {loaded:,} processed order records', 100, TASK)
            return {'status': 'success', 'count': loaded}
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    logger.warning('Could not close processed-order source connection', exc_info=True)
        time.sleep(5 * attempt)
