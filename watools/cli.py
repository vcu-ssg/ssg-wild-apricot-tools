import sys
import json
import importlib
from pathlib import Path

import click
from loguru import logger
from tomlkit.exceptions import ParseError

from watools.config import config
from watools.logger import setup_logger


COMMAND_FOLDER = Path(__file__).parent / "commands"


class WatoolsCLI(click.MultiCommand):
    def list_commands(self, ctx):
        return sorted(
            f.stem
            for f in COMMAND_FOLDER.glob("*.py")
            if f.name not in ("__init__.py",) and not f.name.startswith("_")
        )

    def get_command(self, ctx, name):
        try:
            mod = importlib.import_module(f"watools.commands.{name}")
        except ImportError as e:
            logger.error(f"Cannot import command '{name}': {e}")
            sys.exit(1)
        if not hasattr(mod, "cmd"):
            logger.error(f"Command module '{name}' must define a `cmd` object.")
            sys.exit(1)
        return mod.cmd


@click.command(cls=WatoolsCLI, invoke_without_command=True)
@click.option(
    "--log-level",
    default=None,
    type=click.Choice(["TRACE", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], case_sensitive=False),
    help="Override log level (also enables traceback for DEBUG or TRACE)",
)
@click.pass_context
def cli(ctx, log_level):
    """watools: CLI for managing Wild Apricot integrations."""

    level = (log_level or "WARNING").upper()
    setup_logger(level=level)

    try:
        config.load()
        if not log_level:
            if config.log_level in ["TRACE", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
                setup_logger(level=config.log_level)
        config.validate()

    except FileNotFoundError as e:
        logger.error(f"Config file not found: {e}")
        ctx.exit(1)
    except ParseError as e:
        logger.error(f"Failed to parse config TOML: {e}")
        ctx.exit(1)
    except (KeyError, ValueError, TypeError) as e:
        logger.error(f"Error: {e}")  # logs full traceback if TRACE/DEBUG
        ctx.exit(1)
    except Exception:
        logger.exception("[FATAL] Unhandled exception")
        ctx.exit(1)

    if config.is_loaded:
        keys_to_check = ['default_account_id', 'log_level']
        ctx.obj = {}
        for key in keys_to_check:
            if key in config:
                match key:
                    case "default_account_id":
                        ctx.obj["account_id"] = config[key]
                    case _:
                        ctx.obj[key] = config[key]
            else:
                ctx.obj[key] = None
                logger.debug(f"No '{key}' key found in configuration. Add '{key}=' to the configuration file.")

        logger.debug( json.dumps( config._raw_config ))

    # Step 5: Fallback help if no subcommand
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())
