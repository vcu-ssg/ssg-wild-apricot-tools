"""
"""
import os
import time
import json
import requests
from dotenv import load_dotenv
from loguru import logger
from requests.auth import HTTPBasicAuth

# Load .env variables
load_dotenv()

# Credentials from .env
CLIENT_ID = os.getenv("WILD_APRICOT_CLIENT_ID")
CLIENT_SECRET = os.getenv("WILD_APRICOT_CLIENT_SECRET")
OAUTH_URL = "https://oauth.wildapricot.org/auth/token"
API_BASE_URL = "https://api.wildapricot.org/v2/"

# Cache token in memory
_access_token = None
_token_expiry = None

def get_access_token():
    """Fetch a new OAuth access token if needed (client_credentials flow)."""
    global _access_token, _token_expiry

    if _access_token and _token_expiry and time.time() < _token_expiry:
        return _access_token

    if not CLIENT_ID or not CLIENT_SECRET:
        raise ValueError("Missing WILD_APRICOT_CLIENT_ID or WILD_APRICOT_CLIENT_SECRET in .env file")

    data = {
        "grant_type": "client_credentials",
        "scope": "auto"
    }

    response = requests.post(
        OAUTH_URL,
        data=data,
        auth=HTTPBasicAuth(CLIENT_ID, CLIENT_SECRET),
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )

    if response.status_code == 200:
        token_info = response.json()
        _access_token = token_info["access_token"]
        _token_expiry = time.time() + token_info.get("expires_in", 1800) - 60  # refresh 1 min early
        return _access_token
    else:
        raise RuntimeError(f"OAuth token request failed: {response.status_code} {response.text}")

def get_headers():
    """Return headers for Wild Apricot API requests with Bearer token."""
    return {
        "Authorization": f"Bearer {get_access_token()}",
        "Accept": "application/json",
        "Content-Type": "application/json"
    }

def api_get(endpoint):
    """Generic GET request."""
    url = API_BASE_URL + endpoint
    headers = get_headers()
    response = requests.get(url, headers=headers)
    logger.debug( url )
    if response.ok:
        return response.json()
    else:
        raise RuntimeError(f"GET {url} failed: {response.status_code} {response.text}")
    
def api_get_following_redirect(endpoint):
    """Handles both direct and async (ResultUrl) responses."""
    data = api_get(endpoint)

    # If it's an async response with a ResultUrl
    if "ResultUrl" in data and "State" in data and data["State"] == "Complete":
        return api_get(data["ResultUrl"].replace("https://api.wildapricot.org/v2/", ""))

    return data



def get_accounts():
    """Public method to retrieve Wild Apricot account info."""
    return api_get("accounts")

def get_membergroups( account_id: int ) -> dict:
    """Public method to retrieve Wild Apricot membergroup info."""
    return api_get(f"accounts/{account_id}/membergroups")

def get_events( account_id:int ) -> dict:
    """Retrieve the list of events from the Wild Apricot API."""
    if not account_id:
        raise ValueError("Account ID is required to fetch events.")
    return api_get(f"accounts/{account_id}/events")


def get_contacts(account_id: int, exclude_archived: bool = True) -> list:
    """
    Retrieve all contacts for the given Wild Apricot account ID,
    handling pagination and async ResultUrl responses.

    Parameters:
        account_id (int): Wild Apricot account ID
        exclude_archived (bool): If True, exclude archived contacts

    Returns:
        list of dict: All contact records
    """
    all_contacts = []
    top = 100
    skip = 0

    while True:
        # Construct filter query
        filters = []
        if exclude_archived:
            filters.append("IsArchived eq false")
        filter_part = "&$filter=" + " and ".join(filters) if filters else ""
        
        # Build full endpoint
        endpoint = (
            f"/accounts/{account_id}/contacts?$top={top}&$skip={skip}{filter_part}"
        )

        # Call API
        data = api_get(endpoint)

        # Handle async result
        if "ResultUrl" in data:
            result_url = data["ResultUrl"].replace("https://api.wildapricot.org/v2", "")
            data = api_get(result_url)

        # Process contacts
        page_contacts = data.get("Contacts", [])
        all_contacts.extend(page_contacts)

        # Break if no more pages
        if len(page_contacts) < top:
            break

        skip += top

    return all_contacts



def get_event_details( account_id:int, event_id:int ) -> dict:
    """Retrieve the list of events from the Wild Apricot API."""
    if not account_id:
        raise ValueError("Account ID is required to fetch events.")
    return api_get(f"accounts/{account_id}/events/{event_id}?$expand=AccessControl")


def get_contacts_by_group_ids_with_membership(account_id:int, group_ids:list ) -> dict:
    """
    Fetch contacts who belong to any of the given member group IDs,
    including their membership level, using the api_get helper.

    Parameters:
        group_ids (list of int): Member group IDs to query.
        account_id (int): Your Wild Apricot account ID.

    Returns:
        list of dict: Contacts with membership level info.
    """
    all_contacts = []
    top = 100
    skip = 0

    # Build $filter condition
    filter_query = " or ".join([f"GroupId eq {gid}" for gid in group_ids])
    encoded_filter = requests.utils.quote(filter_query, safe=" ")
    encoded_filter = encoded_filter.replace(" ", "%20")

    while True:
        endpoint = (
            f"/accounts/{account_id}/contacts"
            f"?$filter={encoded_filter}"
            f"&$expand=MembershipLevel"
            f"&$top={top}&$skip={skip}"
        )

        data = api_get(endpoint)
        page_contacts = data.get("Contacts", [])
        all_contacts.extend(page_contacts)

        if len(page_contacts) < top:
            break  # No more pages

        skip += top

    return all_contacts
