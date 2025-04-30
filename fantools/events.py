import click
import json

from datetime import datetime

from .api import get_events, get_event_registration_types

@click.group()
@click.option('--id', 'event_id', type=int, help='Filter by specific event ID')
@click.pass_context
def events(ctx, event_id):
    """Manage Wild Apricot events."""
    ctx.ensure_object(dict)
    ctx.obj['event_id'] = event_id


def get_event_display_date(event: dict) -> str:
    """Return StartDate if StartTimeSpecified, otherwise EndDate if EndTimeSpecified."""
    if event.get("StartTimeSpecified"):
        return event.get("StartDate")
    elif event.get("EndTimeSpecified"):
        return event.get("EndDate")
    else:
        return None


@events.command("list")
@click.option('--year', type=int, help='Filter events by year')
@click.pass_context
def list_events(ctx, year):
    """List Wild Apricot events by date, name, and ID, or show full event details for a given ID."""
    try:
        event_list = get_events()
        event_id = ctx.obj.get('event_id')

        events = event_list.get("Events", [])

        if event_id:
            matching = [e for e in events if e.get("Id") == event_id]
            if matching:
                click.echo(json.dumps(matching[0], indent=2))
            else:
                click.echo(f"No event found with ID {event_id}")
        else:
            for e in events:
                name = e.get("Name", "Unnamed Event")
                eid = e.get("Id", "Unknown ID")
                date_str = get_event_display_date(e)

                if not date_str:
                    continue  # Skip if no date available

                event_year = datetime.fromisoformat(date_str).year

                if year and event_year != year:
                    continue  # Skip events not matching the selected year

                click.echo(f"{date_str} | {eid}: {name}")

    except Exception as e:
        click.echo(f"Error: {e}")

@events.command("regtype")
@click.pass_context
def list_regtypes(ctx):
    """List registration types for a specific event."""
    try:
        event_id = ctx.obj.get("event_id")
        if not event_id:
            raise click.UsageError("Please provide --id to specify the event.")

        regtypes = get_event_registration_types(event_id)
        if not regtypes:
            click.echo("No registration types found.")
            return

        click.echo( json.dumps( regtypes, indent=2) )
        #for rt in regtypes:
        #    click.echo(json.dumps(rt, indent=3))
        #    click.echo(f"{rt['Id']}: {rt['Name']}")

    except Exception as e:
        click.echo(f"Error: {e}")
