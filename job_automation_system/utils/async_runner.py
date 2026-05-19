"""
Persistent async runner for Celery worker processes.
Reuses a single event loop thread per process so async browser resources can
stay bound to a stable loop across task invocations.
"""

from __future__ import annotations

import asyncio
import atexit
import os
import threading
from concurrent.futures import Future
from typing import Any, Coroutine


class PersistentAsyncRunner:
    def __init__(self) -> None:
        self._pid: int | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._ready = threading.Event()
        self._lock = threading.Lock()

    def _ensure_loop(self) -> asyncio.AbstractEventLoop:
        pid = os.getpid()
        with self._lock:
            if self._pid != pid or self._loop is None or self._thread is None or not self._thread.is_alive():
                self._shutdown_locked()
                self._pid = pid
                self._ready.clear()
                self._thread = threading.Thread(
                    target=self._loop_worker,
                    name="persistent-async-runner",
                    daemon=True,
                )
                self._thread.start()
                self._ready.wait(timeout=10)
                if self._loop is None:
                    raise RuntimeError("Failed to start persistent async event loop")
            return self._loop

    def _loop_worker(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop
        self._ready.set()
        loop.run_forever()

    def run(self, coro: Coroutine[Any, Any, Any]) -> Any:
        loop = self._ensure_loop()
        future: Future[Any] = asyncio.run_coroutine_threadsafe(coro, loop)
        return future.result()

    def shutdown(self) -> None:
        with self._lock:
            self._shutdown_locked()

    def _shutdown_locked(self) -> None:
        loop = self._loop
        thread = self._thread
        self._loop = None
        self._thread = None
        self._pid = None
        if loop is not None:
            loop.call_soon_threadsafe(loop.stop)
        if thread is not None and thread.is_alive():
            thread.join(timeout=5)


async_runner = PersistentAsyncRunner()
atexit.register(async_runner.shutdown)
