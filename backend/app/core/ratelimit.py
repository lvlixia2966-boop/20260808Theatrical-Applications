"""进程内滑动窗口限流（单实例部署，无需 Redis）。

注意：222 经 docker-proxy 端口转发，容器内看到的源 IP 均为网关地址，
不可作为限流 key；调用方需用业务维度（如登录用户名）作 key。
"""
import threading
import time
from collections import defaultdict, deque

_MAX_KEYS = 4096  # 防止恶意制造海量 key 撑爆内存（局域网场景足够）


class SlidingWindowLimiter:
    """按 key 限制时间窗口内的事件次数；线程安全。"""

    def __init__(self, max_events: int, window_seconds: float):
        self.max_events = max_events
        self.window_seconds = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def _prune(self, key: str, now: float) -> None:
        q = self._hits.get(key)
        if q is None:
            return
        while q and now - q[0] >= self.window_seconds:
            q.popleft()
        if not q:
            del self._hits[key]

    def blocked(self, key: str) -> bool:
        """窗口内事件数已达上限；达到后本窗口剩余时间内继续拒绝。"""
        now = time.monotonic()
        with self._lock:
            self._prune(key, now)
            return len(self._hits[key]) >= self.max_events

    def record(self, key: str) -> None:
        now = time.monotonic()
        with self._lock:
            if len(self._hits) >= _MAX_KEYS:
                self._hits.clear()
            self._hits[key].append(now)

    def reset(self, key: str) -> None:
        with self._lock:
            self._hits.pop(key, None)
