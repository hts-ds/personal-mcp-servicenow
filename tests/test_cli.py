"""Tests for CLI argument handling."""
import subprocess
import sys
from unittest.mock import patch

import pytest


def test_version_flag():
    """--version should print version and exit 0."""
    result = subprocess.run(
        [sys.executable, 'personal_mcp_servicenow_main.py', '--version'],
        capture_output=True,
        text=True
    )
    assert result.returncode == 0
    assert 'mcp-servicenow' in result.stdout.lower() or '2.0.0' in result.stdout


def test_help_flag():
    """--help should print usage and exit 0."""
    result = subprocess.run(
        [sys.executable, 'personal_mcp_servicenow_main.py', '--help'],
        capture_output=True,
        text=True
    )
    assert result.returncode == 0
    assert 'usage' in result.stdout.lower() or '--version' in result.stdout


def test_setup_collects_only_basic_auth_fields(monkeypatch, capsys):
    """The fork's setup wizard must not offer or persist OAuth credentials."""
    import personal_mcp_servicenow_main as launcher

    captured = {}
    answers = iter(["https://test.service-now.com", "test-user"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    monkeypatch.setattr(launcher.getpass, "getpass", lambda _: "test-password")
    monkeypatch.setattr(
        "config_loader.save_config", lambda config: captured.update(config)
    )

    launcher.run_setup()

    output = capsys.readouterr().out
    assert captured == {
        "instance": "https://test.service-now.com",
        "auth_type": "basic",
        "username": "test-user",
        "password": "test-password",
    }
    assert "OAuth" not in output


def test_stdio_main_keeps_stdout_clean(monkeypatch, capsys):
    """The local MCP launcher must reserve stdout for JSON-RPC frames."""
    import personal_mcp_servicenow_main as launcher
    from tools import mcp

    monkeypatch.setattr(sys, "argv", ["personal_mcp_servicenow_main.py"])
    monkeypatch.setenv("MCP_TRANSPORT", "stdio")
    with patch.object(mcp, "run") as run:
        launcher.main()

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "started (stdio)" in captured.err
    run.assert_called_once_with(transport="stdio")


def test_sse_transport_is_rejected_for_basic_auth_fork(monkeypatch, capsys):
    """A broad Basic Auth server must not expose unauthenticated remote SSE."""
    import personal_mcp_servicenow_main as launcher
    from tools import mcp

    monkeypatch.setattr(sys, "argv", ["personal_mcp_servicenow_main.py"])
    monkeypatch.setenv("MCP_TRANSPORT", "sse")
    with patch.object(mcp, "run") as run, pytest.raises(SystemExit) as exit_status:
        launcher.main()

    assert exit_status.value.code == 2
    assert "stdio only" in capsys.readouterr().err
    run.assert_not_called()
