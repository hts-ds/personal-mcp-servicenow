"""
Configuration loader for MCP ServiceNow.

Supports loading credentials from:
1. Environment variables (highest priority)
2. Config file (~/.config/mcp-servicenow/config.json on Unix, %APPDATA% on Windows)

Environment variables:
- SERVICENOW_INSTANCE or SERVICE_NOW_HOST: ServiceNow instance URL
- SERVICENOW_USERNAME or SERVICE_NOW_USERNAME: Basic auth username
- SERVICENOW_PASSWORD or SERVICE_NOW_PASSWORD: Basic auth password
- SERVICENOW_ENV_FILE: optional path to an existing local credential file
"""
import os
import json
import platform
from typing import Dict, Any

from auth.environment import load_servicenow_environment


class ConfigError(Exception):
    """Raised when configuration is invalid or missing."""
    pass


def get_config_dir() -> str:
    """Get the configuration directory path based on platform."""
    system = platform.system()

    if system == 'Windows':
        base = os.environ.get('APPDATA', os.path.expanduser('~'))
        return os.path.join(base, 'mcp-servicenow')
    else:
        # macOS and Linux
        return os.path.join(os.path.expanduser('~'), '.config', 'mcp-servicenow')


def get_config_file_path() -> str:
    """Get the full path to the config file."""
    return os.path.join(get_config_dir(), 'config.json')


def load_config_from_env() -> Dict[str, Any]:
    """Load configuration from environment variables."""
    load_servicenow_environment()
    config = {'auth_type': os.environ.get('SERVICENOW_AUTH_TYPE', 'basic').lower()}
    env_mapping = {
        'instance': ('SERVICENOW_INSTANCE', 'SERVICE_NOW_HOST'),
        'username': ('SERVICENOW_USERNAME', 'SERVICE_NOW_USERNAME'),
        'password': ('SERVICENOW_PASSWORD', 'SERVICE_NOW_PASSWORD'),
    }

    for config_key, names in env_mapping.items():
        for env_var in names:
            value = os.environ.get(env_var)
            if value:
                config[config_key] = value
                break

    return config


def load_config_from_file() -> Dict[str, Any]:
    """Load configuration from config file."""
    config_path = get_config_file_path()

    if not os.path.exists(config_path):
        return {}

    try:
        with open(config_path, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        raise ConfigError(f"Failed to read config file: {e}")


def load_config() -> Dict[str, Any]:
    """
    Load configuration with priority:
    1. Environment variables (highest)
    2. Config file

    Returns merged configuration dictionary.
    """
    # Start with file config as base
    config = load_config_from_file()

    # Override with environment variables
    env_config = load_config_from_env()
    config.update(env_config)

    return config


def validate_config(config: Dict[str, Any]) -> None:
    """
    Validate configuration is complete.

    Raises:
        ConfigError: If required fields are missing.
    """
    if not config.get('instance'):
        raise ConfigError(
            "Missing 'instance'. Set SERVICENOW_INSTANCE env var or add to config file."
        )

    auth_type = config.get('auth_type', 'basic').lower()
    if auth_type != 'basic':
        raise ConfigError(
            "Only Basic Auth is supported by this fork. Remove SERVICENOW_AUTH_TYPE "
            "or set it to 'basic'."
        )

    if not config.get('username'):
        raise ConfigError(
            "Basic auth requires 'username'. Set SERVICENOW_USERNAME or "
            "SERVICE_NOW_USERNAME."
        )
    if not config.get('password'):
        raise ConfigError(
            "Basic auth requires 'password'. Set SERVICENOW_PASSWORD or "
            "SERVICE_NOW_PASSWORD."
        )


def save_config(config: Dict[str, Any]) -> None:
    """Save configuration to config file."""
    config = dict(config)
    config['auth_type'] = 'basic'
    config.pop('client_id', None)
    config.pop('client_secret', None)
    config_dir = get_config_dir()
    os.makedirs(config_dir, exist_ok=True)

    config_path = get_config_file_path()
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)

    # Set restrictive permissions on Unix
    if platform.system() != 'Windows':
        os.chmod(config_path, 0o600)


def get_setup_instructions() -> str:
    """Return setup instructions for users."""
    config_path = get_config_file_path()
    return f"""
MCP ServiceNow Configuration Required
=====================================

Option 1: Environment Variables
-------------------------------
Set these environment variables:
  SERVICENOW_INSTANCE=https://your-instance.service-now.com
  SERVICENOW_USERNAME=your-username
  SERVICENOW_PASSWORD=your-password

Existing H104 variable names are also accepted:
  SERVICE_NOW_HOST=https://your-instance.service-now.com
  SERVICE_NOW_USERNAME=your-username
  SERVICE_NOW_PASSWORD=your-password

To reuse a protected credential file without copying its values:
  SERVICENOW_ENV_FILE=C:\\path\\to\\servicenow.env

Option 2: Config File
---------------------
Create {config_path} with:

{{
  "instance": "your-instance.service-now.com",
  "auth_type": "basic",
  "username": "your-username",
  "password": "your-password"
}}

Option 3: Interactive Setup
---------------------------
Run: mcp-servicenow --setup
"""
