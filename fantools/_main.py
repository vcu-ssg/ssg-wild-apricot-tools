import click
from loguru import logger
from fantools import accounts, members, events, contacts, groups, config


@click.group(invoke_without_command=True)
@click.pass_context
def cli( ctx ):
    """FanTools CLI."""
    if config.config:
        # Add specified keys to the context if they exist in the config
        keys_to_check = ['account_id','log_level']  # List of keys to check
        ctx.obj = {}
        for key in keys_to_check:
            if key in config.config:
                ctx.obj[key] = config.config[key]
            else:
                ctx.obj[key] = None
                logger.debug(f"No '{key}' key found in configuration. Add '{key}=' to the configuration file.")
    else:
        logger.debug("No configuration loaded.")
        ctx.obj = {}

cli.add_command(accounts.accounts)
cli.add_command(members.members)
cli.add_command(events.events)
cli.add_command(contacts.contacts)
cli.add_command(groups.groups)

