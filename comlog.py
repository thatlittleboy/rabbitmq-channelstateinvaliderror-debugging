from datetime import timedelta
import sys

from loguru import logger


_LOG_FMT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss.SSS:Z}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
    "<level>{message}</level>"
)

# here, I'm reconfiguring the default handler (stderr) to use a different format.
logger.remove()
h_stderr = logger.add(
    sys.stderr,
    level="INFO",
    format=_LOG_FMT,
    backtrace=False,
)

# add another log handler
h_logfile = logger.add(
    f"logs/rmq.log",
    level="DEBUG",
    format=_LOG_FMT,
    backtrace=True,  # print traceback into log
    rotation=timedelta(days=1),
    retention=3,
    compression=None,
)
