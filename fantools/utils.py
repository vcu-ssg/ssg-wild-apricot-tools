"""
Utility functions for managing AWS accounts.
"""

import os
import json
import click
from datetime import datetime
from loguru import logger

def list_accounts_summaries(accounts):
    """List account summaries"""
    keys_to_check = ['Id','Name','PrimaryDomainName']  # List of keys to check
    for account in accounts:
        for key in keys_to_check:
            if key in account:
                click.echo(f"{key}: {account[key]}")
            else:
                click.echo(f"No '{key}' key found in account")

def get_event_display_date(event: dict) -> str:
    """Return StartDate if StartTimeSpecified, otherwise EndDate if EndTimeSpecified."""
    return_date = None
    if event.get("StartTimeSpecified"):
        return_date = event.get("StartDate")
    elif event.get("EndTimeSpecified"):
        return_date = event.get("EndDate")
    if return_date:
        try:
            return_date = datetime.fromisoformat(return_date).strftime("%Y-%m-%d %H:%M")
        except ValueError:
            logger.error(f"Invalid date format for event ID {event.get('Id')}: {return_date}")
            return_date = None
    return return_date

def list_events_details( event_list: dict ):
    """List Wild Apricot events by date, name, and ID, or show full event details for a given ID."""
    try:
        if not event_list:
            click.echo("No events found.")
            return
        
        logger.trace(f"Event list: {event_list}")

        events = event_list.get("Events", [])

        for e in events:
            name = e.get("Name", "Unnamed Event")
            eid = e.get("Id", "Unknown ID")
            date_str = get_event_display_date(e)

            if not date_str:
                continue  # Skip if no date available

            event_year = datetime.fromisoformat(date_str).year

            click.echo(f"{date_str} | {eid}: {name}")

    except Exception as e:
        click.echo(f"Error: {e}")


def list_event_details( event_list: dict, **kwargs ):
    """List Wild Apricot events by date, name, and ID, or show full event details for a given ID."""
    try:
        if not event_list:
            click.echo("No events found.")
            return
        
        logger.trace(f"Event list: {event_list}")

        events = event_list.get("Events", [])

        for e in events:

            name = e.get("Name", "Unnamed Event")
            eid = e.get("Id", "Unknown ID")
            date_str = get_event_display_date(e)

            if not date_str:
                continue  # Skip if no date available

            event_year = datetime.fromisoformat(date_str).year

            #click.echo(f"{date_str} | {eid}: {name}")
            click.echo(json.dumps( e,indent=2))



    except Exception as e:
        click.echo(f"Error: {e}")
