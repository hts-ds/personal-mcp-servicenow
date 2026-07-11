"""Load ServiceNow settings without duplicating credentials across projects."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


EXTERNAL_ENV_FILE_VARIABLE = "SERVICENOW_ENV_FILE"


def load_servicenow_environment() -> None:
    """Load the local ``.env`` and, optionally, a referenced secure env file.

    ``SERVICENOW_ENV_FILE`` is intentionally a path-only setting. It lets an
    H104 developer reuse an already protected local credential file without
    copying username or password into this fork. Process environment values
    continue to take precedence over either file.
    """
    load_dotenv(override=False)

    external_path = os.getenv(EXTERNAL_ENV_FILE_VARIABLE)
    if not external_path:
        return

    candidate = Path(external_path).expanduser()
    if candidate.is_file():
        load_dotenv(dotenv_path=candidate, override=False)
