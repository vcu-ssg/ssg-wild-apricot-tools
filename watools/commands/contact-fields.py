import click
import json

from watools.core.api import get_contact_fields
from watools.core.utils import list_contact_fields
from loguru import logger


@click.command("contact_fields")
@click.option('--is-system/--no-is-system', default=None, help='Filter by IsSystem flag')
@click.option('--is-builtin/--no-is-builtin', default=None, help='Filter by IsBuiltIn flag')
@click.option('--is-editable/--no-is-editable', default=None, help='Filter by IsEditable flag')
@click.option('--member-only/--no-member-only', default=None, help='Filter by MemberOnly flag')
@click.option('--admin-only/--no-admin-only', default=None, help='Filter by AdminOnly flag')
@click.option('--all','all_values', is_flag=True, default=False, help='Ignore all filters and show all fields')
@click.option('--as-json', is_flag=True, default=False, help='Show config properties as JSON')
@click.pass_context
def cmd(ctx,is_system,is_builtin,is_editable,member_only,admin_only,all_values,as_json):
    """
    Display current configuration properties.
    """
    def match(row, key, flag):
        return flag is None or row.get(key) == flag
    
    def all_none(*args):
        return all(x is None for x in args)

    ctx.ensure_object(dict)
    account_id = ctx.obj.get("account_id")
    if not account_id:
        logger.error("No account ID provided. Use --account-id or configure it.")
        return

    fields = get_contact_fields( account_id )

    if all_values:
        filtered = fields
    elif all_none( is_system, is_builtin, is_editable, member_only,admin_only ):
        filtered = [row for row in fields
                    if match(row,"IsEditable",True)
                    and row.get("Type") not in ["Picture"]
                ]
    else:
        filtered = [row for row in fields 
                    if match(row,"IsSystem",is_system)
                    and match(row,"IsBuiltIn",is_builtin)
                    and match(row,"IsEditable",is_editable)
                    and match(row,"MemberOnly",member_only)
                    and match(row,"AdminOnly",admin_only)
                ]
   
    if as_json:
        click.echo(json.dumps(filtered, indent=2, default=str))
    else:
        list_contact_fields(filtered)
