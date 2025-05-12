# api.py

import os
import time
import json
import requests

from datetime import datetime
from pathlib import Path
from requests.auth import HTTPBasicAuth
from loguru import logger

from watools.core.config import config
from watools.core.paths import get_default_cache_dir

# In-memory token cache keyed by account_id
_token_cache = {}

def get_access_token(account_id=None):
    if account_id is None:
        account_id = config.account_id

    if account_id in _token_cache:
        token_info = _token_cache[account_id]
        if time.time() < token_info["expiry"]:
            return token_info["access_token"]

    account_config = config.config.get("accounts", {}).get(account_id,{})
    logger.debug( account_config )
    client_id = account_config.get("client_id")
    client_secret = account_config.get("client_secret")
    oauth_url = config.oauth_url

    if not client_id or not client_secret:
        raise ValueError(f"Missing client credentials for account_id: '{account_id}'.")

    data = {"grant_type": "client_credentials", "scope": "auto"}
    response = requests.post(
        oauth_url,
        data=data,
        auth=HTTPBasicAuth(client_id, client_secret),
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )

    if response.status_code == 200:
        token_data = response.json()
        access_token = token_data["access_token"]
        expiry = time.time() + token_data.get("expires_in", 1800) - 60
        _token_cache[account_id] = {"access_token": access_token, "expiry": expiry}
        return access_token
    else:
        raise RuntimeError(f"OAuth token request failed: {response.status_code} {response.text}")


def normalize_and_flatten_contacts(contacts):
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


def get_headers(account_id=None):
    return {
        "Authorization": f"Bearer {get_access_token(str(account_id))}",
        "Accept": "application/json",
        "Content-Type": "application/json"
    }

def api_get(endpoint, account_id=None):
    url = config.api_base_url + endpoint
    headers = get_headers(account_id)
    response = requests.get(url, headers=headers)
    logger.debug(f"GET {url}")
    if response.ok:
        return response.json()
    else:
        raise RuntimeError(f"GET {url} failed: {response.status_code} {response.text}")

def api_post(endpoint, payload, account_id=None):
    url = config.api_base_url + endpoint
    headers = get_headers(account_id)
    response = requests.post(url, headers=headers, json=payload)
    logger.debug(f"POST {url} with payload: {payload}")
    if response.ok:
        return response.json()
    else:
        raise RuntimeError(f"POST {url} failed: {response.status_code} {response.text}")

def get_account(account_id=None):
    if account_id is None:
        account_id = config.account_id
    response = api_get(f"accounts/{account_id}", account_id)
    contact_limit_info = response.get("ContactLimitInfo")
    # Centralize adding WATOOLS specific key-value pairs
    if contact_limit_info:
        response["wat_contact_limit_info"] = f"{contact_limit_info.get('CurrentContactsCount',0)}/{contact_limit_info.get('BillingPlanContactsLimit',0)}"
    else:
        response["wat_contact_limit_info"] = f"(missing)"
    return response

def get_accounts() -> list:
    account_ids = config.account_ids
    accounts = []
    if account_ids:
        for account_id in account_ids:
            accounts.append( get_account( account_id )  )
    return accounts

def add_new_event_fields( event ):
    dt = datetime.fromisoformat(event["StartDate"])
    # Add formatted keys
    event["wat_start_day"] = dt.strftime("%a")             # e.g., "Tue"
    event["wat_start_date"] = dt.strftime("%Y-%b-%d")      # e.g., "2025-Jun-24"
    if event.get("StartTimeSpecified"):
        event["wat_start_time"] = dt.strftime("%I:%M%p").lstrip("0").lower()
    else:
        event["wat_start_time"] = ""

    dt = datetime.fromisoformat(event["EndDate"])
    # Add formatted keys
    event["wat_end_day"] = dt.strftime("%a")             # e.g., "Tue"
    event["wat_end_date"] = dt.strftime("%Y-%b-%d")      # e.g., "2025-Jun-24"
    if event.get("EndTimeSpecified"):
        event["wat_end_time"] = dt.strftime("%I:%M%p").lstrip("0").lower()
    else:
        event["wat_end_time"] = ""

    confirmed = event.get("ConfirmedRegistrationsCount","-")
    limit = str(event.get("RegistrationsLimit","*"))
    limit = "*" if limit=="None" else limit
    event["wat_confirmed_and_limit"] = f"{confirmed}/{limit}"
    return event


def get_events(account_id=None):
    if account_id is None:
        account_id = config.account_id
    response = api_get(f"accounts/{account_id}/events", account_id)
    for event in response.get("Events"):

        add_new_event_fields( event )
        if 0:
            dt = datetime.fromisoformat(event["StartDate"])
            # Add formatted keys
            event["wat_start_day"] = dt.strftime("%a")             # e.g., "Tue"
            event["wat_start_date"] = dt.strftime("%Y-%b-%d")      # e.g., "2025-Jun-24"
            if event.get("StartTimeSpecified"):
                event["wat_start_time"] = dt.strftime("%I:%M%p").lstrip("0").lower()
            else:
                event["wat_start_time"] = ""

            dt = datetime.fromisoformat(event["EndDate"])
            # Add formatted keys
            event["wat_end_day"] = dt.strftime("%a")             # e.g., "Tue"
            event["wat_end_date"] = dt.strftime("%Y-%b-%d")      # e.g., "2025-Jun-24"
            if event.get("EndTimeSpecified"):
                event["wat_end_time"] = dt.strftime("%I:%M%p").lstrip("0").lower()
            else:
                event["wat_end_time"] = ""

            confirmed = event.get("ConfirmedRegistrationsCount","-")
            limit = str(event.get("RegistrationsLimit","*"))
            limit = "*" if limit=="None" else limit
            event["wat_confirmed_and_limit"] = f"{confirmed}/{limit}"
        
    return response

def get_event_details(event_id, account_id=None):
    if account_id is None:
        account_id = config.account_id
    response = api_get(f"accounts/{account_id}/events/{event_id}?$expand=AccessControl", account_id)
    add_new_event_fields( response )
    return response


def get_default_membership_level_ids(account_id=None):
    if account_id is None:
        account_id = config.account_id
    levels = api_get(f"accounts/{account_id}/membershiplevels", account_id)
    return [level["Id"] for level in levels]

def get_membergroups(account_id=None):
    if account_id is None:
        account_id = config.account_id
    return api_get(f"accounts/{account_id}/membergroups", account_id)

def get_default_membergroup_ids(account_id=None):
    if account_id is None:
        account_id = config.account_id
    groups = api_get(f"accounts/{account_id}/membergroups", account_id)
    return [group["Id"] for group in groups]

def get_contacts_xxx(account_id=None, exclude_archived=True, max_wait=10, normalize_contacts=True, use_cache=True, reload=False):
    if account_id is None:
        account_id = config.account_id

    cache_file = get_default_cache_dir() / f"contacts-{account_id}.json"
    logger.debug(f"cache file: {cache_file}")

    if not reload:
        if use_cache and cache_file.exists():
            age = time.time() - cache_file.stat().st_mtime
            if age < config.cache_expiry_seconds:
                with open(cache_file, "r", encoding="utf-8") as f:
                    logger.debug("Loaded contacts from cache.")
                    contacts = json.load(f)
                    return normalize_and_flatten_contacts(contacts) if normalize_contacts else contacts

    query_parts = []
    if exclude_archived:
        query_parts.append("$filter=IsArchived eq false")
        query_parts.append("$select=*")

    endpoint = f"accounts/{account_id}/contacts"
    if query_parts:
        endpoint += "?" + "&".join(query_parts)

    response = api_get(endpoint, account_id)
    logger.debug( json.dumps(response,indent=2) )


    if "ResultUrl" in response:
        result_url = response["ResultUrl"].replace(config.api_base_url, "")
        state = response.get("State")
        attempts = 0
        while state != "Complete" and attempts < max_wait:
            time.sleep(1.5)
            response = api_get(result_url, account_id)
            state = response.get("State")
            attempts += 1
        contacts = response.get("Contacts", [])
    else:
        contacts = response.get("Contacts", [])

    if use_cache and contacts:
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(contacts, f)
            logger.debug("Contacts saved to cache.")

    return normalize_and_flatten_contacts(contacts) if normalize_contacts else contacts


def api_get_result_url(initial_url: str, account_id: int = None, max_wait: int = 10, sleep_seconds: float = 1.5) -> dict:
    """
    Perform a Wild Apricot API GET request that may return a ResultUrl and require polling.

    Parameters:
        initial_url (str): The full API endpoint (relative, like 'accounts/12345/contacts?...')
        account_id (int): Optional account ID
        max_wait (int): Maximum polling attempts (sleep_seconds * max_wait = total wait time)
        sleep_seconds (float): Delay between polling attempts

    Returns:
        dict: Final parsed JSON response after async processing (includes 'Contacts' or 'EventRegistrations')
    """
    base_url = config.api_base_url
    full_url = base_url + initial_url
    headers = get_headers(account_id)

    logger.debug(f"Initial request to {full_url}")
    response = requests.get(full_url, headers=headers)
    logger.debug(f"Response status: {response.status_code}")

    if not response.ok:
        raise RuntimeError(f"GET {full_url} failed: {response.status_code} {response.text}")

    data = response.json()
    logger.debug(json.dumps(data, indent=2))

    # If asynchronous result is returned
    result_url = data.get("ResultUrl")
    if result_url:
        logger.debug("ResultUrl detected. Sleeping before polling...")
        time.sleep(sleep_seconds)

        state = data.get("State", "")
        attempts = 0
        while state != "Complete" and attempts < max_wait:
            logger.debug(f"Polling attempt {attempts + 1}: {result_url}")
            poll_response = requests.get(result_url, headers=headers)
            data = poll_response.json()
            logger.debug(json.dumps(data, indent=2))

            state = data.get("State", "")
            attempts += 1
            if state != "Complete":
                time.sleep(sleep_seconds)

        if state != "Complete":
            raise TimeoutError(f"Polling timed out after {max_wait} attempts: {result_url}")

    return data

def get_contactsxx(account_id=None, exclude_archived=True, max_wait=10, normalize_contacts=True, use_cache=True, reload=False):
    if account_id is None:
        account_id = config.account_id

    cache_file = get_default_cache_dir() / f"contacts-{account_id}.json"
    logger.debug(f"cache file: {cache_file}")

    if not reload:
        if use_cache and cache_file.exists():
            age = time.time() - cache_file.stat().st_mtime
            if age < config.cache_expiry_seconds:
                with open(cache_file, "r", encoding="utf-8") as f:
                    logger.debug("Loaded contacts from cache.")
                    contacts = json.load(f)
                    return normalize_and_flatten_contacts(contacts) if normalize_contacts else contacts

    # Build query
    query_parts = []
    if exclude_archived:
        query_parts.append("$filter=IsArchived eq false")
        query_parts.append("$select=*")

    query_parts.append("$orderby=Id")

    endpoint = f"accounts/{account_id}/contacts"
    if query_parts:
        endpoint += "?" + "&".join(query_parts)

    response = api_get(endpoint, account_id)
    logger.debug("Initial ResultUrl received. Sleeping 1.5 seconds before polling.")
    time.sleep(1.5)

    # If async ResultUrl is provided
    if "ResultUrl" in response:
        result_url = response["ResultUrl"]
        state = response.get("State")
        attempts = 0
        while state != "Complete" and attempts < max_wait:
            logger.debug(f"Waiting for results... attempt {attempts+1}")
            time.sleep(1.5)
            check_response = requests.get(result_url, headers=get_headers(account_id))
            state = check_response.json().get("State")
            response = check_response.json()
            attempts += 1

        contacts = response.get("Contacts", [])
    else:
        contacts = response.get("Contacts", [])

    if use_cache and contacts:
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(contacts, f)
            logger.debug("Contacts saved to cache.")

    return normalize_and_flatten_contacts(contacts) if normalize_contacts else contacts

def get_contacts(account_id=None, exclude_archived=True, max_wait=10, normalize_contacts=True, use_cache=True, reload=False):
    if account_id is None:
        account_id = config.account_id

    # Build cache path
    cache_file = get_default_cache_dir() / f"contacts-{account_id}.json"
    logger.debug(f"cache file: {cache_file}")

    # Load from cache if allowed
    if not reload and use_cache and cache_file.exists():
        age = time.time() - cache_file.stat().st_mtime
        if age < config.cache_expiry_seconds:
            with open(cache_file, "r", encoding="utf-8") as f:
                logger.debug("Loaded contacts from cache.")
                contacts = json.load(f)
                return normalize_and_flatten_contacts(contacts) if normalize_contacts else contacts

    # Build query
    query_parts = []
    if exclude_archived:
        query_parts.append("$filter=IsArchived eq false")
    query_parts.append("$select=*")
    query_parts.append("$orderby=Id")  # prevent WA result caching

    endpoint = f"accounts/{account_id}/contacts?" + "&".join(query_parts)

    # Fetch from Wild Apricot (handles async ResultUrl)
    response = api_get_result_url(endpoint, account_id=account_id, max_wait=max_wait)

    contacts = response.get("Contacts", [])
    if use_cache and contacts:
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(contacts, f)
            logger.debug("Contacts saved to cache.")

    return normalize_and_flatten_contacts(contacts) if normalize_contacts else contacts


def get_event_registrants(event_id, account_id=None):
    if account_id is None:
        account_id = config.account_id
    endpoint = f"eventregistrations?eventId={event_id}"
    return api_get(endpoint, account_id)

def register_contact_to_event(contact_id, event_id, reg_type_id, account_id=None):
    if account_id is None:
        account_id = config.account_id

    payload = {
        "Contact": {"Id": contact_id},
        "Event": {"Id": event_id},
        "RegistrationTypeId": reg_type_id,
        "IsCheckedIn": False,
        "Status": "Confirmed"
    }
    logger.trace(f"Payload for registration: {json.dumps(payload, indent=2)}")
    return api_post("eventregistrations", payload, account_id)

def register_contacts_to_event(contact_ids, event_id, reg_type_id, delay=0.5, max_retries=3, account_id=None):
    if account_id is None:
        account_id = config.account_id

    logger.info(f"Starting registration of {len(contact_ids)} contacts...")
    success_ids = []
    failed_ids = []

    for i, contact_id in enumerate(contact_ids, start=1):
        success = False
        for attempt in range(1, max_retries + 1):
            try:
                register_contact_to_event(contact_id, event_id, reg_type_id, account_id)
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
