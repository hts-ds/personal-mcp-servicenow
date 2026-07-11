"""Tests for config_loader module."""
import os
import json
import tempfile
import pytest
from unittest.mock import patch


class TestGetConfigDir:
    """Tests for get_config_dir function."""

    @patch('platform.system', return_value='Darwin')
    def test_macos_config_dir(self, mock_system):
        from config_loader import get_config_dir
        result = get_config_dir()
        assert os.path.join('.config', 'mcp-servicenow') in result

    @patch('platform.system', return_value='Windows')
    @patch.dict(os.environ, {'APPDATA': 'C:\\Users\\Test\\AppData\\Roaming'})
    def test_windows_config_dir(self, mock_system):
        from config_loader import get_config_dir
        result = get_config_dir()
        assert 'mcp-servicenow' in result


class TestLoadConfig:
    """Tests for load_config function."""

    def test_env_vars_take_precedence(self):
        """Environment variables should override config file."""
        from config_loader import load_config

        with patch.dict(os.environ, {
            'SERVICE_NOW_HOST': 'env-instance.service-now.com',
            'SERVICE_NOW_USERNAME': 'env-user',
            'SERVICE_NOW_PASSWORD': 'env-pass'
        }):
            config = load_config()
            assert config['instance'] == 'env-instance.service-now.com'
            assert config['auth_type'] == 'basic'
            assert config['username'] == 'env-user'

    def test_config_file_loading(self):
        """Should load from config file when env vars not set."""
        from config_loader import load_config, get_config_dir

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch('config_loader.get_config_dir', return_value=tmpdir):
                config_file = os.path.join(tmpdir, 'config.json')
                with open(config_file, 'w') as f:
                    json.dump({
                        'instance': 'file-instance.service-now.com',
                        'auth_type': 'basic',
                        'username': 'file-user',
                        'password': 'file-pass'
                    }, f)

                # A file-config precedence test must not consult the ignored
                # developer-local credentials referenced by SERVICENOW_ENV_FILE.
                with patch('config_loader.load_servicenow_environment'), \
                     patch.dict(os.environ, {}, clear=True):
                    config = load_config()
                    assert config['instance'] == 'file-instance.service-now.com'


class TestValidateConfig:
    """Tests for validate_config function."""

    def test_valid_basic_config_without_auth_type(self):
        from config_loader import validate_config
        config = {
            'instance': 'test.service-now.com',
            'username': 'user',
            'password': 'pass'
        }
        # Should not raise
        validate_config(config)

    def test_valid_basic_config(self):
        from config_loader import validate_config
        config = {
            'instance': 'test.service-now.com',
            'auth_type': 'basic',
            'username': 'user',
            'password': 'pass'
        }
        # Should not raise
        validate_config(config)

    def test_missing_instance_raises(self):
        from config_loader import validate_config, ConfigError
        config = {
            'auth_type': 'basic',
            'username': 'user',
            'password': 'pass'
        }
        with pytest.raises(ConfigError, match='instance'):
            validate_config(config)

    def test_oauth_auth_type_is_rejected(self):
        from config_loader import validate_config, ConfigError
        config = {
            'instance': 'test.service-now.com',
            'auth_type': 'oauth',
            'username': 'user',
            'password': 'pass'
        }
        with pytest.raises(ConfigError, match='Basic Auth'):
            validate_config(config)

    def test_missing_username_raises(self):
        from config_loader import validate_config, ConfigError

        with pytest.raises(ConfigError, match='username'):
            validate_config({
                'instance': 'test.service-now.com',
                'password': 'pass',
            })

    def test_missing_password_raises(self):
        from config_loader import validate_config, ConfigError

        with pytest.raises(ConfigError, match='password'):
            validate_config({
                'instance': 'test.service-now.com',
                'username': 'user',
            })


def test_load_config_from_external_env_file(tmp_path, monkeypatch):
    """Existing H104 credentials can be referenced without copying secrets."""
    external_env = tmp_path / "servicenow.env"
    external_env.write_text(
        "SERVICE_NOW_HOST=https://h104.example.service-now.com\n"
        "SERVICE_NOW_USERNAME=h104-user\n"
        "SERVICE_NOW_PASSWORD=h104-password\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("SERVICENOW_INSTANCE", raising=False)
    monkeypatch.delenv("SERVICENOW_USERNAME", raising=False)
    monkeypatch.delenv("SERVICENOW_PASSWORD", raising=False)
    monkeypatch.setenv("SERVICENOW_ENV_FILE", str(external_env))

    from config_loader import load_config_from_env

    config = load_config_from_env()

    assert config["instance"] == "https://h104.example.service-now.com"
    assert config["username"] == "h104-user"
    assert config["password"] == "h104-password"


def test_setup_instructions_only_describe_basic_auth():
    from config_loader import get_setup_instructions

    instructions = get_setup_instructions()

    assert "SERVICENOW_USERNAME" in instructions
    assert "SERVICENOW_PASSWORD" in instructions
    assert "CLIENT_SECRET" not in instructions
    assert "OAuth" not in instructions
