import logging
import sys


def configure_logging(*, level: int = logging.INFO) -> None:
    """
    Ensure application loggers (non-uvicorn) show up in the console.

    Uvicorn config doesn't always set the root logger level, so module-level
    logger.info(...) calls can be hidden unless we configure logging.
    """
    # Uvicorn installs its own logging config/handlers; force a basic config so our
    # module loggers (e.g. query_pipeline/generator) reliably show up in console.
    logging.basicConfig(
        level=level,
        stream=sys.stdout,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        force=True,
    )
