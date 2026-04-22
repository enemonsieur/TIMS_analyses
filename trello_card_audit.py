"""Print descriptions and recent comments for selected Strategic Plan cards."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen


ENVIRONMENT_FILE = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\.env")
TRELLO_API_BASE_URL = "https://api.trello.com/1"
TARGET_CARDS = {
    "695d44103839c588450b0486": "CNT lab's progress",
    "69e1f29115fc3cca3b9581a5": "Sprint Plan - Short Term Longterms.",
    "692d5f2236eda41be30b2ed0": "Frequency Tagging with VTS",
    "69773af9d355dc1298995acd": "TIMS Dose Response Project",
    "69df8c33ede437c6d56c780d": "On Task - Short Term Longterms.",
    "69789434df9bc2306009a87b": "CL-Bayesian Optimization",
    "69834e707c229aaab075acbf": "Lab General",
    "69d647bcb2212ce2b15c0473": "Exoskeleton neurorehab",
    "695cfb30a88a06154730c70f": "Yearly Plans and Values 2026",
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
    separator = "&" if "?" in path else "?"
    request_url = f"{TRELLO_API_BASE_URL}{path}{separator}{query_string}"

    with urlopen(request_url) as response:
        response_body = response.read().decode("utf-8")

    return json.loads(response_body)


def safe_console_text(text: str) -> str:
    """Replace characters that cannot be rendered in the current Windows console."""
    return text.encode("cp1252", errors="replace").decode("cp1252")


def print_multiline_block(prefix: str, text: str) -> None:
    """Print multiline text with a consistent prefix."""
    if not text.strip():
        print(f"{prefix}<empty>")
        return

    for line in text.replace("\r\n", "\n").splitlines():
        print(safe_console_text(f"{prefix}{line}"))


def main() -> None:
    """Load credentials, query Trello, and print card descriptions and comments."""
    environment_values = load_env_file(ENVIRONMENT_FILE)
    trello_key = environment_values["TRELLO_KEY"]
    trello_token = environment_values["TRELLO_TOKEN"]

    try:
        for card_id, label in TARGET_CARDS.items():
            card = fetch_json(f"/cards/{card_id}", trello_key=trello_key, trello_token=trello_token)
            actions = fetch_json(
                f"/cards/{card_id}/actions?filter=commentCard&limit=15",
                trello_key=trello_key,
                trello_token=trello_token,
            )

            print(safe_console_text(f"CARD: {label} ({card_id})"))
            print_multiline_block("  DESC: ", str(card.get("desc", "")))
            if not actions:
                print("  COMMENTS: <none>")
            else:
                print("  COMMENTS:")
                for action in actions:
                    action_date = str(action.get("date", ""))[:10]
                    comment_text = str(action.get("data", {}).get("text", ""))
                    print_multiline_block(f"    {action_date}: ", comment_text)
            print()
    except HTTPError as error:
        error_body = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Trello API returned HTTP {error.code}: {error_body}") from error
    except URLError as error:
        raise RuntimeError(f"Could not reach Trello API: {error.reason}") from error


if __name__ == "__main__":
    main()
