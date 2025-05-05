
import click
import json

from datetime import datetime
from loguru import logger

from fantools.api import get_events_details, get_event_registrants, get_event_registration_types
from fantools.utils import list_events_details, list_event_details


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
        events = get_events_details( account_id )
        if events:
            if event_id:
                events = [event for event in events.get("Events", []) if event.get("Id") == event_id]
                if not events:
                    click.echo(f"No event found with ID: {event_id}")
                    return
                events = {"Events": events}
            if as_json:
                click.echo(json.dumps(events, indent=2))
            else:
                if event_id:
                    list_event_details( events )
                else:
                    list_events_details( events )
        else:
            click.echo("No events found.")
            return
    

@events.command("registrants")
@click.option('--account-id', type=int, required=False, default=None, help='Account ID to fetch registrants for')
@click.option('--event-id', type=int, required=False, default=None, help='Event ID to fetch registrants for')
@click.option('--as-json', is_flag=True, default=False, help='Output registrants in JSON format')
@click.pass_context
def registrants(ctx, account_id, event_id, as_json):
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
        registrants = get_event_registrants(account_id, event_id)
        logger.trace( json.dumps(registrants,indent=2))

        if not registrants:
            click.echo(f"No registrants found for event ID {event_id}.")
            return

        if as_json:
            click.echo(json.dumps(registrants, indent=2))
        else:
            for reg in registrants:
                name = reg.get("DisplayName", "Unknown")
                click.echo(f"Name: {name}")
    
    except Exception as e:
        logger.error(f"Error fetching registrants: {e}")
        click.echo(f"Error: {e}")

@events.command("registration-types")
@click.option('--account-id', type=int, required=False, default=None, help='Account ID to fetch registrants for')
@click.option('--event-id', type=int, required=False, default=None, help='Event ID to fetch registrants for')
@click.option('--as-json', is_flag=True, default=False, help='Output registrants in JSON format')
@click.pass_context
def registration_types(ctx, account_id, event_id, as_json):
    """List registrant types for a specific event."""

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
        registration_types = get_event_registration_types(account_id, event_id)
        logger.trace( json.dumps(registration_types,indent=2))

        if not registration_types:
            click.echo(f"No registration_types found for event ID {event_id}.")
            return

        if as_json:
            click.echo(json.dumps(registration_types, indent=2))
        else:
            for reg in registration_types:
                name = reg.get("Name","unknown")
                click.echo(f"{name}")
                #click.echo( json.dumps( reg,indent=2) )
    
    except Exception as e:
        logger.error(f"Error fetching registrants: {e}")
        click.echo(f"Error: {e}")