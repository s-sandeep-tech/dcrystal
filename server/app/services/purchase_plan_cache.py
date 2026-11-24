"""Snapshot-versioned caches shared by the purchase-plan report endpoints."""
import hashlib
import json
import logging
import time
import uuid
from contextvars import ContextVar
from functools import wraps

from flask import has_request_context, request
from redis import Redis
from redis.exceptions import RedisError
from sqlalchemy import event, func
from sqlalchemy.engine import Engine

from app.extensions import REDIS_HOST, REDIS_PORT, db
from app.models.sales_stock_composition_analysis import SalesStockCompositionAnalysisSnapshot

logger = logging.getLogger(__name__)
redis_client = Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True,
                     socket_connect_timeout=0.5, socket_timeout=0.5)
CACHE_TTL_SECONDS = 3 * 60 * 60
LOCK_TTL_SECONDS = 120
LOCK_WAIT_SECONDS = 2
_metrics = ContextVar('purchase_plan_metrics', default=None)


@event.listens_for(Engine, 'before_cursor_execute')
def _count_report_queries(conn, cursor, statement, parameters, context, executemany):
    metrics = _metrics.get()
    if metrics is not None:
        metrics['sql_queries'] += 1


def measure_purchase_plan(operation):
    """Log endpoint time, SQL count and cache activity without changing responses."""
    def decorate(fn):
        @wraps(fn)
        def measured(*args, **kwargs):
            metrics = {'sql_queries': 0, 'hits': 0, 'misses': 0, 'fallbacks': 0}
            token = _metrics.set(metrics)
            started = time.perf_counter()
            try:
                return fn(*args, **kwargs)
            finally:
                _metrics.reset(token)
                logger.info('Purchase Plan operation=%s elapsed_ms=%.1f sql_queries=%s cache_hits=%s cache_misses=%s cache_fallbacks=%s',
                            operation, (time.perf_counter() - started) * 1000,
                            metrics['sql_queries'], metrics['hits'], metrics['misses'], metrics['fallbacks'])
        return measured
    return decorate


def _record(name):
    metrics = _metrics.get()
    if metrics is not None:
        metrics[name] += 1


def _snapshot_version():
    # Reuse only within this request, never across database refreshes/requests.
    if has_request_context() and 'purchase_plan.snapshot_version' in request.environ:
        return request.environ['purchase_plan.snapshot_version']
    synced_at = db.session.query(func.max(SalesStockCompositionAnalysisSnapshot.synced_at)).scalar()
    version = synced_at.isoformat() if synced_at else None
    if has_request_context():
        request.environ['purchase_plan.snapshot_version'] = version
    return version


def normalized_selections(selections):
    return {name: sorted(set(values)) for name, values in selections.items() if values}


def cached_purchase_plan_value(namespace, params, build):
    if has_request_context() and request.environ.get('purchase_plan.cache_unavailable'):
        _record('fallbacks')
        return build()
    version = _snapshot_version()
    if version is None:
        return build()
    digest = hashlib.sha256(json.dumps(params, sort_keys=True).encode()).hexdigest()
    key = f'purchase-plan:{namespace}:v5:{version}:{digest}'
    lock_key = key + ':lock'
    token = uuid.uuid4().hex
    owns_lock = False
    try:
        try:
            cached = redis_client.get(key)
            if cached is not None:
                result = json.loads(cached)
                _record('hits')
                return result
            _record('misses')
            owns_lock = bool(redis_client.set(lock_key, token, nx=True, ex=LOCK_TTL_SECONDS))
            if not owns_lock:
                deadline = time.monotonic() + LOCK_WAIT_SECONDS
                while time.monotonic() < deadline:
                    time.sleep(0.05)
                    cached = redis_client.get(key)
                    if cached is not None:
                        result = json.loads(cached)
                        _record('hits')
                        return result
                # Bound the wait if another worker has stalled. Do not publish
                # an unlocked rebuild over a newer worker's value.
                _record('fallbacks')
                return build()
        except (RedisError, ValueError, TypeError) as exc:
            if isinstance(exc, RedisError) and has_request_context():
                request.environ['purchase_plan.cache_unavailable'] = True
            _record('fallbacks')
            logger.debug('Purchase Plan cache unavailable; using database', exc_info=True)
            return build()

        data = build()
        try:
            redis_client.setex(key, CACHE_TTL_SECONDS, json.dumps(data))
        except (RedisError, TypeError, ValueError):
            logger.debug('Purchase Plan cache write failed', exc_info=True)
        return data
    finally:
        if owns_lock:
            try:
                redis_client.eval("if redis.call('get', KEYS[1]) == ARGV[1] then return redis.call('del', KEYS[1]) else return 0 end", 1, lock_key, token)
            except RedisError:
                logger.debug('Purchase Plan cache lock release failed', exc_info=True)


def cached_purchase_plan_data(date, selections, path, sort_by, sort_order, hierarchy_root, build):
    params = [date.isoformat() if date else None, normalized_selections(selections),
              path, sort_by, sort_order, hierarchy_root]
    return cached_purchase_plan_value('main', params, build)
