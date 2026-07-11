#!/usr/bin/env python3
"""
MCP ServiceNow Server

A Model Context Protocol server for ServiceNow integration.
"""
import argparse
import getpass
import sys

import structlog

# Configure structlog once at the entry point so every module that calls
# structlog.get_logger() emits JSON to stderr (Azure Monitor ingests it
# automatically from Container Apps / ACI stdout/stderr).
structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
)

__version__ = "4.0.0"


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        prog='mcp-servicenow',
        description='MCP ServiceNow Server - ServiceNow integration for Claude'
    )
    parser.add_argument(
        '--version',
        action='version',
        version=f'mcp-servicenow {__version__}'
    )
    parser.add_argument(
        '--setup',
        action='store_true',
        help='Run interactive setup wizard'
    )
    return parser.parse_args()


def run_setup():
    """Run interactive setup wizard."""
    from config_loader import save_config, get_config_file_path

    print("MCP ServiceNow Setup Wizard")
    print("=" * 40)
    print()

    config = {}

    config['instance'] = input("ServiceNow instance URL (e.g., company.service-now.com): ").strip()

    print("\nAuthentication: Basic Auth (username/password)")
    config['auth_type'] = 'basic'
    config['username'] = input("Username: ").strip()
    config['password'] = getpass.getpass("Password: ").strip()

    save_config(config)
    print(f"\nConfiguration saved to: {get_config_file_path()}")
    print("You can now use mcp-servicenow in your Claude Code configuration.")


def main():
    """Main entry point."""
    args = parse_args()

    if args.setup:
        run_setup()
        sys.exit(0)

    # Basic credentials back a broad, write-capable tool set. This fork is
    # intentionally local-only: stdio keeps the MCP endpoint inside the local
    # client process boundary rather than exposing unauthenticated remote SSE.
    import os
    transport = os.environ.get("MCP_TRANSPORT", "stdio")

    if transport != "stdio":
        print(
            "This Basic Auth fork supports stdio only. Use the H104 CMDB MCP "
            "for secured HTTP/SSE deployment.",
            file=sys.stderr,
        )
        raise SystemExit(2)

    print("Personal ServiceNow MCP Server started (stdio).", file=sys.stderr)
    from tools import mcp
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
