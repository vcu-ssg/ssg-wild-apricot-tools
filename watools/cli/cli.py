
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())


import sys
import json
import importlib
from pathlib import Path

import click
from loguru import logger
from tomlkit.exceptions import ParseError

from watools.core.config import config
from watools.cli.logger import setup_logger
from watools.core.paths import get_project_root

COMMAND_FOLDER = get_project_root() / "watools" / "commands"

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
        except Exception as e:
            logger.error(f"Failed to import watools.commands.{name}")
            logger.exception(e)
            sys.exit(1)

        if not hasattr(mod, "cmd"):
            logger.error(f"Command module '{name}' must define a `cmd` object.")
            sys.exit(1)

        return mod.cmd


@click.command(cls=WatoolsCLI, invoke_without_command=True)
@click.option(
    "--log-level",
    default=None,
    type=click.Choice(["TRACE", "DEBUG", "INFO", "SUCCESS", "WARNING", "ERROR", "CRITICAL"], case_sensitive=False),
    help="Override log level (also enables traceback for DEBUG or TRACE)",
)
@click.option('--account-id', default=None,type=int, help="Account ID to filter by")
@click.pass_context
def cli(ctx, log_level, account_id ):
    """watools: CLI for managing Wild Apricot integrations."""

    def perform_setup():
        config.load()
        if not log_level and config.log_level in [
            "TRACE", "DEBUG", "INFO", "SUCCESS", "WARNING", "ERROR", "CRITICAL"
        ]:
            setup_logger(level=config.log_level)
        config.validate()

    debug_exceptions = False

    level = (log_level or "DEBUG").upper()
    setup_logger(level=level)

    ctx.ensure_object(dict)
    ctx.obj["debug_exceptions"] = debug_exceptions

    if debug_exceptions:
        logger.warning("Debug exception mode enabled: exceptions will not be caught.")
        perform_setup()
    else:
        try:
            perform_setup()
        except FileNotFoundError as e:
            logger.error(f"Config file not found: {e}")
            ctx.exit(1)
        except ParseError as e:
            logger.error(f"Failed to parse config TOML: {e}")
            ctx.exit(1)
        except (KeyError, ValueError, TypeError) as e:
            logger.error(f"Error: {e}")
            ctx.exit(1)
        except Exception:
            logger.exception("[FATAL] Unhandled exception")
            ctx.exit(1)

    if config.is_loaded:
        keys_to_check = ['account_id', 'log_level']
        for key in keys_to_check:
            if key in config:
                match key:
                    case "default_account_id":
                        ctx.obj["account_id"] = config[key]
                    case _:
                        ctx.obj[key] = config[key]
            else:
                ctx.obj[key] = None
                logger.debug(
                    f"No '{key}' key found in configuration. Add '{key}=' to the configuration file."
                )

        if account_id:
            ctx.obj["account_id"] = str(account_id)
            logger.debug(f"Using account_id from CLI: {account_id}")

        logger.debug(f"config._raw_config: \n{json.dumps(config._raw_config, indent=2)}")
        logger.debug(f"ctx.obj\n{json.dumps(ctx.obj, indent=2)}")

    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())
