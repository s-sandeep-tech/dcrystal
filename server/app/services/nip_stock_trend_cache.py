"""Redis caching for live NIP requests and rollback snapshot maintenance."""
import hashlib
import json
import logging

from redis import Redis
from redis.exceptions import RedisError
from sqlalchemy import select

from app.extensions import REDIS_HOST, REDIS_PORT, db
from app.models.nip_stock_trend import NIPStockTrendSnapshot as S

logger = logging.getLogger(__name__)
redis_client = Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True,
                     socket_connect_timeout=0.5, socket_timeout=0.5)
PREFIX = 'nip-stock-trend:v2'
LIVE_PREFIX = 'nip-stock-trend:live:v1'
LIVE_TTL_SECONDS = 8 * 60 * 60


def snapshot_version():
    row = db.session.execute(
        select(S.date, S.synced_at, S.id).order_by(S.id.desc()).limit(1)
    ).first()
    return f'{row.date.isoformat()}:{row.synced_at.isoformat()}:{row.id}' if row else 'empty'


def cached_live_payload(kind, branches, params, build, *, refresh=False):
    digest = hashlib.sha256(json.dumps((branches, params)).encode()).hexdigest()
    key = f'{LIVE_PREFIX}:{kind}:{digest}'
    if not refresh:
        try:
            cached = redis_client.get(key)
            if cached is not None:
                payload = json.loads(cached)
                # Give previously non-expiring entries an eight-hour expiry.
                # NX leaves existing TTLs unchanged: reads do not extend expiry.
                try:
                    redis_client.expire(key, LIVE_TTL_SECONDS, nx=True)
                except RedisError:
                    logger.debug('Unable to set NIP cache expiry', exc_info=True)
                return payload
        except (RedisError, ValueError):
            logger.debug('NIP live cache read failed; querying the view', exc_info=True)
            return build()

    payload = build()
    try:
        # A miss that started before Refresh must not overwrite its result.
        # Refresh replaces the value and starts a new eight-hour cache window.
        redis_client.set(key, json.dumps(payload), ex=LIVE_TTL_SECONDS, nx=not refresh)
    except RedisError:
        logger.debug('NIP cache write failed', exc_info=True)
    return payload


def clear_snapshot_cache(version):
    try:
        for key in redis_client.scan_iter(match=f'{PREFIX}:{version}:*'):
            redis_client.unlink(key)
    except RedisError:
        logger.warning('Unable to clean up previous NIP cache; entries will expire', exc_info=True)
