"""Async sampling loop: periodically collects metrics and persists them."""
from __future__ import annotations

import asyncio
import logging
import time

from .collector import Collector
from .config import config
from . import store

log = logging.getLogger("watchtower.sampler")

# Keep raw samples for this long; older rows are pruned.
RETENTION_SECONDS = 7 * 24 * 3600


async def run_sampler(stop: asyncio.Event) -> None:
    collector = Collector()
    batch: list[dict] = []
    last_flush = 0.0
    last_prune = 0.0

    while not stop.is_set():
        try:
            row = collector.sample()
            if row:
                batch.append(row)
            now = time.time()
            # Flush every ~5s to keep SQLite writes cheap.
            if batch and now - last_flush >= 5:
                store.insert_metrics(batch)
                batch.clear()
                last_flush = now
            if now - last_prune >= 3600:
                removed = store.prune(now - RETENTION_SECONDS)
                if removed:
                    log.info("pruned %d old metric rows", removed)
                last_prune = now
        except Exception:
            log.exception("sampling error")
        try:
            await asyncio.wait_for(stop.wait(), timeout=config.sample_interval)
        except asyncio.TimeoutError:
            pass

    if batch:
        store.insert_metrics(batch)
