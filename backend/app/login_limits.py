"""Bounded login budgets shared across names and client addresses."""

import threading
import time
from collections import OrderedDict, deque
from contextlib import contextmanager


class LoginLimiter:
    def __init__(self, capacity=2048):
        self.capacity = max(1, capacity // 2)
        self.ips, self.accounts = OrderedDict(), OrderedDict()
        self.lock = threading.Lock()
        self.slots = threading.BoundedSemaphore(4)

    @property
    def size(self):
        return len(self.ips) + len(self.accounts)

    def check(self, ip, username, at=None):
        at = time.monotonic() if at is None else at
        with self.lock:
            for buckets in (self.ips, self.accounts):
                for key in list(buckets):
                    if buckets[key][-1] <= at - 300:
                        del buckets[key]
            entries = []
            for buckets, key, limit in ((self.ips, ip, 20), (self.accounts, username, 10)):
                recent = buckets.get(key, deque())
                while recent and recent[0] <= at - 300:
                    recent.popleft()
                if len(recent) >= limit:
                    raise ValueError("Too many attempts; wait five minutes.")
                entries.append((buckets, key, recent))
            for buckets, key, recent in entries:
                recent.append(at)
                buckets[key] = recent
                buckets.move_to_end(key)
                while len(buckets) > self.capacity:
                    buckets.popitem(last=False)

    @contextmanager
    def verification(self):
        if not self.slots.acquire(blocking=False):
            raise ValueError("Login is busy; try again shortly.")
        try:
            yield
        finally:
            self.slots.release()
