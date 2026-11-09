"""Run stock detail refreshes after a provision refresh, with a separate log."""
import logging
import time
from datetime import datetime

from app.extensions import db
from app.models.core import SyncLog
from app.utils.stock_processed_order_sync import sync_stock_drilldown_details
from app.utils.sync_tasks import emit_sync_update

logger = logging.getLogger(__name__)


def run_stock_sync_followup(task_data):
    if task_data.get('type') != 'provision_stock_status':
        return
    user_id = task_data.get('user_id')
    log = SyncLog(task_name='stock_drilldown_details', status='processing',
                  start_time=datetime.utcnow(), initiated_by=str(user_id) if user_id else None)
    db.session.add(log)
    db.session.commit()
    started = time.monotonic()
    try:
        result = sync_stock_drilldown_details()
    except Exception as error:
        db.session.rollback()
        logger.exception('Chained stock drill-down sync failed')
        result = {'status': 'error', 'message': str(error)}
        emit_sync_update('error', 'Chained stock drill-down sync failed.', 0, 'stock_drilldown_details')
    log.end_time = datetime.utcnow()
    log.duration = time.monotonic() - started
    log.status = 'success' if result and result.get('status') == 'success' else 'error'
    log.details = ({'count': result.get('count')} if log.status == 'success'
                   else {'error': result.get('message') if result else 'Unknown error'})
    db.session.commit()
    return result
