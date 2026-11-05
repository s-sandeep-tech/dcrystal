"""Opt-in Redis lease tests, using only unique disposable test keys."""
import os
import threading
import time
import unittest
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor
from app.extensions import redis_client
from app.utils.report_cache_lock import ReportCacheLock


@unittest.skipUnless(os.getenv('REDIS_LOCK_TEST') == '1', 'Requires Redis')
class ReportLockTests(unittest.TestCase):
    def setUp(self):
        self.client = redis_client
        self.prefix = 'test:report-lock:' + uuid4().hex

    def tearDown(self):
        keys = list(self.client.scan_iter(self.prefix + '*'))
        if keys: self.client.delete(*keys)

    def test_concurrent_readers_calculate_once(self):
        key = self.prefix + ':payload'
        barrier = threading.Barrier(8)
        calculations = []
        def request():
            barrier.wait()
            lease = ReportCacheLock(self.client, self.prefix + ':lock')
            try:
                deadline = time.monotonic() + 5
                while time.monotonic() < deadline:
                    value = self.client.get(key)
                    if value: return value
                    if lease.acquire():
                        value = self.client.get(key)
                        if value: return value
                        calculations.append(1)
                        threading.Event().wait(.1)
                        lease.publish(key, 'complete', 3000)
                        return 'complete'
                    threading.Event().wait(.01)
                raise AssertionError('Waiter timed out')
            finally:
                lease.release()
        with ThreadPoolExecutor(max_workers=8) as pool:
            self.assertEqual(list(pool.map(lambda _: request(), range(8))), ['complete'] * 8)
        self.assertEqual(len(calculations), 1)
        self.assertGreater(self.client.ttl(key), 2990)

    def test_release_and_publish_cannot_touch_successors_lock(self):
        key = self.prefix + ':lock'
        lease = ReportCacheLock(self.client, key)
        self.assertTrue(lease.acquire())
        self.client.set(key, 'successor', ex=30)
        try:
            with self.assertRaises(RuntimeError): lease.publish(self.prefix + ':payload', 'stale', 3000)
        finally:
            lease.release()
        self.assertEqual(self.client.get(key), 'successor')
        self.assertIsNone(self.client.get(self.prefix + ':payload'))

    def test_renewal_keeps_slow_calculation_owned(self):
        key = self.prefix + ':lock'
        lease = ReportCacheLock(self.client, key, ttl=1)
        contender = ReportCacheLock(self.client, key)
        self.assertTrue(lease.acquire())
        try:
            threading.Event().wait(1.4)
            self.assertFalse(contender.acquire())
            lease.publish(self.prefix + ':payload', 'complete', 3000)
        finally:
            lease.release()
        self.assertEqual(self.client.get(self.prefix + ':payload'), 'complete')

    def test_distinct_filters_can_acquire_independently(self):
        first = ReportCacheLock(self.client, self.prefix + ':gold')
        second = ReportCacheLock(self.client, self.prefix + ':diamond')
        try:
            self.assertTrue(first.acquire())
            self.assertTrue(second.acquire())
        finally:
            first.release(); second.release()
