"""List Trello boards using local credentials from a .env file."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen


ENVIRONMENT_FILE = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\.env")
TRELLO_API_BASE_URL = "https://api.trello.com/1"


def load_env_file(environment_file: Path) -> dict[str, str]:
    """Read simple KEY=VALUE pairs from a local .env file."""
    environment_values: dict[str, str] = {}

    for raw_line in environment_file.read_text(encoding="utf-8").splitlines():
        stripped_line = raw_line.strip()
        if not stripped_line or stripped_line.startswith("#"):
            continue
        if "=" not in stripped_line:
            raise ValueError(f"Invalid .env line: {raw_line!r}")

        key, value = stripped_line.split("=", 1)
        environment_values[key.strip()] = value.strip()

    return environment_values


def fetch_trello_boards(trello_key: str, trello_token: str) -> list[dict[str, object]]:
    """Fetch the current member's Trello boards."""
    query_string = urlencode({"key": trello_key, "token": trello_token})
    request_url = f"{TRELLO_API_BASE_URL}/members/me/boards?{query_string}"

    with urlopen(request_url) as response:
        response_body = response.read().decode("utf-8")

    return json.loads(response_body)


def main() -> None:
    """Load credentials, query Trello, and print a short board summary."""
    if not ENVIRONMENT_FILE.is_file():
        raise FileNotFoundError(f"Missing credentials file: {ENVIRONMENT_FILE}")

    environment_values = load_env_file(ENVIRONMENT_FILE)
    trello_key = environment_values.get("TRELLO_KEY")
    trello_token = environment_values.get("TRELLO_TOKEN")
    if not trello_key or not trello_token:
        raise ValueError("Expected TRELLO_KEY and TRELLO_TOKEN in .env.")

    try:
        boards = fetch_trello_boards(trello_key=trello_key, trello_token=trello_token)
    except HTTPError as error:
        error_body = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Trello API returned HTTP {error.code}: {error_body}") from error
    except URLError as error:
        raise RuntimeError(f"Could not reach Trello API: {error.reason}") from error

    if not boards:
        print("No boards found for this Trello account.")
        return

    print("Trello boards:")
    for board in boards:
        print(f"- {board['name']} ({board['id']})")


if __name__ == "__main__":
    main()
