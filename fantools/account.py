"""
"""
import json
import click
from fantools.api import get_account_details

@click.command()
def account():
    """Display Wild Apricot account details in pretty JSON format."""
    try:
        accounts = get_account_details()
        click.echo(json.dumps(accounts, indent=2))

    except Exception as e:
        click.echo(f"Error: {e}")