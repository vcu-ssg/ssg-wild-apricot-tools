

import json
import click
from loguru import logger

from watools.core.api import get_contacts
from watools.core.utils import list_contacts, list_contact_details, summarize_contact_fields, summarize_membership_levels, \
    summarize_member_groups, summarize_levels_by_status, summarize_groups_by_status, member_legend, \
    default_contacts_csv_filename, write_contacts_to_csv


@click.group('contacts',invoke_without_command=True)
@click.option('--contact-id', type=int, help='Filter by specific contact ID')
@click.option('--as-json', is_flag=True, default=False, help='List all contact info in JSON format')
@click.option('--reload', is_flag=True, default=False, help='Reload contact cache')
@click.option(
    "--to-csv",
    required=False,
    default=None,
    help="Write contacts to CSV file. Optional filename. If not provided, uses contacts-YYYY-MM-DD.csv",
    is_flag=False,
    flag_value="",  # Triggered when used as --to-csv without value
)


@click.pass_context
def cmd(ctx, contact_id, as_json, reload, to_csv):
    """Manage Wild Apricot contacts"""

    ctx.ensure_object(dict)
    logger.debug(f"Invoked subcommand: {ctx.invoked_subcommand}" )

    account_id = ctx.obj.get('account_id')
    if not account_id:
        logger.error("No account ID provided. Use --account-id or specify in config.toml file.")
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

            if to_csv is None:
                summarize_levels_by_status( contacts )
                summarize_groups_by_status( contacts )
                #summarize_membership_levels( contacts )
                #summarize_member_groups( contacts )
                member_legend()
            else:
                filename = to_csv or default_contacts_csv_filename()
                click.echo(f"Exporting contacts to: {filename}")
                # Placeholder: write_contacts_to_csv(filename)

                write_contacts_to_csv( contacts, filename )

        else:
            click.echo("No contacts found.")
            return
