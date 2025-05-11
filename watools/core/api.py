# api.py

import os
import time
import json
import requests
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

    account_config = config.config.get("accounts", {}).get(account_id, {})
    client_id = account_config.get("client_id")
    client_secret = account_config.get("client_secret")
    oauth_url = config.oauth_url

    if not client_id or not client_secret:
        raise ValueError(f"Missing client credentials for account_id '{account_id}'.")

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

def get_headers(account_id=None):
    return {
        "Authorization": f"Bearer {get_access_token(account_id)}",
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
    return api_get(f"accounts/{account_id}", account_id)

def get_accounts() -> list:
    account_ids = config.account_ids
    accounts = []
    if account_ids:
        for account_id in account_ids:
            accounts.append( get_account( account_id )  )
    return accounts

def get_events(account_id=None):
    if account_id is None:
        account_id = config.account_id
    return api_get(f"accounts/{account_id}/events", account_id)

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

def get_contacts(account_id=None, exclude_archived=True, max_wait=10, normalize_contacts=True, use_cache=True, reload=False):
    if account_id is None:
        account_id = config.account_id

    cache_file = get_default_cache_dir() / f"contacts-{account_id}.json"
    if use_cache and not reload and cache_file.exists():
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

def get_event_details(event_id, account_id=None):
    if account_id is None:
        account_id = config.account_id
    return api_get(f"accounts/{account_id}/events/{event_id}?$expand=AccessControl", account_id)

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
