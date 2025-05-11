

import json
import click
from loguru import logger

from watools.core.api import get_contacts
from watools.core.utils import list_contacts, list_contact_details, summarize_contact_fields, summarize_membership_levels, \
    summarize_member_groups, summarize_levels_by_status, summarize_groups_by_status, member_legend


@click.group('contacts',invoke_without_command=True)
@click.option('--account-id', type=int, default=None, help='Use specific account ID')
@click.option('--contact-id', type=int, help='Filter by specific contact ID')
@click.option('--as-json', is_flag=True, default=False, help='List all events info in JSON format')
@click.option('--reload', is_flag=True, default=False, help='Reload contact cache')
@click.pass_context
def cmd(ctx, account_id, contact_id, as_json, reload):
    """Manage Wild Apricot contacts"""

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

    if not contact_id:
        contact_id = ctx.obj.get('contact_id')
        logger.debug(f"Contact ID from context: {contact_id}")
    else:
        ctx.obj["contact_id"] = contact_id
        logger.debug(f"Contact ID from CLI: {contact_id}")

    if not ctx.invoked_subcommand:
        contacts = get_contacts( account_id, reload=reload )
        logger.trace( json.dumps( contacts[:5] ) )
        if contacts:

            summarize_levels_by_status( contacts )
            summarize_groups_by_status( contacts )
            #summarize_membership_levels( contacts )
            #summarize_member_groups( contacts )
            member_legend()
            
        else:
            click.echo("No contacts found.")
            return
