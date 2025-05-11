"""
"""
import json
import click
from loguru import logger

from watools.core.api import get_accounts
from watools.core.utils import list_accounts
from watools.cli.config import config

@click.command()
@click.pass_context
@click.option('--account-id', default=None,type=int, help="Account ID to filter by")
@click.option('--as-json', is_flag=True, default=False, help="List all accounts info in JSON format")
def cmd( ctx,account_id,as_json ):
    """Display Wild Apricot account details in pretty JSON format."""

    try:
        accounts = get_accounts()
        logger.trace(f"Accounts: {accounts}")
        if not accounts:
            click.echo("No accounts found.")
            return
    except Exception as e:
        click.echo(f"Error: {e}")
        return

    if as_json:
        click.echo(json.dumps(accounts, indent=2))
    else:
        list_accounts(accounts)

