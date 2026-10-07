import asyncio
import logging
import os

from .runner import worker


async def supervise(app, worker_fn=None, retry_delays=(1, 2, 4), fatal=None):
    """Recover the worker; persistent failure must reach the container restart policy."""
    worker_fn = worker_fn or worker
    fatal = fatal or os._exit
    for attempt in range(len(retry_delays) + 1):
        app.state.worker_state = "starting" if attempt == 0 else "recovering"
        try:
            await worker_fn(app)
            raise RuntimeError("Worker exited unexpectedly")
        except asyncio.CancelledError:
            raise
        except Exception as error:
            logging.getLogger(__name__).error("Worker failure: %s", type(error).__name__)
            app.state.worker_state = "recovering"
            if attempt < len(retry_delays):
                await asyncio.sleep(retry_delays[attempt])
    app.state.worker_state = "failed"
    fatal(1)
