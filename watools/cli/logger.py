import click
from loguru import logger


def click_sink(message):
    record = message.record
    level = record["level"].name
    color = {
        "TRACE": "bright_black",
        "DEBUG": "blue",
        "INFO": "green",
        "SUCCESS": "white",
        "WARNING": "yellow",
        "ERROR": "red",
        "CRITICAL": "bright_red",
    }.get(level, "white")

    # Add source file + line number prefix if enabled
    prefix = ""
    if record["extra"].get("log_source"):
        module = record["module"]
        function = record["function"]
        line = record["line"]
        prefix = f"[{level}|{module}.{function}:{line}] "

    click.secho(prefix + record["message"].rstrip(), fg=color)


def setup_logger(level="INFO"):
    """
    Configure loguru logger with click-based color output.

    Args:
        level (str): Log level string (e.g., "DEBUG").
        log_source (bool): Show [module:line] before log messages.
        show_traceback (bool): Enable backtrace for exception logging.
    """

    show_traceback = level in ("TRACE", "DEBUG")
    log_source = level in ("TRACE", "DEBUG", "INFO")

    logger.remove()

    logger.add(
        click_sink,
        level=level.upper(),
        format="{message}",
        backtrace=show_traceback,
        diagnose=show_traceback,
        filter=lambda record: record.update(extra={"log_source": log_source}) or True
    )
