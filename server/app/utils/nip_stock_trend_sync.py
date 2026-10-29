"""Short source reads, validated local staging, and atomic history publication."""
import logging
import time
from datetime import datetime
from uuid import uuid4
from psycopg2.extras import RealDictCursor
from sqlalchemy import text, func, Table, Column, MetaData, Numeric, UniqueConstraint, select, or_
from app.extensions import db
from app.models.nip_stock_trend import NIPStockTrendSnapshot as S, SOURCE_COLUMNS

SOURCE = 'ext_view.vw_weight_level_excess_nip_barcode_data'
BATCH_SIZE = 1000
logger = logging.getLogger(__name__)
COLUMNS_SQL = ', '.join('"' + name + '"' for name in SOURCE_COLUMNS)
HASH_SQL = f'md5(ROW({COLUMNS_SQL})::text)'


def _source_manifest(conn):
    # Each statement owns its source snapshot; no source transaction spans pages.
    with conn.cursor() as cur:
        cur.execute(f'''SELECT date, COUNT(*),
            COUNT(*) FILTER (WHERE date IS NULL OR uid IS NULL),
            COUNT(*) - COUNT(DISTINCT uid), SUM(gross_wt), SUM(pieces),
            SUM(('x' || substr({HASH_SQL}, 1, 16))::bit(64)::bigint::numeric),
            SUM(('x' || substr({HASH_SQL}, 17, 16))::bit(64)::bigint::numeric)
            FROM {SOURCE} GROUP BY date ORDER BY date''')
        rows = cur.fetchall()
    if not rows or any(not row[0] or row[2] or row[3] for row in rows):
        raise ValueError('Source empty or has missing/duplicate (date, uid) keys; previous snapshot preserved')
    return {row[0]: tuple(value or 0 for value in row[1:]) for row in rows}


def _staging_table():
    return Table('nip_trend_stage_' + uuid4().hex, MetaData(),
                 *(Column(name, S.__table__.c[name].type, nullable=S.__table__.c[name].nullable)
                   for name in (*SOURCE_COLUMNS, 'synced_at')),
                 Column('checksum_a', Numeric(38, 0), nullable=False),
                 Column('checksum_b', Numeric(38, 0), nullable=False),
                 UniqueConstraint('date', 'uid'), prefixes=['TEMPORARY'], postgresql_on_commit='DROP')


def _signed_hash(part):
    value = int(part, 16)
    return value - (1 << 64) if value >= (1 << 63) else value


def sync_nip_stock_trend_task():
    from app.utils.sync_tasks import emit_sync_update
    for attempt in range(1, 4):
        logger.info('NIP stock trend sync starting attempt %s/3 (batch size %s)', attempt, BATCH_SIZE)
        result = _sync_nip_stock_trend_attempt()
        if result['status'] == 'success':
            return result
        if not result.pop('retryable', False) or attempt == 3:
            emit_sync_update('error', result['message'], 0, 'nip_stock_trend')
            return result
        delay = attempt * 5
        message = f'NIP stock trend sync attempt {attempt}/3 failed; retrying in {delay}s: {result["message"]}'
        logger.warning(message)
        emit_sync_update('processing', message, 0, 'nip_stock_trend')
        time.sleep(delay)


def _sync_nip_stock_trend_attempt():
    from app.utils.sync_tasks import get_external_db_connection, emit_sync_update
    emit = lambda status, message, progress: emit_sync_update(status, message, progress, 'nip_stock_trend')
    conn = stage = None
    committed = False
    try:
        S.__table__.create(db.engine, checkfirst=True)
        if not db.session.execute(text('SELECT pg_try_advisory_xact_lock(80321643)')).scalar():
            raise ValueError('NIP trend sync is already running')
        stage = _staging_table()
        stage.create(db.session.connection())
        emit('processing', 'Validating NIP barcode history before paginated import...', 5)
        conn = get_external_db_connection()
        conn.set_session(isolation_level='READ COMMITTED', readonly=True, autocommit=True)
        logger.info('NIP source connected; validating source history')
        before = _source_manifest(conn)
        count = sum(row[0] for row in before.values())
        logger.info('NIP source validated: rows=%s, dates=%s', count, len(before))
        loaded, synced_at = 0, datetime.utcnow()
        last_key = None
        while True:
            started = time.monotonic()
            logger.info('NIP source fetching page %s; staged=%s/%s', loaded // BATCH_SIZE + 1, loaded, count)
            where = 'WHERE (date, uid) > (%s::date, %s::uuid)' if last_key else ''
            params = (*last_key, BATCH_SIZE) if last_key else (BATCH_SIZE,)
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(f'''SELECT {COLUMNS_SQL}, {HASH_SQL} AS _source_hash
                    FROM {SOURCE} {where} ORDER BY date, uid LIMIT %s''', params)
                batch = cur.fetchall()
            logger.info('NIP source fetched %s rows in %.2fs (source transaction finished)', len(batch), time.monotonic() - started)
            if not batch:
                break
            records = []
            for row in batch:
                item = dict(row)
                digest = item.pop('_source_hash')
                item.update(uid=str(item['uid']), synced_at=synced_at,
                            checksum_a=_signed_hash(digest[:16]), checksum_b=_signed_hash(digest[16:]))
                records.append(item)
            next_key = (records[-1]['date'], records[-1]['uid'])
            if last_key and next_key <= last_key:
                raise RuntimeError('Source keyset did not advance; previous snapshot preserved')
            db.session.execute(stage.insert(), records)
            loaded += len(records)
            if loaded > count:
                raise RuntimeError('Source grew during pagination; retrying with fresh staging')
            last_key = next_key
            emit('processing', f'Staged {loaded:,} of {count:,} history rows', min(90, 10 + int(loaded / count * 80)))

        emit('processing', 'Validating staged history and checking source changes...', 92)
        c = stage.c
        local_rows = db.session.execute(select(c.date, func.count(),
            func.count().filter(or_(c.date.is_(None), c.uid.is_(None))),
            func.count() - func.count(func.distinct(c.uid)), func.sum(c.gross_wt), func.sum(c.pieces),
            func.sum(c.checksum_a), func.sum(c.checksum_b)).group_by(c.date)).all()
        local = {row[0]: tuple(value or 0 for value in row[1:]) for row in local_rows}
        after = _source_manifest(conn)
        if loaded != count or before != after or local != before:
            raise RuntimeError('Source changed or staged row/weight/pieces/checksum validation failed; previous snapshot preserved')
        conn.close()
        conn = None
        logger.info('NIP staging validated; publishing %s rows atomically', loaded)
        emit('processing', 'Publishing validated NIP history...', 97)
        # Only now modify live data. Historical dates absent from the source remain.
        source_dates = select(c.date).distinct()
        db.session.query(S).filter(S.date.in_(source_dates)).delete(synchronize_session=False)
        publish_columns = (*SOURCE_COLUMNS, 'synced_at')
        db.session.execute(S.__table__.insert().from_select(publish_columns,
            select(*(c[name] for name in publish_columns))))
        stage.drop(db.session.connection())
        stage = None
        db.session.commit()
        committed = True
        emit('success', f'NIP stock history synced: {loaded:,} rows', 100)
        return {'status': 'success', 'count': loaded}
    except Exception as error:
        logger.exception('NIP stock trend sync failed')
        if committed:
            # Notification failure must not restart a successfully committed import.
            return {'status': 'success', 'count': loaded}
        try:
            db.session.rollback()
        except Exception:
            logger.warning('Rollback failed after NIP sync disconnect; invalidating local connection', exc_info=True)
            try:
                db.session().invalidate()
            except Exception:
                logger.warning('Failed to invalidate NIP sync session', exc_info=True)
        return {'status': 'error', 'message': str(error), 'retryable': not isinstance(error, ValueError)}
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                logger.warning('Failed to close NIP trend source connection', exc_info=True)
        if stage is not None:
            try:
                stage.drop(db.session.connection(), checkfirst=True)
                db.session.commit()
            except Exception:
                db.session.rollback()
                logger.warning('Failed to clean temporary NIP staging table', exc_info=True)
