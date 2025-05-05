"""
"""
import os
import toml
import click
from loguru import logger

def find_config_file():
    """Search for the .fantools file starting from the current directory and walking up."""
    current_dir = os.getcwd()
    home_dir = os.path.expanduser("~")
    root_dir = os.path.abspath(os.sep)

    while current_dir != root_dir:  # Stop at the root directory
        config_file = os.path.join(current_dir, ".fantools")
        if os.path.exists(config_file):
            return config_file
        current_dir = os.path.dirname(current_dir)  # Move to the parent directory

    # Check the home directory as a last resort
    config_file = os.path.join(home_dir, ".fantools")
    if os.path.exists(config_file):
        return config_file

    return None  # No config file found

# Find the .fantools file
CONFIG_FILE = find_config_file()

# Initialize the config dictionary
config = {}

# Load the configuration if the file is found
if CONFIG_FILE:
    try:
        with open(CONFIG_FILE, 'r') as file:
            config = toml.load(file)
    except Exception as e:
        click.echo(f"Error loading configuration file: {e}")
else:
    click.echo("Configuration file not found.")

config['config_file'] = CONFIG_FILE  # Add the config file path to the config dictionary

LOG_LEVEL = 'INFO'
logger.remove()  # Remove the default logger
logger.add(lambda msg: click.echo(msg), level=LOG_LEVEL)
logger.debug(f"Default Log level set to: {LOG_LEVEL}")


if 'log_level' in config:
    LOG_LEVEL = config['log_level'].upper()
    if LOG_LEVEL not in ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']:
        click.debug(f"Invalid log level '{LOG_LEVEL}' in configuration. Defaulting to INFO.")
else:
    logger.debug("LOG_LEVEL not found in configuration. Defaulting to INFO.")

logger.remove()  # Remove the default logger
logger.add(lambda msg: click.echo(msg,nl=False), level=LOG_LEVEL)
logger.debug(f"Log level set to: {LOG_LEVEL}")
