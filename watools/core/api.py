"""
Watools core API module
"""
import os
import ssl
import time
import json
import socket
import platform
import subprocess
import shutil
from pathlib import Path

import click
import requests
from loguru import logger
from requests.auth import HTTPBasicAuth
import certifi

# Updated import from CLI config singleton and shared paths
from watools.cli.config import config
from watools.paths import get_default_cache_dir


# Cache token in memory
_access_token = None
_token_expiry = "None"

# Default cache config
CACHE_FILE = get_default_cache_dir() / "contacts.json"
CACHE_EXPIRY_SECONDS = 3600

def load_contacts_cache(reload: bool = False):
    cache_file = config.contacts_cache_file
    if cache_file.exists():
        age = time.time() - cache_file.stat().st_mtime
        if reload:
            logger.debug("Forcing cache reload")
        elif age < config.cache_expiry_seconds:
            with open(cache_file, "r", encoding="utf-8") as f:
                logger.debug("Loaded contacts from cache.")
                return json.load(f)
        else:
            logger.debug("Cache expired. Will fetch new contacts.")
    return None

def save_contacts_cache(contacts: list):
    cache_file = config.contacts_cache_file 
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(contacts, f)
        logger.debug("Contacts saved to cache.")

def check_tls(timeout: int = 5):
    try:
        response = requests.get(config.api_base_url + "accounts", timeout=timeout)
        logger.debug(f"TLS check succeeded (HTTP status: {response.status_code})")
    except requests.exceptions.SSLError as e:
        logger.error("TLS certificate verification failed.")
        raise
    except requests.exceptions.ConnectionError as e:
        logger.error("Network error during TLS check.")
        raise
    except requests.exceptions.RequestException as e:
        logger.warning(f"Non-TLS API error ignored during check: {e}")

def get_access_token():
    global _access_token, _token_expiry

    CLIENT_ID = config.client_id
    CLIENT_SECRET = config.client_secret
    OAUTH_URL = config.oauth_url

    if _access_token and _token_expiry and time.time() < _token_expiry:
        return _access_token

    if not CLIENT_ID or not CLIENT_SECRET:
        raise ValueError("Missing client credentials.")

    data = {"grant_type": "client_credentials", "scope": "auto"}

    response = requests.post(
        OAUTH_URL,
        data=data,
        auth=HTTPBasicAuth(CLIENT_ID, CLIENT_SECRET),
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )

    if response.status_code == 200:
        token_info = response.json()
        _access_token = token_info["access_token"]
        _token_expiry = time.time() + token_info.get("expires_in", 1800) - 60
        return _access_token
    else:
        raise RuntimeError(f"OAuth token request failed: {response.status_code} {response.text}")

def get_headers():
    return {
        "Authorization": f"Bearer {get_access_token()}",
        "Accept": "application/json",
        "Content-Type": "application/json"
    }

def api_get(endpoint):
    url = config.api_base_url + endpoint
    headers = get_headers()
    response = requests.get(url, headers=headers)
    logger.debug(url)
    if response.ok:
        return response.json()
    else:
        raise RuntimeError(f"GET {url} failed: {response.status_code} {response.text}")

def api_get_following_redirect(endpoint):
    data = api_get(endpoint)
    if "ResultUrl" in data and data.get("State") == "Complete":
        return api_get(data["ResultUrl"].replace(config.api_base_url, ""))
    return data

def get_accounts():
    return api_get("accounts")

def get_events(account_id: int):
    if not account_id:
        raise ValueError("Account ID is required.")
    return api_get(f"accounts/{account_id}/events")

def get_default_membership_level_ids(account_id: int):
    levels = api_get(f"accounts/{account_id}/membershiplevels")
    return [level["Id"] for level in levels]

def get_membergroups(account_id: int):
    return api_get(f"accounts/{account_id}/membergroups")

def get_default_membergroup_ids(account_id: int):
    groups = api_get(f"accounts/{account_id}/membergroups")
    return [group["Id"] for group in groups]

def normalize_and_flatten_contacts(contacts: list):
    all_keys = set()
    flattened = []
    for contact in contacts:
        all_keys.update(contact.keys())

    for contact in contacts:
        flat = {k: contact.get(k, None) for k in all_keys}
        ml = contact.get("MembershipLevel")
        flat["MembershipLevelId"] = ml.get("Id") if isinstance(ml, dict) else None
        flat["MembershipLevelName"] = ml.get("Name") if isinstance(ml, dict) else None
        flattened.append(flat)

    logger.debug(f"Normalized {len(flattened)} contacts.")
    return flattened

def get_contacts(account_id: int, exclude_archived=True, max_wait=10, normalize_contacts=True, use_cache=True, reload=False):
    if use_cache:
        cached = load_contacts_cache(reload)
        if cached:
            return normalize_and_flatten_contacts(cached) if normalize_contacts else cached

    query_parts = []
    if exclude_archived:
        query_parts.append("$filter=IsArchived eq false")
        query_parts.append("$select=*")

    endpoint = f"accounts/{account_id}/contacts"
    if query_parts:
        endpoint += "?" + "&".join(query_parts)

    response = api_get(endpoint)
    if "ResultUrl" in response:
        result_url = response["ResultUrl"].replace(config.api_base_url, "")
        state = response.get("State")
        attempts = 0
        while state != "Complete" and attempts < max_wait:
            time.sleep(1.5)
            response = api_get(result_url)
            state = response.get("State")
            attempts += 1
        contacts = response.get("Contacts", [])
    else:
        contacts = response.get("Contacts", [])

    if use_cache and contacts:
        save_contacts_cache(contacts)

    return normalize_and_flatten_contacts(contacts) if normalize_contacts else contacts

def get_event_details(account_id: int, event_id: int):
    return api_get(f"accounts/{account_id}/events/{event_id}?$expand=AccessControl")

def get_contacts_by_group_ids_with_membership(account_id: int, group_ids: list):
    all_contacts = []
    top = 100
    skip = 0
    filter_query = " or ".join([f"GroupId eq {gid}" for gid in group_ids])
    encoded_filter = requests.utils.quote(filter_query, safe=" ").replace(" ", "%20")

    while True:
        endpoint = (
            f"/accounts/{account_id}/contacts"
            f"?$filter={encoded_filter}&$expand=MembershipLevel&$top={top}&$skip={skip}"
        )
        data = api_get(endpoint)
        page_contacts = data.get("Contacts", [])
        all_contacts.extend(page_contacts)
        if len(page_contacts) < top:
            break
        skip += top
    return all_contacts


def normalize_event_registrants(registrants: list) -> list:
    """
    Flatten Contact-level membership info into the top-level registrant dictionary.
    Specifically extracts MembershipLevel and Status.
    """
    normalized = []

    for reg in registrants:
        contact = reg.get("Contact", {})

        # Extract membership level
        membership = contact.get("MembershipLevel")
        if isinstance(membership, dict):
            reg["MembershipLevel"] = {
                "Id": membership.get("Id"),
                "Name": membership.get("Name")
            }
        else:
            reg["MembershipLevel"] = None

        # Extract contact status
        reg["Status"] = contact.get("Status", "Unknown")

        # You can flatten more fields here if needed

        normalized.append(reg)

    return normalized


def get_event_registrants(event_id: int) -> list:
    """
    Fetch registrants for a given event ID from Wild Apricot.
    No retries, no caching, no polling — just a direct GET request.

    Parameters:
    - event_id: Wild Apricot event ID

    Returns:
    - A list of registrant dictionaries
    """
    endpoint = f"eventregistrations?eventId={event_id}"
    response = api_get(endpoint)  # assumes api_get is defined elsewhere
    return response


def register_contact_to_event(contact_id: int, event_id: int, account_id: int, reg_type_id: int) -> dict:
    """
    Auto-register a contact to an event using a specified registration type.

    Parameters:
    - contact_id: Wild Apricot Contact ID
    - event_id: Wild Apricot Event ID
    - account_id: Wild Apricot Account ID
    - reg_type_id: Registration Type ID for the event

    Returns:
    - The JSON response from the API (the new registration object)
    """
    # Step 1: Validate that the registration type exists for the event (optional but safe)
    
    #event = api_get(f"accounts/{account_id}/events/{event_id}")
    #valid_ids = {rt["Id"] for rt in event.get("RegistrationTypes", [])}
    #if reg_type_id not in valid_ids:
    #    raise ValueError(f"Registration type ID {reg_type_id} not found in event {event_id}.")

    # Step 2: Construct registration payload
    payload = {
        "Contact": {"Id": contact_id},
        "Event": {"Id": event_id},
        "RegistrationTypeId": reg_type_id,
        "IsCheckedIn": False,
        "Status": "Confirmed"
    }
    logger.trace(f"Payload for registration: {json.dumps(payload, indent=2)}")

    # Step 3: POST to /eventregistrations
    url = "https://api.wildapricot.org/v2/eventregistrations"
    headers = get_headers()  # Assumes your Bearer token auth setup
    response = requests.post(url, headers=headers, json=payload)

    if response.status_code >= 400:
        raise RuntimeError(f"Registration failed: {response.status_code} {response.text}")

    return response.json()


def register_contacts_to_event(
    contact_ids: list,
    event_id: int,
    account_id: int,
    reg_type_id: int,
    delay: float = 0.5,
    max_retries: int = 3
) -> dict:
    """
    Register a list of contacts to an event, one by one, with retries and rate limiting.

    Returns:
    - A dict with 'success' and 'failed' lists of contact IDs.
    """
    logger.info(f"Starting registration of {len(contact_ids)} contacts...")

    success_ids = []
    failed_ids = []

    for i, contact_id in enumerate(contact_ids, start=1):
        success = False

        for attempt in range(1, max_retries + 1):
            try:
                register_contact_to_event(
                    contact_id=contact_id,
                    event_id=event_id,
                    account_id=account_id,
                    reg_type_id=reg_type_id
                )
                logger.debug(f"[{i}] Registered contact {contact_id} (attempt {attempt})")
                success = True
                break
            except Exception as e:
                logger.warning(f"[{i}] Attempt {attempt} failed for contact {contact_id}: {e}")
                time.sleep(delay)

        if success:
            success_ids.append(contact_id)
        else:
            failed_ids.append(contact_id)
            logger.error(f"[{i}] Gave up on contact {contact_id} after {max_retries} attempts.")

        time.sleep(delay)

    logger.info(f"Registration complete: {len(success_ids)} succeeded, {len(failed_ids)} failed.")
    return {"success": success_ids, "failed": failed_ids}

