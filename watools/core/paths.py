import os
from pathlib import Path

APP_NAME = "watools"

def get_project_root() -> Path:
    """Return the root directory of the project (2 levels above this file)."""
    return Path(__file__).resolve().parents[2]


def get_default_config_dir() -> Path:
    """Return the default config directory, following the XDG spec or local override."""
    env_path = os.getenv("WATOOLS_CONFIG_DIR")
    if env_path:
        return Path(env_path).expanduser()

    local_path = get_project_root() / "config"
    if local_path.exists():
        return local_path

    return Path(os.getenv("XDG_CONFIG_HOME", Path.home() / ".config")) / APP_NAME


def get_default_cache_dir() -> Path:
    """Return the default cache directory, following the XDG spec or local override."""
    env_path = os.getenv("WATOOLS_CACHE_DIR")
    if env_path:
        return Path(env_path).expanduser()

    local_path = get_project_root() / ".cache"
    if local_path.exists():
        return local_path

    return Path(os.getenv("XDG_CACHE_HOME", Path.home() / ".cache")) / APP_NAME
