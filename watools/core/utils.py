"""
Utility functions for managing AWS accounts.
"""

import os
import csv
import ast
import json
import click
import inspect

from typing import Any
from loguru import logger
from datetime import datetime, timedelta, timezone, date
from collections import defaultdict, Counter


import click


def default_contacts_csv_filename():
    return f"contacts-{date.today().isoformat()}.csv"

def display_kv_table(data: dict, columns: list[str] = None, fill="."):
    # Filter to specified columns if provided
    items = (
        [(k, data.get(k, "")) for k in columns]
        if columns else
        list(data.items())
    )

    if not items:
        click.echo("No data to display.")
        return

    max_key_len = max(len(str(k)) for k, _ in items)
    for k, v in items:
        padded_key = str(k).ljust(max_key_len, fill)
        click.echo(f"{padded_key} : {v}")


def display_table(data: list[dict], columns: list[str | dict], max_col_width=40, separator="  "):
    if not data:
        click.echo("No data to display.")
        return

    # Normalize columns to (key, label) tuples
    normalized_columns = []
    for col in columns:
        if isinstance(col, dict):
            key, label = next(iter(col.items()))
        else:
            key, label = col, col
        normalized_columns.append((key, label))

    # Compute column widths
    col_widths = []
    for key, label in normalized_columns:
        max_data_width = max((len(str(row.get(key, ""))) for row in data), default=0)
        width = min(max(max_data_width, len(label)), max_col_width)
        col_widths.append(width)

    # Print header
    header = separator.join(
        f"{label:<{col_widths[i]}}" for i, (_, label) in enumerate(normalized_columns)
    )
    click.echo(header)
    click.echo("-" * len(header))

    # Print rows
    for row in data:
        line = separator.join(
            f"{str(row.get(key, '')).strip():<{col_widths[i]}}"[:col_widths[i]]
            for i, (key, _) in enumerate(normalized_columns)
        )
        click.echo(line)


class UnsafeExpression(Exception):
    pass

def safe_eval_expr(expr: str, context: dict) -> bool:
    """
    Safely evaluate a restricted Python expression using the AST module.
    Supports comparisons, boolean ops, and parentheses.
    """

    tree = ast.parse(expr, mode='eval')

    def _eval(node: ast.AST) -> Any:
        if isinstance(node, ast.Expression):
            return _eval(node.body)

        elif isinstance(node, ast.BoolOp):
            values = [_eval(v) for v in node.values]
            if isinstance(node.op, ast.And):
                return all(values)
            elif isinstance(node.op, ast.Or):
                return any(values)
            else:
                raise UnsafeExpression(f"Unsupported boolean operator: {type(node.op).__name__}")

        elif isinstance(node, ast.Compare):
            left = _eval(node.left)
            for op, comparator in zip(node.ops, node.comparators):
                right = _eval(comparator)
                if isinstance(op, ast.Eq):
                    if not (left == right): return False
                elif isinstance(op, ast.NotEq):
                    if not (left != right): return False
                elif isinstance(op, ast.Lt):
                    if not (left < right): return False
                elif isinstance(op, ast.LtE):
                    if not (left <= right): return False
                elif isinstance(op, ast.Gt):
                    if not (left > right): return False
                elif isinstance(op, ast.GtE):
                    if not (left >= right): return False
                elif isinstance(op, ast.In):
                    if not (left in right): return False
                elif isinstance(op, ast.NotIn):
                    if not (left not in right): return False
                else:
                    raise UnsafeExpression(f"Unsupported comparison operator: {type(op).__name__}")
            return True

        elif isinstance(node, ast.Name):
            return context.get(node.id, None)

        elif isinstance(node, ast.Constant):  # Python 3.8+
            return node.value

        elif isinstance(node, ast.Str):  # For Python <3.8 compatibility
            return node.s
        elif isinstance(node, ast.Num):  # Python <3.8
            return node.n
        elif isinstance(node, ast.NameConstant):  # True/False/None
            return node.value

        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            return not _eval(node.operand)

        else:
            raise UnsafeExpression(f"Unsupported expression type: {type(node).__name__}")

    return bool(_eval(tree))


def filter_events(
    events: list[dict],
    *,
    show_all=False,
    future=False,
    year=None,
    month=None,
    after=None,
    before=None,
    query: str = None
) -> list[dict]:
    """
    Filters a list of event dictionaries based on date and optional query string.
    """

    now = datetime.now(timezone.utc).astimezone()  # Make 'now' timezone-aware
    default_after = now - timedelta(days=30)
    
    has_explicit_time_filter = any([after, before, year, month, future, show_all])
    use_after = after if after else (None if has_explicit_time_filter else default_after)
    use_before = before if not show_all else None  # Keep before if set, or disable if showing all

    filtered = []

    for event in events:
        try:
            dt = datetime.fromisoformat(event.get("StartDate", ""))
        except Exception:
            continue  # Skip events with bad/missing StartDate

        # Time filters
        if use_after and dt < use_after:
            continue
        if use_before and dt > use_before:
            continue
        if future and dt < now:
            continue
        if year and dt.year != year:
            continue
        if month and dt.month != month:
            continue

        # Safe ad hoc query
        if query:
            try:
                if not safe_eval_expr(query, event):
                    continue
            except UnsafeExpression as e:
                logger.error(f"Query error: {e}", fg="red")
                return []
            except Exception as e:
                logger.error(f"Unexpected query error: {e}", fg="red")
                return []

        filtered.append(event)

    return filtered


def list_account( account ):
    """ List single account details """
    keys_to_view = ['Id','Name','PrimaryDomainName','ContactEmail','wat_contact_limit_info']  # List of keys to check
    display_kv_table( account, columns=keys_to_view )


def list_accounts(accounts):
    """List account summaries"""
    keys_to_view = ['Id','Name',{'wat_contact_limit_info':'Contacts'},'PrimaryDomainName']  # List of keys to check
    display_table( accounts, keys_to_view )


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

def list_events( events: list|dict,  \
                columns: list[str|dict] = ["Id",{"wat_start_date":"Date"},{"wat_start_day":"Day"},{"wat_start_time":"Start"},{"wat_confirmed_and_limit":"Conf/Tot"},"Name"], max_col_width=50):
    """List Wild Apricot events by date, name, and ID, or show full event details for a given ID."""
    if not events:
        click.echo("No events found.")
        return
 
    if isinstance(events, dict):
        events = events.get("Events", [])

    display_table( events, columns, max_col_width=max_col_width)



def list_event_details( event : dict, report_type: str = "summary" ):
    """List Wild Apricot events by date, name, and ID, or show full event details for a given ID."""

    try:
        if not event:
            click.echo("No event details provided.")
            return
        
        logger.trace(f"Event: {json.dumps(event,indent=2)}")
        logger.trace(f"Keys: {event.keys()}")

        summary_items = ["Id","Name","Location","EventType","StartDate","wat_start_day","EndDate","StartTimeSpecified","EndTimeSpecified",
                         'PendingRegistrationsCount', 'ConfirmedRegistrationsCount','WaitListRegistrationCount', 'CheckedInAttendeesNumber',
                         ]
        display_items = ['RegistrationsLimit',
                         'InviteeStat', 'Tags',
                         'AccessLevel',
                         'HasEnabledRegistrationTypes']

        display_kv_table( event, summary_items )


      
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

            name = contact.get("Name", "Unnamed person")
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


def write_contacts_to_csvxx( contacts, filename ):
    """ Write contacts to CSV file """

    click.echo(f"writing CSV to: {filename}, records: {len(contacts)}")

    contacts = normalize_contacts( contacts )
    click.echo( json.dumps( contacts, indent=2) )

    return

def extract_value(value):
    if isinstance(value, dict):
        return value.get("Label") or value.get("Value") or str(value)
    elif isinstance(value, list):
        return "; ".join(map(str, value))
    elif value is None:
        return ""
    return value

def looks_like_leading_zero_number(s):
    return isinstance(s, str) and s.isdigit() and len(s) > 1 and s.startswith("0")

def write_contacts_to_csv(contacts, filename):
    all_columns = {}
    flattened_rows = []
    column_values = {}  # Track all values per column

    for contact in contacts:
        flat_row = {}
        top_level_keys = set(contact.keys())

        for key, value in contact.items():
            if key == "FieldValues":
                continue
            col_key = (key, key)
            val = extract_value(value)
            flat_row[col_key] = val
            all_columns[col_key] = True
            column_values.setdefault(col_key, []).append(val)

        for field in contact.get("FieldValues", []):
            field_name = field.get("FieldName")
            system_code = field.get("SystemCode")

            if system_code in top_level_keys:
                system_code += "_dup"
                field_name += " (duplicate)"

            col_key = (field_name, system_code)
            val = extract_value(field.get("Value"))
            flat_row[col_key] = val
            all_columns[col_key] = True
            column_values.setdefault(col_key, []).append(val)

        flattened_rows.append(flat_row)

    # Detect which columns require string handling (e.g., leading zero numbers)
    columns_force_string = set()
    for col, values in column_values.items():
        if any(looks_like_leading_zero_number(str(v)) for v in values):
            columns_force_string.add(col)

    # Ensure 'Id' appears first
    sorted_columns = sorted(
        all_columns.keys(),
        key=lambda x: (0 if x[0] == "Id" else 1, x[0].lower())
    )

    # Write CSV
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([col[0] for col in sorted_columns])  # FieldName
        writer.writerow([col[1] for col in sorted_columns])  # SystemCode

        for row in flattened_rows:
            output_row = []
            for col in sorted_columns:
                val = row.get(col, "")
                if col in columns_force_string:
                    val = f"'{val}"  # Prefix with single quote to preserve formatting in Excel
                output_row.append(val)
            writer.writerow(output_row)

    print(f"Wrote {len(flattened_rows)} contacts to {filename}")
    


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

def member_legend():
    # Explanation

    click.echo("")
    click.echo("Active     : Members whose status is Active and membership is current.")
    click.echo("P.Renew    : Members whose renewal is overdue but still within the grace period (PendingRenewal).")
    click.echo("P.New      : Members who have applied and are awaiting approval (PendingNew).")
    click.echo("Lapsed     : Members whose membership has expired and are outside the grace period.")
    click.echo("Unknown    : Contacts with no recognized status or missing status field.")
