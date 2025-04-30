import os
import time
import requests
from dotenv import load_dotenv
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
        raise ValueError("Missing WA_CLIENT_ID or WA_CLIENT_SECRET in .env file")

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

    if response.ok:
        return response.json()
    else:
        raise RuntimeError(f"GET {url} failed: {response.status_code} {response.text}")

def get_account_details():
    """Public method to retrieve Wild Apricot account info."""
    return api_get("accounts")


def get_events() -> dict:
    """Retrieve the list of events from the Wild Apricot API."""
    from .api import get_access_token  # or adjust import if needed

    # Load account ID from environment
    load_dotenv()
    account_id = os.getenv("WILD_APRICOT_ACCOUNT_ID")
    if not account_id:
        raise RuntimeError("WILD_APRICOT_ACCOUNT_ID is not set in .env")

    # Get token
    access_token = get_access_token()

    # Build request
    url = f"https://api.wildapricot.org/v2.2/accounts/{account_id}/events"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json"
    }

    response = requests.get(url, headers=headers)
    response.raise_for_status()

    return response.json()


def get_event_registration_types(event_id: int) -> list:
    """Return a list of registration types (IDs and names) for a given event."""
    load_dotenv()
    account_id = os.getenv("WILD_APRICOT_ACCOUNT_ID")
    if not account_id:
        raise RuntimeError("WILD_APRICOT_ACCOUNT_ID is not set in .env")

    access_token = get_access_token()

    url = f"https://api.wildapricot.org/v2.2/accounts/{account_id}/events/{event_id}"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json"
    }

    response = requests.get(url, headers=headers)
    response.raise_for_status()

    event_details = response.json()
    return event_details
    #return event_details.get("RegistrationTypes", [])