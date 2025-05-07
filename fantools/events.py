
import click
import json

from datetime import datetime
from loguru import logger

from collections import defaultdict

from fantools.api import get_events, get_event_details, get_event_registrants, \
    get_default_membership_level_ids, get_default_membergroup_ids, \
    get_contacts, register_contacts_to_event

from fantools.utils import list_events, list_event_details


@click.group(invoke_without_command=True)
@click.option('--account-id', type=int, default=None, help='Use specific account ID')
@click.option('--event-id', type=int, help='Filter by specific event ID')
@click.option('--as-json', is_flag=True, default=False, help='List all events info in JSON format')
@click.pass_context
def events(ctx, account_id, event_id, as_json):
    """Manage Wild Apricot events."""

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

    logger.debug(f"Event ID from CLI: {event_id}")
    if not event_id:
        event_id = ctx.obj.get('event_id')
        logger.debug(f"Event ID from context: {event_id}")
    else:
        ctx.obj["event_id"] = event_id

    if not ctx.invoked_subcommand:
        events = get_events( account_id )
        if events:
            click.echo("")
            if not event_id:
                if as_json:
                    click.echo(json.dumps(events, indent=2))
                else:
                    list_events( events )
            else:
                event = [event for event in events.get("Events", []) if str(event.get("Id")) == str(event_id)]
                if not event:
                    click.echo(f"No event found with ID: {event_id}")
                    return
                
                event = event[0]
                event = get_event_details( account_id, event.get("Id",None) )
                if event:
                    if as_json:
                        click.echo(json.dumps(event, indent=2))
                    else:
                        list_event_details( event )
                        click.echo("")
                        click.echo( ctx.get_help() )
                else:
                    click.echo(f"Error loading details for event ID: {event_id}")
        else:
            click.echo("No events found.")
            click.echo("")
            click.echo( ctx.get_help() )
            return
    

@events.command()
@click.option('--account-id', type=int, required=False, default=None, help='Account ID to fetch registrants for')
@click.option('--event-id', type=int, required=False, default=None, help='Event ID to fetch registrants for')
@click.option('--as-json', is_flag=True, default=False, help='Output registrants in JSON format')
@click.option('--confirm', is_flag=True, default=False, help='Confirm action before proceeding')
@click.pass_context
def sync_registrants(ctx, account_id, event_id, as_json, confirm):
    """List registrants for a specific event."""

    logger.debug(f"Account ID from CLI: {account_id}")
    if not account_id:
        account_id = ctx.obj.get('account_id')
        logger.debug(f"Account ID from context: {account_id}")

    if not account_id:
        logger.error("No account ID provided. Use --account-id to specify an account.")
        return

    logger.debug(f"Event ID from CLI: {event_id}")
    if not event_id:
        event_id = ctx.obj.get('event_id')
        logger.debug(f"Event ID from context: {event_id}")

    if not event_id:
        logger.error("No event_id provided. Use --event-id to specify an event.")
        return

    try:
        # Fetch event details (dict), look for AccessControl
        event = get_event_details( account_id, event_id )
        if not event:
            click.echo(f"No event found with ID: {event_id}")
            return
        logger.debug(f"Processing event: {event["Name"]}")

        # Fetch event registrants (list of dict)
        registrants = get_event_registrants( event_id )
        if not registrants:
            click.echo(f"No registrants found for event ID {event_id}.")
        logger.debug( f"Registrants: {len(registrants)}" )

        # Fetch contacts/members
        contacts = get_contacts( account_id )
        if not contacts:
            click.echo(f"No contacts found for account ID {account_id}.")
            return
        logger.debug( f"Contacts: {len(contacts)}" )

        # Fetch membership levels
        default_membership_level_ids = get_default_membership_level_ids( account_id )
        if not default_membership_level_ids:
            click.echo(f"No membership levels found for account ID {account_id}.")
            return
        logger.debug( f"Membership level ids: {default_membership_level_ids}" )

        # Fetch member groups
        default_membergroup_ids = get_default_membergroup_ids( account_id )
        if not default_membergroup_ids:
            click.echo(f"No member groups found for account ID {account_id}.")
            return
        logger.debug( f"Member group ids: {default_membergroup_ids}" )

        # Access control: by membership level and member group
        access_control = event.get("Details",{}).get("AccessControl")
        if not access_control:
            click.echo(f"No access control found for event ID {event_id}.")
            return 
        logger.debug(f"Access control: {json.dumps( access_control,indent=2)}")

        # Potential registrants: by member level and member group
        membership_levels_ids = default_membership_level_ids
        if not access_control["AvailableForAnyLevel"]:
            membership_levels_ids = [item["Id"] for item in access_control.get("AvailableForLevels",[])]
        logger.debug(f"Membership levels ids: {membership_levels_ids}")

        membergroup_ids = default_membergroup_ids
        if not access_control["AvailableForAnyGroup"]:
            membergroup_ids = [item["Id"] for item in access_control.get("AvailableForGroups",[])]
        logger.debug(f"Member group ids: {membergroup_ids}")
    
        members_ids_by_level = [ contact["Id"] for contact in contacts if contact["MembershipLevelId"] in membership_levels_ids ]
        logger.debug(f"Count of members ids by level: {len(members_ids_by_level)}")

        #logger.debug(f"{json.dumps([contact for contact in contacts if "Leonard" in contact["DisplayName"]],indent=2)}")

        def contact_in_group(contact, group_ids):
            for field in contact.get("FieldValues", []):
                if field.get("SystemCode") == "Groups":
                    for group in field.get("Value", []):
                        if group.get("Id") in group_ids:
                            return True
            return False
        
        member_ids_by_group = [c["Id"] for c in contacts if contact_in_group(c, membergroup_ids)]
        logger.debug(f"Count of member_ids_by_group: {len(member_ids_by_group)}")

        current_registrant_ids = [c.get("Contact",{}).get("Id") for c in registrants]

        # build list of potential registrants by combining level and group ids and removing current registrants
        temp_ids = list(set(members_ids_by_level + member_ids_by_group))
        potential_registrant_ids = [cid for cid in temp_ids if cid not in current_registrant_ids]
        
        logger.debug(f"Count of current registrants: {len(current_registrant_ids)}")
        logger.debug(f"Count of potential registrants: {len(potential_registrant_ids)}")

        # Given list potential_registrant_ids, create sublists by membership status (e.g., Active, etc.)
        status_groups = defaultdict(list)
        for contact in contacts:
            cid = contact.get("Id")
            if cid in potential_registrant_ids:
                status = contact.get("Status","Unknown")
                status_groups[status].append(cid)

        for key in status_groups.keys():
            logger.debug(f"Status: {key}, Count: {len(status_groups[key])}")           

        # Derive list of potential ticket types

        registration_types = event.get("Details",{}).get("RegistrationTypes",{})
        if not registration_types:
            click.echo(f"No registration types found for event ID {event_id}.")
            return
        logger.trace(f"Registration types: {json.dumps(registration_types,indent=2)}")

        registration_type_ids = [item["Id"] for item in registration_types]
        logger.debug( f"Registration type ids: { registration_type_ids }" )
        if len(registration_type_ids) > 1:
            click.echo(f"Multiple registration types found for event ID {event_id}.")
            return

        #logger.debug(f"Contact: {json.dumps([contact for contact in contacts if contact['DisplayName'] in ["Leonard, John"]], indent=2)}")

        if confirm:
            if status_groups:
                for key in status_groups.keys():
                    if len(status_groups[key]) > 0:


                        result = register_contacts_to_event(
                            contact_ids=status_groups[key],
                            event_id=event_id,
                            account_id=account_id,
                            reg_type_id=registration_type_ids[0]
                        )

                        click.echo(f"[{key}] registrations: {len(result["success"])} successful.")
                        click.echo(f"[{key}] registrations: {len(result["failed"])} failed.")
                    else:
                        logger.debug(f"Key {key} has no records to process.")
            else:
                click.echo("No records to process.")                
        return
        event_details = get_event_details( account_id, event_id )
        access_control = event_details.get("Details",{}).get("AccessControl",{})
        logger.debug( json.dumps(access_control,indent=2) )


        if as_json:
            click.echo(json.dumps(registrants, indent=2))
        else:
            for reg in registrants:
                name = reg.get("DisplayName", "Unknown")
                click.echo(f"Name: {name}")

    
    except Exception as e:
        #logger.error(f"Error fetching registrants: {e}")
        click.echo(f"Error: {e}")
