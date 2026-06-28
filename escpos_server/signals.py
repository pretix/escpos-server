import logging
import signal

shutdown_handlers = []
logger = logging.getLogger(__name__)


def shutdown(signal, frame):
    logger.info(f"Received signal {signal}, shutting down cleanly…")
    for s in shutdown_handlers:
        s()


def setup_signals():
    for sig in (signal.SIGINT,):
        signal.signal(sig, shutdown)
