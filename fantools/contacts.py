

import json
import click
from loguru import logger

from fantools.api import get_contacts
from fantools.utils import list_contacts, list_contact_details


@click.group('contacts',invoke_without_command=True)
@click.option('--account-id', type=int, default=None, help='Use specific account ID')
@click.option('--contact-id', type=int, help='Filter by specific contact ID')
@click.option('--as-json', is_flag=True, default=False, help='List all events info in JSON format')
@click.pass_context
def contacts(ctx, account_id, contact_id, as_json):
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
        contacts = get_contacts( account_id )
        logger.debug( json.dumps( contacts ) )
        if contacts:
            if 0:
                contacts = {"Contacts":contacts}

                logger.trace( json.dumps( contacts, indent=2) )
                
                if member_group_id:
                    contacts = [contact for contact in contacts.get("Contacts",[]) if str(contact.get("Id")) == str(contact_id)]
                    if not contacts:
                        click.echo(f"No contacts with ID: {contact_id}")
                        return
                    contacts = {"Contacts": contacts}

                if as_json:
                    click.echo(json.dumps(contacts, indent=2))
                else:
                    if contact_id:
                        list_contact_details( contact )
                    else:
                        list_contacts( contacts )
        else:
            click.echo("No contacts found.")
            return
