import os
import inspect
import argparse
from pathlib import Path
from tomlkit import parse
from loguru import logger

APP_NAME = "watools"

class WatoolsConfig:
    def __init__(self):
        self._raw_config = None
        self._config_dir = None
        self._account_id = None
        self._cache_dir = None

    def _get_config_dir(self) -> Path:
        if self._config_dir:
            return self._config_dir

        env_path = os.getenv("WATOOLS_CONFIG_DIR")
        if env_path:
            self._config_dir = Path(env_path).expanduser()
        else:
            local_path = Path(__file__).resolve().parent.parent / "config"
            self._config_dir = local_path if local_path.exists() else Path(
                os.getenv("XDG_CONFIG_HOME", Path.home() / ".config")
            ) / APP_NAME

        self._config_dir.mkdir(parents=True, exist_ok=True)
        return self._config_dir
    
    def get_cache_dir(self) -> Path:
        """Get the cache directory according to the XDG specification."""
        if self._cache_dir:
            return self._cache_dir
        
        env_path = os.getenv("WATOOLS_CACHE_DIR")
        if env_path:
            self._cache_dir = Path(env_path).expanduser()
        else:
            local_path = Path(__file__).resolve().parent.parent / ".cache"
            self._cache_dir = local_path if local_path.exists() else Path(
                os.getenv("XDG_CONFIG_HOME", Path.home() / ".cache")
            ) / APP_NAME

        self._cache_dir.mkdir(parents=True, exist_ok=True)
        return self._cache_dir


    def _load_toml_file(self, path: Path):
        if not path.exists():
            raise FileNotFoundError(f"Missing TOML file: {path}")
        return parse(path.read_text())

    def _merge_configs(self, config, credentials):
        accounts = config.get("accounts", {})
        cred_accounts = credentials.get("accounts", {})
        for acc_id, creds in cred_accounts.items():
            accounts.setdefault(acc_id, {}).update(creds)
        config["accounts"] = accounts
        return config

    def _peek_account_id(self):
        parser = argparse.ArgumentParser(add_help=False)
        parser.add_argument("--account-id")
        args, _ = parser.parse_known_args()
        return args.account_id

    def _validate_log_level(self, value: str) -> str:
        valid = {"TRACE", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        value = str(value).upper()
        if value not in valid:
            raise ValueError(f"Invalid log_level '{value}'. Must be one of: {', '.join(valid)}.")
        return value

    def _ensure_loaded(self):
        if self._raw_config is None:
            raise RuntimeError("WatoolsConfig has not been loaded. Call `config.load()` first.")

    def load(self):
        if self._raw_config is not None:
            return

        config_dir = self._get_config_dir()
        config = self._load_toml_file(config_dir / "config.toml")
        credentials = self._load_toml_file(config_dir / "credentials.toml")
        merged = self._merge_configs(config, credentials)

        account_id = (
            self._peek_account_id() or
            merged.get("account_id")
        )

        if not account_id:
            raise ValueError(f"No account_id provided and no account_id set in {config_dir}/config.toml")
        if not isinstance(account_id, str):
            raise TypeError(f"account_id must be a quoted string like \"201263\"")

        if account_id not in merged.get("accounts", {}):
            raise KeyError(f"Account ID '{account_id}' not found in [accounts] section of {config_dir}/config.toml")

        self._raw_config = merged
        self._account_id = account_id

    def validate(self):
        self._ensure_loaded()
        account = self.account
        required = ["client_id", "client_secret"]
        optional = []

        logger.trace(f"Account block:\n{account}")

        missing = [k for k in required if k not in account]
        if missing:
            raise ValueError(f"Missing required keys for account '{self._account_id}': {', '.join(missing)}")

        for key in optional:
            if key not in account:
                logger.warning(f"Optional key '{key}' not set for account {self._account_id}")

    def list_properties(self) -> dict:
        """Return a dictionary of public property names and their values."""
        self._ensure_loaded()
        props = inspect.getmembers(type(self), lambda o: isinstance(o, property))
        result = {}
        for name, _ in props:
            if name.startswith("_"):
                continue  # Skip internal/private properties
            try:
                result[name] = getattr(self, name)
            except Exception as e:
                result[name] = f"<error: {e}>"
        return result

    def __getitem__(self, key):
        self._ensure_loaded()
        return self._raw_config.get(key)

    def __contains__(self, key):
        self._ensure_loaded()
        return key in self._raw_config

    def __iter__(self):
        self._ensure_loaded()
        return iter(self._raw_config)

    @property
    def config(self):
        self._ensure_loaded()
        return self._raw_config

    @property
    def config_dir(self) -> Path:
        return self._get_config_dir()

    @property
    def account_id(self) -> str:
        self._ensure_loaded()
        return self._account_id

    @property
    def account(self) -> dict:
        self._ensure_loaded()
        return self._raw_config["accounts"][self._account_id]

    @property
    def log_level(self) -> str:
        self._ensure_loaded()
        return self._validate_log_level(self._raw_config.get("log_level", "INFO"))

    @property
    def is_loaded(self):
        return self._raw_config is not None
    
    @property
    def client_id( self ) ->str:
        self._ensure_loaded()
        return self.account.get("client_id")

    @property
    def client_secret( self ) -> str:
        self._ensure_loaded()
        return self.account.get("client_secret")

    @property
    def oauth_url( self ) -> str:
        self._ensure_loaded()
        return self._raw_config.get("api",{}).get("oauth_url")

    @property
    def api_base_url( self ) -> str:
        self._ensure_loaded()
        return self._raw_config.get("api",{}).get("api_base_url")
    
    @property
    def contacts_cache_file( self ) -> str:
        self._ensure_loaded()
        filename = self._raw_config.get("cache",{}).get("contacts_cache_file","contacts.json")
        filename = self.get_cache_dir() / filename
        logger.debug(f"cache file: {filename}")
        return filename
    
    @property
    def cache_expiry_seconds( self ) -> str:
        self._ensure_loaded()
        return self._raw_config.get("cache",{}).get("cache_expiry_seconds",3600)

# Global singleton instance
config = WatoolsConfig()
