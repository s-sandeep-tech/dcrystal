"""Reconnectable, bounded reads of the branch/item composition summary.

Checkpoints live for this iterator's lifetime, not across worker restarts.
The source must keep unique, non-null branch/item keys. Changing source rows
between pages/reconnections does not provide point-in-time snapshot isolation.
"""
import time

import psycopg2
from psycopg2.extras import RealDictCursor


class CompositionSourceError(RuntimeError):
    pass


def composition_source_rows(connect, batch_size=30000, progress=None, max_attempts=5):
    conn = None
    last_key = None
    transferred = 0
    validated = False

    def close():
        nonlocal conn
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
            conn = None

    try:
        while True:
            for attempt in range(1, max_attempts + 1):
                try:
                    if conn is None:
                        conn = connect()
                        conn.autocommit = True
                        with conn.cursor() as cur:
                            cur.execute('SET statement_timeout = 0')
                    with conn.cursor(cursor_factory=RealDictCursor) as cur:
                        if not validated:
                            cur.execute('''SELECT branch_id, item_definition_id
                                FROM ext_view.item_wise_tsk_summary_view
                                GROUP BY branch_id, item_definition_id
                                HAVING branch_id IS NULL OR item_definition_id IS NULL
                                    OR COUNT(*) > 1 LIMIT 1''')
                            if cur.fetchone() is not None:
                                raise CompositionSourceError(
                                    'Resumable sync requires unique, non-null branch_id/item_definition_id pairs')
                            validated = True
                        where = '' if last_key is None else ' WHERE (branch_id, item_definition_id) > (%s, %s)'
                        params = (batch_size,) if last_key is None else (*last_key, batch_size)
                        cur.execute('SELECT * FROM ext_view.item_wise_tsk_summary_view' + where
                                    + ' ORDER BY branch_id, item_definition_id LIMIT %s', params)
                        page = cur.fetchall()  # Bounded by LIMIT, never the complete source.
                    break
                except (psycopg2.OperationalError, psycopg2.InterfaceError) as exc:
                    close()
                    if attempt == max_attempts:
                        raise CompositionSourceError(
                            f'Source connection failed {max_attempts} times at checkpoint {last_key}; '
                            f'{transferred:,} rows read. Previous report retained.') from exc
                    if progress:
                        progress(f'Source disconnected after {transferred:,} rows; reconnecting at '
                                 f'branch/item {last_key}, retry {attempt}/{max_attempts}, in 5s.')
                    time.sleep(5)
            if not page:
                return
            # Validate the entire page before handing it to the destination.
            previous = last_key
            for row in page:
                key = (row['branch_id'], row['item_definition_id'])
                if None in key or (previous is not None and key <= previous):
                    raise CompositionSourceError('Source keys are null, duplicated or out of order')
                previous = key
            for row in page:
                yield row
            # Consumer has processed this page before we advance its checkpoint.
            last_key = previous
            transferred += len(page)
    finally:
        close()
