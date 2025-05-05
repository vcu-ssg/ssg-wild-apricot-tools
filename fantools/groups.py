
import click
import json

from datetime import datetime
from loguru import logger

from fantools.api import get_groups_details
from fantools.utils import list_events_details, list_event_details


@click.group(invoke_without_command=True)
@click.option('--account-id', type=int, default=None, help='Use specific account ID')
@click.option('--group-id', type=int, help='Filter by specific group ID')
@click.option('--as-json', is_flag=True, default=False, help='List all events info in JSON format')
@click.pass_context
def groups(ctx, account_id, group_id, as_json):
    """Manage Wild Apricot groups."""

    ctx.ensure_object(dict)
    logger.debug(f"Invoked subcommand: {ctx.invoked_subcommand}" )

    logger.debug(f"Account ID from CLI: {account_id}")
    if not account_id:
        account_id = ctx.obj.get('account_id')
        logger.debug(f"Account ID from context: {account_id}")
    else:
        ctx.obj["account_id"] = account_id

    if not account_id:
        logger.error("No account ID provided. Use --account-id to specify an account.")
        return

    logger.debug(f"Group ID from CLI: {group_id}")
    if not group_id:
        group_id = ctx.obj.get('group_id')
        logger.debug(f"Group ID from context: {group_id}")
    else:
        ctx.obj["group_id"] = group_id

    if not ctx.invoked_subcommand:
        groups = get_groups_details( account_id )
        if groups:

            click.echo( json.dumps( groups, indent=2) )
            
            if 0:
                if group_id:
                    groups = [group for groups in groups.get("Events", []) if groups.get("Id") == event_id]
                    if not events:
                        click.echo(f"No event found with ID: {event_id}")
                        return
                    events = {"Events": events}

                if as_json:
                    click.echo(json.dumps(groups, indent=2))
                else:
                    if group_id:
                        list_group_details( groups )
                    else:
                        list_groups_details( groups )
        else:
            click.echo("No groups found.")
            return
    

