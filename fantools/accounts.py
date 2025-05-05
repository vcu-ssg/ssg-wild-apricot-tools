"""
"""
import json
import click
from fantools.api import get_accounts_details
from fantools.utils import list_accounts_summaries
from loguru import logger

@click.command()
@click.pass_context
@click.option('--account-id', default=None,type=int, help="Account ID to filter by")
@click.option('--as-json', is_flag=True, default=False, help="List all accounts info in JSON format")
def accounts( ctx,account_id,as_json ):
    """Display Wild Apricot account details in pretty JSON format."""

    if account_id:
        logger.debug(f"Account id from CLI: {account_id}")

    try:
        accounts = get_accounts_details()
        logger.trace(f"Accounts: {accounts}")
        if not accounts:
            click.echo("No accounts found.")
            return
    except Exception as e:
        click.echo(f"Error: {e}")
        return

    if not account_id:
        account_id = ctx.obj.get('account_id')
        logger.debug(f"Account ID from context: {account_id}")

    if account_id:
        accounts = [account for account in accounts if str(account['Id']) == str(account_id)]
        logger.trace(f"Filtered accounts: {accounts}")

    if not accounts:
        click.echo(f"No account found with ID: {account_id}")
        return
    
    if as_json:
        click.echo(json.dumps(accounts, indent=2))
    else:
        list_accounts_summaries(accounts)

