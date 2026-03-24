"""
logger.py
Persists pick history to a JSON log file (data/picks_log.json).
Each run appends a timestamped session entry with all slips and their legs.
"""
import json
import os
from datetime import datetime, timezone

LOG_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "picks_log.json")


def _load() -> list:
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    if not os.path.exists(LOG_PATH):
        return []
    try:
        with open(LOG_PATH, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (json.JSONDecodeError, OSError):
        return []


def _save(records: list) -> None:
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    with open(LOG_PATH, "w", encoding="utf-8") as fh:
        json.dump(records, fh, ensure_ascii=False, indent=2)


def log_picks(slips: list[dict]) -> None:
    """
    Append the current session's slips to the log file.
    Each slip has its legs serialised without circular refs.
    """
    if not slips:
        return
    records = _load()
    session = {
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "slips": [
            {
                "label": s["label"],
                "tag": s["tag"],
                "risk": s["risk"],
                "combined_odds": s["combined_odds"],
                "stake": s["stake"],
                "potential_payout": s["potential_payout"],
                "sports_mix": s["sports_mix"],
                "legs": [
                    {
                        "sport": l["sport"],
                        "match": l["match"],
                        "tournament": l.get("tournament", ""),
                        "market": l["market"],
                        "odds": l["odds"],
                        "game_id": l.get("game_id"),
                        "outcome_id": l.get("outcome_id"),
                    }
                    for l in s["legs"]
                ],
            }
            for s in slips
        ],
    }
    records.append(session)
    # Keep last 500 sessions to avoid unbounded file growth
    _save(records[-500:])
    print(f"[logger] Session logged — {len(slips)} slip(s) written to {LOG_PATH}")
