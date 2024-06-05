import logging
import sys

from loguru import logger


class InterceptHandler(logging.Handler):
    """
    Default handler from examples in loguru documentaion.
    See https://loguru.readthedocs.io/en/stable/overview.html#entirely-compatible-with-standard-logging
    """

    def emit(self, record: logging.LogRecord):
        """Intercept standard logging records."""
        # Get corresponding Loguru level if it exists
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find caller from where originated the logged message
        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:
            if frame.f_back:
                frame = frame.f_back
                depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


def init_logging():
    """
    Replaces logging handlers with a handler for using the custom handler.
    """
    # disable handlers for uvicorn specific loggers
    for uvicorn_logger in (
        logging.getLogger(name) for name in logging.root.manager.loggerDict if name.startswith("uvicorn.")
    ):
        uvicorn_logger.handlers = []

    # change handler for default uvicorn logger
    intercept_handler = InterceptHandler()
    logging.getLogger("uvicorn").handlers = [intercept_handler]

    # set logs output, level and format
    logger.configure(handlers=[{"sink": sys.stdout, "level": logging.INFO}])

    # fast_api_app.add_middleware(LoggingMiddleware)
