"""Credential-free fetch audit, committed independently of forecast failures."""
import json
from contextvars import ContextVar
from datetime import datetime, timezone
from ..utils.logger import logger

fetch_scope = ContextVar('sales_fetch_scope', default={})


def audit(event, **fields):
    record = {**fetch_scope.get(), 'event': event, **fields}
    logger.info('external_fetch %s', json.dumps(record, default=str))
    if not record.get('task_id'):
        return
    try:
        from ..db.connection import SessionLocal
        from ..db.models import SalesExternalFetchLog
        with SessionLocal.begin() as session:
            session.add(SalesExternalFetchLog(task_id=record['task_id'],
                created_at=datetime.now(timezone.utc), event_json=record))
    except Exception as error:
        logger.warning('external_fetch audit persistence failed (%s)', type(error).__name__)
