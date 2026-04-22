"""Print a concise snapshot of one Trello board, its lists, and its cards."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen


ENVIRONMENT_FILE = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\.env")
TRELLO_API_BASE_URL = "https://api.trello.com/1"
STRATEGIC_PLAN_BOARD_ID = "661cf193e0d1ae943cef40e6"
TARGET_LIST_NAMES = {
    "Seasonal Plan",
    "Sprint Plan",
    "On Task",
    "Paused/ In basket",
}


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


def fetch_json(path: str, trello_key: str, trello_token: str) -> object:
    """Fetch JSON from a Trello REST path with key and token query parameters."""
    query_string = urlencode({"key": trello_key, "token": trello_token})
    request_url = f"{TRELLO_API_BASE_URL}{path}?{query_string}"

    with urlopen(request_url) as response:
        response_body = response.read().decode("utf-8")

    return json.loads(response_body)


def safe_console_text(text: str) -> str:
    """Replace characters that cannot be rendered in the current Windows console."""
    return text.encode("cp1252", errors="replace").decode("cp1252")


def main() -> None:
    """Load credentials, query Trello, and print a filtered board snapshot."""
    environment_values = load_env_file(ENVIRONMENT_FILE)
    trello_key = environment_values["TRELLO_KEY"]
    trello_token = environment_values["TRELLO_TOKEN"]

    try:
        lists = fetch_json(
            f"/boards/{STRATEGIC_PLAN_BOARD_ID}/lists",
            trello_key=trello_key,
            trello_token=trello_token,
        )
        cards = fetch_json(
            f"/boards/{STRATEGIC_PLAN_BOARD_ID}/cards",
            trello_key=trello_key,
            trello_token=trello_token,
        )
    except HTTPError as error:
        error_body = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Trello API returned HTTP {error.code}: {error_body}") from error
    except URLError as error:
        raise RuntimeError(f"Could not reach Trello API: {error.reason}") from error

    cards_by_list_id: dict[str, list[dict[str, object]]] = {}
    for card in cards:
        cards_by_list_id.setdefault(str(card["idList"]), []).append(card)

    print("BOARD: Strategic Plan")
    for trello_list in lists:
        if trello_list["name"] not in TARGET_LIST_NAMES:
            continue

        list_id = str(trello_list["id"])
        print(f"LIST: {trello_list['name']} ({list_id})")
        list_cards = cards_by_list_id.get(list_id, [])
        if not list_cards:
            print("  No cards found.")
            print()
            continue

        for card in list_cards:
            description = str(card.get("desc", "")).strip().replace("\r\n", "\n")
            print(safe_console_text(f"  CARD: {card['name']} ({card['id']})"))
            if description:
                first_line = description.splitlines()[0]
                print(safe_console_text(f"    DESC: {first_line[:140]}"))
            else:
                print("    DESC: <empty>")

        print()


if __name__ == "__main__":
    main()
