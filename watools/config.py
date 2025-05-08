import os
import json
import argparse
from pathlib import Path

from tomlkit import parse

from loguru import logger

APP_NAME = "watools"

class WatoolsConfig:
    def __init__(self):
        self._config = None
        self._account_id = None
        self._account_data = None
        self._config_dir = None
        self._log_level = None

    def _get_config_dir(self) -> Path:
        if self._config_dir:
            return self._config_dir  # Already determined

        # 1. Environment override
        env_path = os.getenv("WATOOLS_CONFIG_DIR")
        if env_path:
            self._config_dir = Path(env_path).expanduser()
            return self._config_dir

        # 2. Local ./config folder
        local_path = Path(__file__).resolve().parent.parent / "config"
        if local_path.exists():
            self._config_dir = local_path
            return self._config_dir

        # 3. Fallback to XDG
        xdg_base = os.getenv("XDG_CONFIG_HOME", Path.home() / ".config")
        self._config_dir = Path(xdg_base) / APP_NAME
        return self._config_dir

    def _load_toml_file(self, path: Path):
        if not path.exists():
            raise FileNotFoundError(f"Missing TOML file: {path}")
        return parse(path.read_text())

    def _merge_configs(self, config, credentials):
        accounts = config.get("accounts", {})
        cred_accounts = credentials.get("accounts", {})

        for acc_id, creds in cred_accounts.items():
            if acc_id not in accounts:
                accounts[acc_id] = {}
            accounts[acc_id].update(creds)

        config["accounts"] = accounts
        return config

    def _peek_account_id(self):
        parser = argparse.ArgumentParser(add_help=False)
        parser.add_argument("--account-id")
        args, _ = parser.parse_known_args()
        return args.account_id

    def _validate_log_level(self, value: str) -> str:
        valid_levels = {"TRACE", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        value = str(value).upper()
        if value not in valid_levels:
            raise ValueError(
                f"Invalid log_level '{value}'. Must be one of: {', '.join(valid_levels)}."
            )
        return value

    def _ensure_loaded(self):
        if self._config is None:
            raise RuntimeError("WatoolsConfig has not been loaded. Call `config.load()` first.")

    def load(self):
        """Load and merge configuration files, select account."""
        if self._config is not None:
            return  # already loaded

        config_dir = self._get_config_dir()

        # Load both files
        config = self._load_toml_file(config_dir / "config.toml")
        credentials = self._load_toml_file(config_dir / "credentials.toml")
        merged = self._merge_configs(config, credentials)

        # Validate and store log level
        log_level = merged.get("log_level", "INFO")
        self._log_level = self._validate_log_level(log_level)

        # Determine account ID
        account_id = (
            self._peek_account_id() or
            merged.get("default_account_id") or
            merged.get("account_id")
        )

        if not account_id:
            raise ValueError(
                f"No account_id provided and no default_account_id set in {config_dir}/config.toml"
            )

        if not isinstance(account_id, str):
            raise TypeError(
                f"default_account_id must be a **quoted string**, like \"201263\" — not an unquoted number.\n"
                f"Please update your config: {config_dir}/config.toml"
            )

        # Validate selected account
        accounts = merged.get("accounts", {})
        if account_id not in accounts:
            raise KeyError(
                f"Account ID '{account_id}' not found in [accounts] section of {config_dir}/config.toml"
            )

        self._config = merged
        self._account_id = account_id
        self._account_data = accounts[account_id]

    def validate(self):
        """Validate required fields for the selected account."""
        self._ensure_loaded()


        logger.debug( json.dumps( self._config ))

        required_keys = ["client_id", "client_secret"]
        optional_keys = []

        missing = [key for key in required_keys if key not in self._account_data]
        if missing:
            raise ValueError(
                f"Missing required keys for account '{self._account_id}': {', '.join(missing)}"
            )

        for key in optional_keys:
            if key not in self._account_data:
                #from loguru import logger
                logger.warning(f"Optional key '{key}' not set for account {self._account_id}")

    @property
    def config_dir(self) -> Path:
        return self._get_config_dir()

    @property
    def account_id(self):
        self._ensure_loaded()
        return self._account_id

    @property
    def account(self):
        self._ensure_loaded()
        return self._account_data

    @property
    def all_config(self):
        self._ensure_loaded()
        return self._config

    @property
    def log_level(self):
        self._ensure_loaded()
        return self._log_level


# Global singleton
config = WatoolsConfig()
