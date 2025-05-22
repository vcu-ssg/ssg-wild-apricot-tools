"""
"""
import json
import click
from loguru import logger

from watools.core.api import get_account
from watools.core.utils import list_account

@click.command()
@click.pass_context
@click.option('--as-json', is_flag=True, default=False, help="List all accounts info in JSON format")
def cmd( ctx,as_json ):
    """ Display Wild Apricot account details in pretty JSON format."""

    try:
        account = get_account()
        logger.trace(f"Accounts: {account}")
        if not account:
            click.echo("No accounts found.")
            return
    except Exception as e:
        click.echo(f"Error: {e}")
        return

    if as_json:
        click.echo(json.dumps(account, indent=2))
    else:
        list_account(account,)

