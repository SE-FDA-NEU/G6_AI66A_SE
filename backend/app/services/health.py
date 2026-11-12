"""Bounded readiness probes with a separate, small MySQL connection pool."""
import asyncio
from functools import lru_cache

from sqlalchemy import create_engine, text

from app.core.config import settings


@lru_cache(maxsize=1)
def health_engine():
    options = dict(settings.engine_options)
    options.update(pool_size=1, max_overflow=0, pool_timeout=1)
    options['connect_args'] = {**options['connect_args'], 'connect_timeout': 2,
                               'read_timeout': 2, 'write_timeout': 2}
    return create_engine(settings.DATABASE_URL, **options)


def query_database():
    with health_engine().connect() as connection:
        return connection.execute(text('SELECT 1')).scalar_one() == 1


class HealthProbe:
    def __init__(self, query=query_database, timeout=2):
        self.query = query
        self.timeout = timeout
        self.pending = None

    async def ready(self):
        # A timed-out thread is still alive until the driver's timeout. Do not
        # queue more threads/connections behind that same probe.
        if self.pending is not None and not self.pending.done():
            return False

        async def check():
            try:
                return bool(await asyncio.to_thread(self.query))
            except Exception:
                return False  # Never expose/log a DB URL or driver exception.

        self.pending = asyncio.create_task(check())
        try:
            return await asyncio.wait_for(asyncio.shield(self.pending), timeout=self.timeout)
        except TimeoutError:
            return False


probe = HealthProbe()


def get_health_probe():
    return probe
