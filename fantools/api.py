"""
"""
import os
import ssl
import time
import json
import socket
import requests
from pathlib import Path
from loguru import logger
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv


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


TLS_TEST_URL = API_BASE_URL+"accounts"  # public endpoint that uses valid cert

def check_tls(timeout: int = 5):
    """
    Perform a simple unauthenticated GET request to validate TLS.
    Does not require OAuth or credentials.
    """
    try:
        response = requests.get(TLS_TEST_URL, timeout=timeout)
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

1. Copy the certificate (e.g., `wildapricot-ca.crt`) into your trusted store:

   sudo cp wildapricot-ca.crt /usr/local/share/ca-certificates/
   sudo update-ca-certificates

2. Restart your WSL session or Linux shell.

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

        root_cert = certs[-1]  # Assume last in chain is root
        Path(output_file).write_text(root_cert)
        print(f"✅ Root certificate written to: {output_file}")
        return output_file

    except subprocess.TimeoutExpired:
        raise RuntimeError("openssl command timed out")
    except Exception as e:
        raise RuntimeError(f"Failed to extract root certificate: {e}")

