import json
import os
import socket
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from uuid import uuid4

import redis
from ..config import settings
from ..utils.logger import logger
from .protocol import TaskStatus


@dataclass
class Delivery:
    message_id: str
    raw: str
    attempts: int


OWNED = """
local p = redis.call('XPENDING', KEYS[1], ARGV[1], ARGV[2], ARGV[2], 1)
if #p == 0 or p[1][2] ~= ARGV[3] then return 0 end
"""


class RedisManager:
    """At-least-once Streams delivery with renewable leases and bounded attempts."""

    def __init__(self):
        self.client = redis.Redis(
            host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=settings.REDIS_DB,
            password=settings.REDIS_PASSWORD, decode_responses=True,
            socket_timeout=15, socket_connect_timeout=10, health_check_interval=30
        )
        self.queue_name = settings.REDIS_QUEUE_NAME
        self.stream = self.queue_name + ':stream'
        self.dead_letter = self.queue_name + ':dead'
        self.group = 'intelligence-workers'
        self.consumer = f'{socket.gethostname()}-{os.getpid()}-{uuid4().hex}'
        self.result_prefix = settings.REDIS_RESULT_PREFIX
        self.event_channel = settings.REDIS_EVENT_CHANNEL
        self.ttl = settings.REDIS_TASK_TTL_SECONDS
        self.lease_ms = settings.REDIS_TASK_LEASE_SECONDS * 1000
        self.max_attempts = settings.REDIS_TASK_MAX_ATTEMPTS
        if self.lease_ms < 30000 or self.max_attempts < 1:
            raise ValueError('Task lease must be >=30 seconds and max attempts >=1')
        self.claim_cursor = '0-0'

    def ping(self):
        try:
            return self.client.ping()
        except redis.RedisError:
            return False

    def ensure_group(self):
        try:
            self.client.xgroup_create(self.stream, self.group, id='0-0', mkstream=True)
        except redis.ResponseError as error:
            if 'BUSYGROUP' not in str(error):
                raise

    def migrate_legacy(self):
        # Add before removing, atomically, so pending list jobs survive deployment.
        return self.client.eval("""
        local n = 0
        for i=1,100 do
            local raw = redis.call('LINDEX', KEYS[1], 0)
            if not raw then break end
            redis.call('XADD', KEYS[2], '*', 'task', raw)
            redis.call('LPOP', KEYS[1])
            n = n + 1
        end
        return n
        """, 2, self.queue_name, self.stream)

    def pop_task(self, timeout=5):
        self.ensure_group()
        self.migrate_legacy()
        recovered = self.client.xautoclaim(
            self.stream, self.group, self.consumer, self.lease_ms,
            start_id=self.claim_cursor, count=1
        )
        self.claim_cursor = recovered[0]
        messages = recovered[1]
        if not messages:
            response = self.client.xreadgroup(
                self.group, self.consumer, {self.stream: '>'}, count=1,
                block=max(1, timeout * 1000)
            )
            messages = response[0][1] if response else []
        if not messages:
            return None
        message_id, fields = messages[0]
        pending = self.client.xpending_range(self.stream, self.group, message_id, message_id, 1)
        return Delivery(message_id, fields.get('task', ''), pending[0]['times_delivered'])

    def push_task(self, task):
        self.client.xadd(self.stream, {'task': task.model_dump_json()})
        return True

    def renew(self, delivery):
        return bool(self.client.eval(OWNED + """
        redis.call('XCLAIM', KEYS[1], ARGV[1], ARGV[3], 0, ARGV[2], 'JUSTID')
        return 1
        """, 1, self.stream, self.group, delivery.message_id, self.consumer))

    @contextmanager
    def heartbeat(self, delivery):
        stop, lost = threading.Event(), threading.Event()

        def renew_loop():
            while not stop.wait(self.lease_ms / 3000):
                try:
                    if not self.renew(delivery):
                        lost.set()
                        break
                except Exception:
                    lost.set()
                    logger.exception('Task lease renewal failed')
                    break

        thread = threading.Thread(target=renew_loop, daemon=True)
        thread.start()

        def check():
            if lost.is_set() or not self.renew(delivery):
                raise RuntimeError('Task lease lost; output transaction must not commit')

        try:
            check()
            yield check
        finally:
            stop.set()
            thread.join()

    def acknowledge(self, delivery, error=None):
        result = self.client.eval(OWNED + """
        if ARGV[4] ~= '' then
            redis.call('XADD', KEYS[2], '*', 'task', ARGV[5],
                       'error', ARGV[4], 'attempts', ARGV[6], 'source_id', ARGV[2])
        end
        redis.call('XACK', KEYS[1], ARGV[1], ARGV[2])
        redis.call('XDEL', KEYS[1], ARGV[2])
        return 1
        """, 2, self.stream, self.dead_letter, self.group, delivery.message_id,
            self.consumer, error or '', delivery.raw, delivery.attempts)
        if not result:
            raise RuntimeError('Cannot acknowledge task owned by another worker')

    def update_task_status(self, task_id, status, progress=None):
        mapping = {'status': status.value}
        if status == TaskStatus.PROCESSING:
            mapping.update(error='', completed_at='', result_json='{}')
        if progress is not None:
            mapping['progress'] = str(progress)
        with self.client.pipeline(transaction=True) as pipe:
            pipe.hset(f'{self.result_prefix}{task_id}', mapping=mapping)
            pipe.expire(f'{self.result_prefix}{task_id}', self.ttl)
            pipe.execute()

    def save_task_result(self, result):
        key = f'{self.result_prefix}{result.task_id}'
        with self.client.pipeline(transaction=True) as pipe:
            pipe.hset(key, mapping={
                'status': result.status.value, 'task_type': result.task_type.value,
                'execution_time_sec': str(result.execution_time_sec),
                'result_json': json.dumps(result.result or {}), 'error': result.error or '',
                'completed_at': result.created_at
            })
            pipe.expire(key, self.ttl)
            pipe.publish(self.event_channel, json.dumps({
                'event': 'task_completed' if result.status == TaskStatus.COMPLETED else
                         'task_retrying' if result.status == TaskStatus.RETRYING else 'task_failed',
                'task_id': result.task_id, 'task_type': result.task_type.value,
                'status': result.status.value
            }))
            pipe.execute()

    def get_task_result(self, task_id):
        raw = self.client.hgetall(f'{self.result_prefix}{task_id}')
        if raw and raw.get('result_json'):
            raw['result'] = json.loads(raw['result_json'])
        return raw or None
