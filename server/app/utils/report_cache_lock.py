"""Owned, renewable Redis lease for a single report/filter calculation."""
import threading
from uuid import uuid4

RENEW = """if redis.call('GET', KEYS[1]) == ARGV[1] then
return redis.call('EXPIRE', KEYS[1], ARGV[2]) else return 0 end"""
RELEASE = """if redis.call('GET', KEYS[1]) == ARGV[1] then
return redis.call('DEL', KEYS[1]) else return 0 end"""
PUBLISH = """if redis.call('GET', KEYS[1]) == ARGV[1] then
redis.call('SET', KEYS[2], ARGV[2], 'EX', ARGV[3])
redis.call('DEL', KEYS[1]) return 1 else return 0 end"""


class ReportCacheLock:
    def __init__(self, client, key, ttl=90):
        self.client, self.key, self.ttl = client, key, ttl
        self.token = uuid4().hex
        self.stop = threading.Event()
        self.lost = threading.Event()
        self.thread = None

    def acquire(self):
        if not self.client.set(self.key, self.token, nx=True, ex=self.ttl):
            return False
        self.thread = threading.Thread(target=self._renew, daemon=True)
        self.thread.start()
        return True

    def _renew(self):
        while not self.stop.wait(self.ttl / 3):
            try:
                if not self.client.eval(RENEW, 1, self.key, self.token, self.ttl):
                    self.lost.set()
                    return
            except Exception:
                self.lost.set()
                return

    def publish(self, key, value, ttl):
        if self.lost.is_set() or not self.client.eval(PUBLISH, 2, self.key, key, self.token, value, ttl):
            raise RuntimeError('Report cache lease was lost')
        self.stop.set()

    def release(self):
        self.stop.set()
        # Never delete a successor's lock if our lease expired or was replaced.
        self.client.eval(RELEASE, 1, self.key, self.token)
