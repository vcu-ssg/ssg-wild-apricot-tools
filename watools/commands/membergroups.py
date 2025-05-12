
import click
import json

from datetime import datetime
from loguru import logger

from watools.core.api import get_membergroups
from watools.core.utils import list_groups, list_group_details


@click.group('member-groups',invoke_without_command=True)
@click.option('--member-group-id', type=int, help='Filter by specific group ID')
@click.option('--as-json', is_flag=True, default=False, help='List all events info in JSON format')
@click.pass_context
def cmd(ctx, member_group_id, as_json):
    """Manage Wild Apricot groups."""

    ctx.ensure_object(dict)
    logger.debug(f"Invoked subcommand: {ctx.invoked_subcommand}" )

    account_id = ctx.obj.get('account_id')
    if not account_id:
        logger.error("No account ID provided. Use --account-id to specify an account.")
        return

    if not member_group_id:
        group_id = ctx.obj.get('membeg_group_id')
        logger.debug(f"Group ID from context: {member_group_id}")
    else:
        ctx.obj["member_group_id"] = member_group_id
        logger.debug(f"Member group ID from CLI: {member_group_id}")

    if not ctx.invoked_subcommand:
        groups = get_membergroups( account_id )
        if groups:

            groups = {"MemberGroups":groups}

            logger.trace( json.dumps( groups, indent=2) )
            
            if member_group_id:
                groups = [group for group in groups.get("MemberGroups",[]) if str(group.get("Id")) == str(member_group_id)]
                if not groups:
                    click.echo(f"No event found with ID: {member_group_id}")
                    return
                groups = {"MemberGroups": groups}

            if as_json:
                click.echo(json.dumps(groups, indent=2))
            else:
                if member_group_id:
                    list_group_details( groups )
                else:
                    list_groups( groups )
        else:
            click.echo("No groups found.")
            return
    

