import hashlib
import json
import logging

from redis import Redis
from redis.exceptions import RedisError
from sqlalchemy import func

from app.extensions import REDIS_HOST, REDIS_PORT, db
from app.models.sales_stock_composition_analysis import SalesStockCompositionAnalysisSnapshot

logger = logging.getLogger(__name__)
redis_client = Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True,
                     socket_connect_timeout=0.5, socket_timeout=0.5)
CACHE_TTL_SECONDS = 3 * 60 * 60


def cached_purchase_plan_data(date, selections, path, sort_by, sort_order, hierarchy_root, build):
    # A successful snapshot replacement stamps all rows with the new sync time.
    synced_at = db.session.query(func.max(SalesStockCompositionAnalysisSnapshot.synced_at)).scalar()
    if synced_at is None:
        return build()

    filters = {name: sorted(set(values)) for name, values in selections.items()}
    params = [date.isoformat() if date else None, filters, path, sort_by, sort_order, hierarchy_root]
    digest = hashlib.sha256(json.dumps(params, sort_keys=True).encode()).hexdigest()
    key = f'purchase-plan:main:v1:{synced_at.isoformat()}:{digest}'
    try:
        cached = redis_client.get(key)
        if cached is not None:
            return json.loads(cached)
    except (RedisError, ValueError):
        logger.debug('Purchase Plan cache read failed; using database', exc_info=True)
        return build()

    data = build()
    try:
        redis_client.setex(key, CACHE_TTL_SECONDS, json.dumps(data))
    except RedisError:
        logger.debug('Purchase Plan cache write failed', exc_info=True)
    return data
