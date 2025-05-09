import click
import json

from watools.config import config  # assumes config singleton is in watools/config.py
from loguru import logger


@click.command("config")
@click.option('--as-json', is_flag=True, default=False, help='Show config properties as JSON')
def cmd(as_json):
    """
    Display current configuration properties.
    """
    try:
        config.load()
    except Exception as e:
        logger.error(f"Failed to load configuration: {e}")
        click.echo(f"Error: {e}")
        return

    props = config.list_properties()

    if as_json:
        click.echo(json.dumps(props, indent=2, default=str))
    else:
        click.echo("Configuration Properties:")
        for k, v in props.items():
            click.echo(f"{k}: {v}")
