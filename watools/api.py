"""
"""
import os
import ssl
import time
import json
import click
import socket
import requests
from pathlib import Path
from loguru import logger
from requests.auth import HTTPBasicAuth

from watools.config import config


# Credentials from .env
#CLIENT_ID = os.getenv("WILD_APRICOT_CLIENT_ID")
#CLIENT_SECRET = os.getenv("WILD_APRICOT_CLIENT_SECRET")

#API_BASE_URL = "https://api.wildapricot.org/v2.2/"

# Cache token in memory

_access_token = None
_token_expiry = "None"


#TLS_TEST_URL = API_BASE_URL+"accounts"  # public endpoint that uses valid cert

# Cache file for contacts
CACHE_FILE = Path(".cache/contacts.json")
CACHE_EXPIRY_SECONDS = 3600  # 1 hour

#CACHE_FILENAME = "contacts.json"
#CACHE_EXPIRY_SECONDS = 3600  # 1 hour

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
    """
    Perform a simple unauthenticated GET request to validate TLS.
    Does not require OAuth or credentials.
    """
    try:
        response = requests.get(config.api_base_url+"accounts", timeout=timeout )
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
    """Fetch a new OAuth access token if needed (client_credentials flow)."""
    global _access_token, _token_expiry

    CLIENT_ID = config.client_id
    CLIENT_SECRET = config.client_secret
    OAUTH_URL = config.oauth_url

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
    url = config.api_base_url + endpoint
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
        return api_get(data["ResultUrl"].replace(config.api_base_url, ""))

    return data


def get_accounts():
    """Public method to retrieve Wild Apricot account info."""
    return api_get("accounts")

def get_events( account_id:int ) -> dict:
    """Retrieve the list of events from the Wild Apricot API."""
    if not account_id:
        raise ValueError("Account ID is required to fetch events.")
    return api_get(f"accounts/{account_id}/events")

def get_default_membership_level_ids(account_id: int) -> list:
    """
    Retrieve all membership levels for a given Wild Apricot account.
    """
    endpoint = f"accounts/{account_id}/membershiplevels"
    response = api_get(endpoint)  # assumes api_get handles auth and base URL
    levels = response

    return [level["Id"] for level in levels]

def get_membergroups( account_id: int ) -> dict:
    """Public method to retrieve Wild Apricot membergroup info."""
    response = api_get(f"accounts/{account_id}/membergroups")
    return response

def get_default_membergroup_ids( account_id: int ) -> dict:
    """Public method to retrieve Wild Apricot membergroup info."""
    response = api_get(f"accounts/{account_id}/membergroups")
    return [ group["Id"] for group in response]

def normalize_and_flatten_contacts(contacts: list) -> list:
    """
    Normalize and flatten contact records.
    Adds 'MembershipLevelId' and 'MembershipLevelName' fields.
    """
    all_keys = set()
    flattened = []

    for contact in contacts:
        all_keys.update(contact.keys())

    for contact in contacts:
        flat_contact = {key: contact.get(key, None) for key in all_keys}

        membership_level = contact.get("MembershipLevel")
        if isinstance(membership_level, dict):
            flat_contact["MembershipLevelId"] = membership_level.get("Id")
            flat_contact["MembershipLevelName"] = membership_level.get("Name")
        else:
            flat_contact["MembershipLevelId"] = None
            flat_contact["MembershipLevelName"] = None

        flattened.append(flat_contact)

    logger.debug( f"Normalized and flattened {len(flattened)} contacts.", fg="blue")
    return flattened

def get_contacts(account_id: int, exclude_archived: bool = True, max_wait: int = 10, normalize_contacts: bool = True, use_cache: bool = True, reload: bool = False) -> list:
    """
    Retrieve all contacts from Wild Apricot, optionally using a cache.
    Handles report-style filtered queries and optional normalization.
    """
    if use_cache:
        cached = load_contacts_cache( reload )
        if cached:
            logger.debug("Loaded contacts from local cache.")
            return normalize_and_flatten_contacts(cached) if normalize_contacts else cached

    query_parts = []
    if exclude_archived:
        query_parts.append("$filter=IsArchived eq false")
        query_parts.append("$select=*")  # Force full results

    endpoint = f"accounts/{account_id}/contacts"
    if query_parts:
        endpoint += "?" + "&".join(query_parts)

    response = api_get(endpoint)

    if "ResultUrl" in response:
        result_url = response["ResultUrl"].replace(config.api_base_url, "")
        state = response.get("State")
        attempts = 0

        while state != "Complete" and attempts < max_wait:
            logger.debug(f"Waiting for report to complete (attempt {attempts + 1})...")
            time.sleep(1.5)
            response = api_get(result_url)
            state = response.get("State", "Complete")
            attempts += 1

        for retry in range(2):
            contacts = response.get("Contacts", [])
            if contacts:
                break
            logger.debug(f"Report returned no contacts on attempt {retry + 1}, retrying...")
            time.sleep(1.0)
            response = api_get(result_url)
        else:
            contacts = []
    else:
        contacts = response.get("Contacts", [])

    if not contacts:
        logger.warning("No contacts were returned from the API.")
    else:
        logger.debug(f"Retrieved {len(contacts)} contacts from API.")

    if use_cache and contacts:
        save_contacts_cache(contacts)
        logger.debug("Saved contacts to local cache.")

    return normalize_and_flatten_contacts(contacts) if normalize_contacts else contacts


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

import platform

def fix_tls_error_instructions():
    os_name = platform.system()
    is_wsl = "microsoft" in platform.release().lower() or "wsl" in platform.version().lower()

    if os_name == "Windows" and not is_wsl:
        return """You're on Windows. To fix the TLS certificate error:

1. Open PowerShell as Administrator.
2. Run the following command to import the certificate (adjust the path):

   Import-Certificate -FilePath "C:\\path\\to\\certificate.crt" -CertStoreLocation Cert:\\LocalMachine\\Root

3. Restart your terminal or computer.

Make sure you're importing the **correct** CA certificate used by Wild Apricot.
"""

    elif is_wsl or (os_name == "Linux"):
        return """You're using WSL or native Linux. To fix the TLS certificate error:

1. Rerun program with --write-certs option.

2. Copy the certificate (e.g., `wildapricot-ca.crt`) into your trusted store:

   sudo cp wildapricot-ca.crt /usr/local/share/ca-certificates/
   sudo update-ca-certificates

3. Restart your WSL session or Linux shell.

Make sure you're using the correct certificate and that `ca-certificates` is installed.
"""

    elif os_name == "Darwin":
        return """You're on macOS. To fix the TLS certificate error:

1. Open the Keychain Access application.
2. Drag and drop the certificate into the **System** keychain.
3. Double-click the certificate and set "When using this certificate" to **Always Trust**.
4. Close and save changes, then restart your terminal.

Make sure you're importing the **correct** CA certificate from Wild Apricot.
"""

    else:
        return "Unsupported OS. Please manually install and trust the CA certificate for your system."


def extract_tls_cert_to_file(hostname="oauth.wildapricot.org", port=443, output_path="wildapricot-ca.crt"):
    """
    Fetch the TLS certificate from the given host:port, skipping verification,
    and save it to a .crt PEM file. Useful behind MITM proxies like Zscaler.
    """
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE  

    with socket.create_connection((hostname, port)) as sock:
        with context.wrap_socket(sock, server_hostname=hostname) as ssock:
            der_cert = ssock.getpeercert(binary_form=True)
            pem_cert = ssl.DER_cert_to_PEM_cert(der_cert)

    path = Path(output_path)
    path.write_text(pem_cert)
    return str(path.resolve())

import subprocess
from pathlib import Path

def extract_zscaler_root_cert(host="oauth.wildapricot.org", port=443, output_file="zscaler-root-ca.crt"):
    """
    Uses openssl to fetch the full certificate chain, extracts the last certificate (assumed root),
    and writes it to a PEM file.
    """
    try:
        # Run openssl s_client to fetch cert chain
        result = subprocess.run(
            ["openssl", "s_client", "-showcerts", "-connect", f"{host}:{port}"],
            input="\n", capture_output=True, text=True, timeout=10

        )
        output = result.stdout

        # Extract all certs
        certs = []
        current_cert = []
        for line in output.splitlines():
            if "BEGIN CERTIFICATE" in line:
                current_cert = [line]
            elif "END CERTIFICATE" in line:
                current_cert.append(line)
                certs.append("\n".join(current_cert))
                current_cert = []
            elif current_cert:
                current_cert.append(line)

        if not certs:
            raise RuntimeError("No certificates found in output.")

        root_cert = certs[-2]  # Assume last in chain is root
        Path(output_file).write_text(root_cert)
        print(f"✅ Root certificate written to: {output_file}")
        return output_file

    except subprocess.TimeoutExpired:
        raise RuntimeError("openssl command timed out")
    except Exception as e:
        raise RuntimeError(f"Failed to extract root certificate: {e}")

import subprocess
from pathlib import Path
import certifi
import shutil

import subprocess
from pathlib import Path
import os
import shutil
import certifi


import subprocess
from pathlib import Path
import os
import shutil
import certifi


def write_combined_cert_bundle(
    host="oauth.wildapricot.org",
    port=443,
    local_crt_file="zscaler-intermediate.crt"
) -> str:
    """
    Appends the Zscaler intermediate cert to the CA bundle (from REQUESTS_CA_BUNDLE or certifi),
    backs up the original bundle, and saves the intermediate cert locally as well.
    """
    try:
        # Fetch the cert chain from the remote host
        result = subprocess.run(
            ["openssl", "s_client", "-showcerts", "-connect", f"{host}:{port}"],
            input="\n",
            capture_output=True,
            text=True,
            timeout=10,
        )
        output = result.stdout

        # Extract certs from the openssl output
        certs = []
        current_cert = []
        for line in output.splitlines():
            if "BEGIN CERTIFICATE" in line:
                current_cert = [line]
            elif "END CERTIFICATE" in line:
                current_cert.append(line)
                certs.append("\n".join(current_cert))
                current_cert = []
            elif current_cert:
                current_cert.append(line)

        if len(certs) < 2:
            raise RuntimeError("Fewer than 2 certificates found in the chain.")

        zscaler_cert = certs[-2]

        # Save the Zscaler cert as its own file
        local_crt_path = Path(local_crt_file)
        local_crt_path.write_text(zscaler_cert)

        # Determine which bundle to modify
        bundle_path = Path(os.getenv("REQUESTS_CA_BUNDLE", certifi.where())).resolve()
        backup_path = bundle_path.with_suffix(".pem.backup")

        # Backup and append cert
        shutil.copy(bundle_path, backup_path)
        with open(bundle_path, "a") as f:
            f.write("\n")
            f.write(zscaler_cert)

        return str(bundle_path)

    except subprocess.TimeoutExpired:
        raise RuntimeError("OpenSSL command timed out")
    except Exception as e:
        raise RuntimeError(f"Failed to write combined cert bundle: {e}")
    

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

