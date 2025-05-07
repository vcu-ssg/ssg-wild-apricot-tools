"""
Utility functions for managing AWS accounts.
"""

import os
import json
import click

from loguru import logger
from datetime import datetime
from collections import defaultdict, Counter

def list_accounts(accounts):
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

def list_events( event_list: dict ):
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
            event_type = e.get("EventType", "Unknown Type")
            date_str = get_event_display_date(e)

            if not date_str:
                continue  # Skip if no date available

            event_year = datetime.fromisoformat(date_str).year

            click.echo(f"{date_str:16} | {eid:>8} | {event_type:<8} | {name}")

    except Exception as e:
        click.echo(f"Error: {e}")


def list_event_details( event : dict, report_type: str = "summary" ):
    """List Wild Apricot events by date, name, and ID, or show full event details for a given ID."""

    try:
        if not event:
            click.echo("No event details provided.")
            return
        
        logger.trace(f"Event: {json.dumps(event,indent=2)}")
        logger.trace(f"Keys: {event.keys()}")

        summary_items = ["Id","Name","Location","EventType","StartDate","EndDate","StartTimeSpecified","EndTimeSpecified",
                         'PendingRegistrationsCount', 'ConfirmedRegistrationsCount','WaitListRegistrationCount', 'CheckedInAttendeesNumber',
                         ]
        display_items = ['RegistrationsLimit',
                         'InviteeStat', 'Tags',
                         'AccessLevel',
                         'HasEnabledRegistrationTypes']

        for item in summary_items:
            if item in event.keys():
                click.echo(f"{item:>33} : {event[item]}")
            else:
                click.echo(f"No '{item}' key found in event")

        if report_type in ["details"]:
            for item in display_items:
                if item in event.keys():
                    click.echo(f"{item:>33} : {event[item]}")
                else:
                    click.echo(f"No '{item}' key found in event")

        if report_type in ["details","full"]:

            for item in event.get("Details",{}).keys():
                value = event.get("Details",{}).get(item)
                if item in ["EventRegistrationFields","DescriptionHtml"]:
                    value = "(Too long to display)"
                elif item in ["RegistrationTypes"]:
                    value = ".".join([f"'{x.get('Name','Unknown')}'" for x in value])
                elif item in ["TimeZone"]:
                    value = value.get("Name","Unknown")
                elif item in ["Organizer"]:
                    if value:
                        if isinstance(value, dict):
                            value = value.get("Id","Unknown")
                click.echo(f"{item:>33} : {value}")

      
    except Exception as e:
        click.echo(f"Error: {e}")
        raise


def list_groups( group_list: dict ):
    """List Wild Apricot groups """
    try:
        if not group_list:
            click.echo("No groups found.")
            return
        
        logger.trace(f"Group list: {group_list}")

        groups = group_list.get("MemberGroups", [])

        for g in groups:

            name = g.get("Name", "Unnamed Event")
            eid = g.get("Id", "Unknown ID")

            click.echo(f"{eid} | {name}")
            
    except Exception as e:
        click.echo(f"Error: {e}")

def list_group_details( group_list: dict, **kwargs ):
    """List Wild Apricot groups """
    try:
        if not group_list:
            click.echo("No groups found.")
            return
        
        logger.trace(f"Group list: {group_list}")

        groups = group_list.get("MemberGroups", [])

        for g in groups:

            name = g.get("Name", "Unnamed Event")
            eid = g.get("Id", "Unknown ID")

            click.echo(f"{eid} | {name}")
            
    except Exception as e:
        click.echo(f"Error: {e}")


def list_contacts( contact_list: dict ):
    """List Wild Apricot contacts """
    try:
        if not contact_list:
            click.echo("No groups found.")
            return
        
        logger.trace(f"Contact list: {contact_list}")

        contacts = contact_list.get("Contacts", [])

        for contact in contacts:

            name = contact.get("Name", "Unnamed Event")
            eid = contact.get("Id", "Unknown ID")

            click.echo(f"{eid} | {name}")
            
    except Exception as e:
        click.echo(f"Error: {e}")

def list_contact_details( contact_list: dict ):
    """List Wild Apricot contacts """
    try:
        if not contact_list:
            click.echo("No groups found.")
            return
        
        logger.trace(f"Contact list: {contact_list}")

        contacts = contact_list.get("Contacts", [])

        for contact in contacts:

            name = contact.get("Name", "Unnamed Event")
            eid = contact.get("Id", "Unknown ID")

            click.echo(f"{eid} | {name}")
            
    except Exception as e:
        click.echo(f"Error: {e}")


def summarize_contact_fields(contacts: list) -> list:
    """
    Analyzes the contact list and returns a sorted list of all unique field names.
    Verifies that all contacts contain the same fields.

    Parameters:
    - contacts: List of contact dictionaries

    Returns:
    - List of field names (keys)
    """
    if not contacts:
        click.echo("No contacts provided.")
        return []

    # Start with the keys from the first contact
    base_keys = set(contacts[0].keys())
    consistent = True

    for idx, contact in enumerate(contacts[1:], start=2):
        keys = set(contact.keys())
        if keys != base_keys:
            consistent = False
            extra = keys - base_keys
            missing = base_keys - keys
            click.echo(f"Inconsistent fields at contact #{idx}:")
            if extra:
                click.echo(f"  Extra fields: {sorted(extra)}")
            if missing:
                click.echo(f"  Missing fields: {sorted(missing)}")

    sorted_keys = sorted(base_keys)
    click.secho(f"\nTotal unique fields: {len(sorted_keys)}", fg="green")
    for field in sorted_keys:
        click.echo(f" - {field}")

    if consistent:
        click.secho("\nAll contacts have the same fields.", fg="green")
    else:
        click.secho("\nSome contacts have inconsistent fields.", fg="yellow")

    return sorted_keys

def normalize_contacts(contacts: list) -> list:
    """
    Normalize a list of contact records so all dictionaries have the same keys.

    Missing keys are added with a value of None.

    Returns:
    - List of normalized contact dictionaries
    """
    # Gather the full set of all keys
    all_keys = set()
    for contact in contacts:
        all_keys.update(contact.keys())

    normalized = []
    for contact in contacts:
        # Fill in missing keys with None
        normalized_contact = {key: contact.get(key, None) for key in all_keys}
        normalized.append(normalized_contact)

    click.secho(f"Normalized all contacts to {len(all_keys)} fields.", fg="blue")
    return normalized

from collections import Counter
import click

def summarize_membership_levels(contacts: list):
    """
    Print a summary table of membership levels from an unnormalized contact list.

    Contacts without 'MembershipLevel' are grouped under ID=None and Name='Non-Member'.
    """
    counter = Counter()
    level_names = {}

    for contact in contacts:
        level = contact.get("MembershipLevel")
        if isinstance(level, dict):
            level_id = level.get("Id")
            level_name = level.get("Name", "Unknown Level")
        else:
            level_id = None
            level_name = "Non-Member"

        counter[level_id] += 1
        level_names[level_id] = level_name

    if not counter:
        click.secho("No membership level data found.", fg="yellow")
        return

    # Sort: Non-Member last, then by count desc, then by name
    sorted_levels = sorted(
        counter.items(),
        key=lambda x: (x[0] is None, -x[1], level_names.get(x[0], ""))
    )

    click.secho("\nMembership Level Summary", bold=True, fg="cyan")
    click.echo(f"{'Level ID':<10} {'Count':>5}  {'Level Name'}")
    click.echo("-" * 50)
    for level_id, count in sorted_levels:
        level_name = level_names.get(level_id, "Unknown")
        click.echo(f"{str(level_id):<10} {count:>5}  {level_name}")
    click.echo("-" * 50)
    click.secho(f"{'Total Contacts':<10} {sum(counter.values()):>5}", fg="green")


from collections import defaultdict, Counter
import click

def summarize_member_groups(contacts: list):
    """
    Summarize group participation using 'FieldValues' with FieldName == 'Group participation'.

    Output:
    - Group ID
    - Count of contacts in that group
    - Group name
    """
    group_counts = Counter()
    group_names = {}

    for contact in contacts:
        field_values = contact.get("FieldValues", [])
        for field in field_values:
            if field.get("FieldName") == "Group participation":
                groups = field.get("Value", [])
                for group in groups:
                    group_id = group.get("Id")
                    group_label = group.get("Label", "Unknown Group")
                    if group_id:
                        group_counts[group_id] += 1
                        group_names[group_id] = group_label

    if not group_counts:
        click.secho("No group participation data found in FieldValues.", fg="yellow")
        return

    sorted_groups = sorted(group_counts.items(), key=lambda x: (-x[1], group_names.get(x[0], "")))

    click.secho("\nMember Group Summary", bold=True, fg="cyan")
    click.echo(f"{'Group ID':<10} {'Count':>5}  {'Group Name'}")
    click.echo("-" * 50)
    for group_id, count in sorted_groups:
        group_name = group_names.get(group_id, "Unknown")
        click.echo(f"{group_id:<10} {count:>5}  {group_name}")
    click.echo("-" * 50)
    click.secho(f"{'Total Group Memberships':<10} {sum(group_counts.values()):>5}", fg="green")



def summarize_levels_by_status(contacts: list):
    """
    Print a table summarizing membership levels by status.

    Columns:
    - Level ID (left-aligned)
    - Membership status counts (right-aligned, using short labels)
    - Row total (right-aligned)
    - Level Name (left-aligned, max 30 chars)
    """
    summary = defaultdict(Counter)
    level_names = {}
    all_statuses = set()

    # Prepare data
    for contact in contacts:
        level = contact.get("MembershipLevel")
        if isinstance(level, dict):
            level_id = level.get("Id")
            level_name = level.get("Name", "Unknown Level")
        else:
            level_id = None
            level_name = "Non-Member"

        raw_status = str(contact.get("Status") or "Unknown")
        status = {
            "PendingNew": "P.New",
            "PendingRenewal": "P.Renew"
        }.get(raw_status, raw_status)

        summary[level_id][status] += 1
        level_names[level_id] = level_name
        all_statuses.add(status)

    # Column settings

    preferred_order = ["Active", "P.Renew", "P.New", "Lapsed", "Unknown"]
    # Only include statuses that actually exist in your data
    status_columns = [status for status in preferred_order if status in all_statuses]
    
    #level_ids = sorted(summary.keys(), key=lambda x: (x is None, x or 0))

    level_ids = sorted(
        summary.keys(),
        key=lambda x: (
            level_names.get(x, "Non-Member") in {"Friend", "Non-Member"},  # True → sort last
            level_names.get(x, "Non-Member").lower()
        )
    )

    col_widths = {
        "level_id": 10,
        "status": 8,
        "row_total": 8,
        "level_name": 30
    }

    # Print header
    click.secho("\nMembership Level Summary by Status", bold=True, fg="cyan")
    header = f"{'Level ID':<{col_widths['level_id']}} " + \
             " ".join(f"{status:>{col_widths['status']}}" for status in status_columns) + " " + \
             f"{'Total':>{col_widths['row_total']}} " + \
             f"{'Level Name':<{col_widths['level_name']}}"
    click.echo(header)
    click.echo("-" * (
        col_widths['level_id'] + 1 +
        len(status_columns) * (col_widths['status'] + 1) +
        col_widths['row_total'] + 1 +
        col_widths['level_name']
    ))

    # Print rows
    total_counts = Counter()
    for level_id in level_ids:
        row = f"{str(level_id or 'None'):<{col_widths['level_id']}} "
        row_total = 0
        for status in status_columns:
            count = summary[level_id].get(status, 0)
            row += f"{count:>{col_widths['status']}} "
            total_counts[status] += count
            row_total += count
        row += f"{row_total:>{col_widths['row_total']}} "
        level_name = level_names.get(level_id, "Unknown")[:col_widths['level_name']]
        row += f"{level_name:<{col_widths['level_name']}}"
        click.echo(row)

    # Footer total row
    footer = f"{'Total':<{col_widths['level_id']}} "
    grand_total = 0
    for status in status_columns:
        count = total_counts[status]
        footer += f"{count:>{col_widths['status']}} "
        grand_total += count
    footer += f"{grand_total:>{col_widths['row_total']}} "
    footer += " " * col_widths['level_name']

    click.echo("-" * (
        col_widths['level_id'] + 1 +
        len(status_columns) * (col_widths['status'] + 1) +
        col_widths['row_total'] + 1 +
        col_widths['level_name']
    ))
    click.secho(footer, fg="green")

    click.echo("")
    click.echo("Active     : Members whose status is Active and membership is current.")
    click.echo("P.Renew    : Members whose renewal is overdue but still within the grace period (PendingRenewal).")
    click.echo("P.New      : Members who have applied and are awaiting approval (PendingNew).")
    click.echo("Lapsed     : Members whose membership has expired and are outside the grace period.")
    click.echo("Unknown    : Contacts with no recognized status or missing status field.")


def summarize_groups_by_status(contacts: list):
    """
    Print a table summarizing group participation by membership status.

    Columns:
    - Group ID (left-aligned)
    - Membership status counts (right-aligned, using short labels)
    - Row total (right-aligned)
    - Group Name (left-aligned, max 30 chars)
    """
    summary = defaultdict(Counter)
    group_names = {}
    all_statuses = set()

    for contact in contacts:
        status_raw = str(contact.get("Status") or "Unknown")
        status = {
            "PendingNew": "P.New",
            "PendingRenewal": "P.Renew"
        }.get(status_raw, status_raw)

        field_values = contact.get("FieldValues", [])
        for field in field_values:
            if field.get("SystemCode") == "Groups" and isinstance(field.get("Value"), list):
                for group in field["Value"]:
                    group_id = group.get("Id")
                    group_name = group.get("Label", "Unknown Group")
                    summary[group_id][status] += 1
                    group_names[group_id] = group_name
                    all_statuses.add(status)

    # Preferred column order
    preferred_order = ["Active", "P.Renew", "P.New", "Lapsed", "Unknown"]
    status_columns = [status for status in preferred_order if status in all_statuses]

    group_ids = sorted(
        summary.keys(),
        key=lambda x: (
            group_names.get(x, "Unknown Group") in {"Friend", "Non-Member"},  # sort last if needed
            group_names.get(x, "Unknown Group").lower()
        )
    )

    col_widths = {
        "group_id": 10,
        "status": 8,
        "row_total": 8,
        "group_name": 30
    }

    # Print header
    click.secho("\nGroup Participation Summary by Status", bold=True, fg="cyan")
    header = f"{'Group ID':<{col_widths['group_id']}} " + \
             " ".join(f"{status:>{col_widths['status']}}" for status in status_columns) + " " + \
             f"{'Total':>{col_widths['row_total']}} " + \
             f"{'Group Name':<{col_widths['group_name']}}"
    click.echo(header)
    click.echo("-" * (
        col_widths['group_id'] + 1 +
        len(status_columns) * (col_widths['status'] + 1) +
        col_widths['row_total'] + 1 +
        col_widths['group_name']
    ))

    # Print rows
    total_counts = Counter()
    for group_id in group_ids:
        row = f"{str(group_id or 'None'):<{col_widths['group_id']}} "
        row_total = 0
        for status in status_columns:
            count = summary[group_id].get(status, 0)
            row += f"{count:>{col_widths['status']}} "
            total_counts[status] += count
            row_total += count
        row += f"{row_total:>{col_widths['row_total']}} "
        group_name = group_names.get(group_id, "Unknown Group")[:col_widths['group_name']]
        row += f"{group_name:<{col_widths['group_name']}}"
        click.echo(row)

    # Footer row
    footer = f"{'Total':<{col_widths['group_id']}} "
    grand_total = 0
    for status in status_columns:
        count = total_counts[status]
        footer += f"{count:>{col_widths['status']}} "
        grand_total += count
    footer += f"{grand_total:>{col_widths['row_total']}} "
    footer += " " * col_widths['group_name']

    click.echo("-" * (
        col_widths['group_id'] + 1 +
        len(status_columns) * (col_widths['status'] + 1) +
        col_widths['row_total'] + 1 +
        col_widths['group_name']
    ))
    click.secho(footer, fg="green")

    # Explanation
    click.echo("")
    click.echo("Active     : Members whose status is Active and membership is current.")
    click.echo("P.Renew    : Members whose renewal is overdue but still within the grace period (PendingRenewal).")
    click.echo("P.New      : Members who have applied and are awaiting approval (PendingNew).")
    click.echo("Lapsed     : Members whose membership has expired and are outside the grace period.")
    click.echo("Unknown    : Contacts with no recognized status or missing status field.")
