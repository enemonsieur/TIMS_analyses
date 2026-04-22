"""Dump Strategic Plan planning lists with card descriptions and recent comments."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen


ENVIRONMENT_FILE = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\.env")
TRELLO_API_BASE_URL = "https://api.trello.com/1"
STRATEGIC_PLAN_BOARD_ID = "661cf193e0d1ae943cef40e6"
TARGET_LIST_NAMES = [
    "Seasonal Plan",
    "Sprint Plan",
    "On Task",
    "Paused/ In basket",
]


def load_env_file(environment_file: Path) -> dict[str, str]:
    environment_values: dict[str, str] = {}
    for raw_line in environment_file.read_text(encoding="utf-8").splitlines():
        stripped_line = raw_line.strip()
        if not stripped_line or stripped_line.startswith("#"):
            continue
        key, value = stripped_line.split("=", 1)
        environment_values[key.strip()] = value.strip()
    return environment_values


def fetch_json(path: str, trello_key: str, trello_token: str) -> object:
    query_string = urlencode({"key": trello_key, "token": trello_token})
    separator = "&" if "?" in path else "?"
    request_url = f"{TRELLO_API_BASE_URL}{path}{separator}{query_string}"
    with urlopen(request_url) as response:
        return json.loads(response.read().decode("utf-8"))


def safe_console_text(text: str) -> str:
    return text.encode("cp1252", errors="replace").decode("cp1252")


def print_multiline_block(prefix: str, text: str) -> None:
    clean_text = text.replace("\r\n", "\n").strip()
    if not clean_text:
        print(f"{prefix}<empty>")
        return
    for line in clean_text.splitlines():
        print(safe_console_text(f"{prefix}{line}"))


def main() -> None:
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

    list_order = {
        str(trello_list["id"]): index
        for index, trello_list in enumerate(lists)
        if trello_list["name"] in TARGET_LIST_NAMES
    }
    relevant_lists = [
        trello_list for trello_list in lists if trello_list["name"] in TARGET_LIST_NAMES
    ]
    relevant_cards = [
        card for card in cards if str(card["idList"]) in list_order
    ]
    relevant_cards.sort(key=lambda card: (list_order[str(card["idList"])], card["name"].lower()))

    print("BOARD: Strategic Plan")
    current_list_id = None
    for card in relevant_cards:
        if str(card["idList"]) != current_list_id:
            current_list_id = str(card["idList"])
            matching_list = next(
                trello_list for trello_list in relevant_lists if str(trello_list["id"]) == current_list_id
            )
            print()
            print(safe_console_text(f"LIST: {matching_list['name']} ({matching_list['id']})"))

        card_id = str(card["id"])
        print()
        print(safe_console_text(f"CARD: {card['name']} ({card_id})"))
        print_multiline_block("  DESC: ", str(card.get("desc", "")))

        try:
            actions = fetch_json(
                f"/cards/{card_id}/actions?filter=commentCard&limit=12",
                trello_key=trello_key,
                trello_token=trello_token,
            )
        except HTTPError as error:
            error_body = error.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Trello comments fetch failed HTTP {error.code}: {error_body}") from error

        if not actions:
            print("  COMMENTS: <none>")
            continue

        print("  COMMENTS:")
        for action in actions:
            action_date = str(action.get("date", ""))[:10]
            comment_text = str(action.get("data", {}).get("text", ""))
            print_multiline_block(f"    {action_date}: ", comment_text)


if __name__ == "__main__":
    main()
