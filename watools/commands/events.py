
import click
import json

from datetime import datetime
from loguru import logger

from collections import defaultdict

from watools.core.api import get_events, get_event_details, get_event_registrants, \
    get_default_membership_level_ids, get_default_membergroup_ids, \
    get_contacts, register_contacts_to_event

from watools.core.utils import filter_events, list_events, list_event_details


@click.group("events", invoke_without_command=True)
@click.option('--event-id', type=int, help='Filter by specific event ID')
@click.option('--all', 'show_all', is_flag=True, help='Show all events, bypass default date filter')
@click.option('--future', is_flag=True, help='Show only future events')
@click.option('--year', type=int, help='Filter by event start year')
@click.option('--month', type=int, help='Filter by event start month')
@click.option('--after', type=click.DateTime(), help='Only events after this date')
@click.option('--before', type=click.DateTime(), help='Only events before this date')
@click.option('--query', type=str, help='Ad hoc query expression (e.g., \'ConfirmedRegistrationsCount > 5 and "Diamond" in Name\')')
@click.option('--as-json', is_flag=True, default=False, help='Output events as JSON')
@click.pass_context
def cmd(ctx, event_id, show_all,future, year, month, after, before, query, as_json):
    """Manage Wild Apricot events."""

    ctx.ensure_object(dict)
    account_id = ctx.obj.get("account_id")
    if not account_id:
        logger.error("No account ID provided. Use --account-id or configure it.")
        return

    logger.debug(f"Fetching events for account {account_id}")
    event_data = get_events(account_id)
    events = event_data.get("Events", [])

    # Filter by ID directly
    if event_id:
        events = [e for e in events if str(e.get("Id")) == str(event_id)]

        if not events:
            click.echo(f"No event found with ID: {event_id}")
            return

        # Show single event details
        event = get_event_details(event_id, account_id=account_id)
        logger.debug( event )
        if event:
            if as_json:
                click.echo(json.dumps(event, indent=2))
            else:
                list_event_details(event)  # Assuming this is defined
        else:
            click.echo(f"Failed to load details for event ID {event_id}")
        return

    # Apply filters
    events = filter_events(
        events,
        show_all=show_all,
        future=future,
        year=year,
        month=month,
        after=after,
        before=before,
        query=query
    )

    if not events:
        click.echo("No events found.")
        return

    if as_json:
        click.echo(json.dumps(events, indent=2))
    else:
        click.echo("")  # spacing
        list_events(
            events,
            columns=[
                "Id",
                {"wat_start_day": "Day"},
                {"wat_start_date": "Date"},
                {"wat_start_time": "Time"},
                {"wat_confirmed_and_limit":"Cnf/Max"},
                {"Name": "Title"},
            ]
        )    

@cmd.command()
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
