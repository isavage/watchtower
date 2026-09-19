"""Dev helper: seed synthetic metric history so the dashboard has data to show.

Usage: .venv/bin/python -m app.seed
"""
from __future__ import annotations

import math
import random
import time

from . import store


def seed(hours: int = 24, interval: int = 20) -> int:
    store.init_db()
    now = time.time()
    start = now - hours * 3600
    rows = []
    t = start
    i = 0
    while t <= now:
        # gentle daily wave + noise, per-core-ish
        wave = (math.sin((t / 86400) * 2 * math.pi) + 1) / 2
        cpu = max(1, min(99, 12 + wave * 45 + random.uniform(-8, 12)))
        cores = 8
        mem_pct = max(20, min(95, 62 + wave * 10 + random.uniform(-4, 6)))
        mem_total = 16 * 1024**3
        rows.append(
            {
                "ts": t,
                "cpu_pct": round(cpu, 1),
                "cpu_count": cores,
                "load1": round(cpu / 100 * cores * random.uniform(0.7, 1.1), 2),
                "load5": round(cpu / 100 * cores * random.uniform(0.7, 1.05), 2),
                "load15": round(cpu / 100 * cores * random.uniform(0.7, 1.0), 2),
                "mem_total": mem_total,
                "mem_used": mem_total * mem_pct / 100,
                "mem_pct": round(mem_pct, 1),
                "swap_total": 2 * 1024**3,
                "swap_used": random.uniform(0, 0.3) * 1024**3 if mem_pct > 80 else 0,
                "disk_total": 100 * 1024**3,
                "disk_used": (48 + (i / 500)) * 1024**3,
                "disk_pct": round(48 + (i / 500), 1),
                "disk_read": random.uniform(0, 40) * 1024**2 if random.random() > 0.6 else random.uniform(0, 3) * 1024**2,
                "disk_write": random.uniform(0, 20) * 1024**2 if random.random() > 0.6 else random.uniform(0, 2) * 1024**2,
                "net_recv": random.uniform(0, 8) * 1024**2 if random.random() > 0.5 else random.uniform(10**4, 5 * 10**5),
                "net_sent": random.uniform(0, 3) * 1024**2 if random.random() > 0.5 else random.uniform(10**4, 2 * 10**5),
                "uptime": t - (now - 6 * 86400),
                "proc_count": int(300 + random.uniform(-20, 60)),
            }
        )
        t += interval
        i += 1
    store.insert_metrics(rows)
    return len(rows)


if __name__ == "__main__":
    n = seed()
    print(f"seeded {n} rows")
