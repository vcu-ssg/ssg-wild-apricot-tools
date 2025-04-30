import click
from fantools import account, members, events, contacts

@click.group()
def cli():
    """FanTools CLI."""
    pass

cli.add_command(account.account)
cli.add_command(members.members)
cli.add_command(events.events)
cli.add_command(contacts.contacts)
