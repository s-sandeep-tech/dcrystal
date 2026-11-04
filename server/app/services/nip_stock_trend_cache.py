"""Redis cache for unscoped NIP report reads."""
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
PREFIX = 'nip-stock-trend:v1'
TTL_SECONDS = 1800


def snapshot_version():
    row = db.session.execute(
        select(S.date, S.synced_at, S.id).order_by(S.id.desc()).limit(1)
    ).first()
    return f'{row.date.isoformat()}:{row.synced_at.isoformat()}:{row.id}' if row else 'empty'


def cached_payload(kind, args, build):
    digest = hashlib.sha256(json.dumps(sorted(args.lists())).encode()).hexdigest()
    key = f'{PREFIX}:{snapshot_version()}:{kind}:{digest}'
    try:
        cached = redis_client.get(key)
        if cached is not None:
            return json.loads(cached)
    except (RedisError, ValueError):
        logger.debug('NIP cache read failed; using database', exc_info=True)
        return build()

    payload = build()
    try:
        redis_client.setex(key, TTL_SECONDS, json.dumps(payload))
    except RedisError:
        logger.debug('NIP cache write failed', exc_info=True)
    return payload


def clear_snapshot_cache(version):
    try:
        for key in redis_client.scan_iter(match=f'{PREFIX}:{version}:*'):
            redis_client.unlink(key)
    except RedisError:
        logger.warning('Unable to clean up previous NIP cache; entries will expire', exc_info=True)
