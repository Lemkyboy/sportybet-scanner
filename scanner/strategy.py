"""
strategy.py
Applies the three-sport edge strategy to raw SportyBet fixture lists.

EDGE RULES (calibrated for SportyBet Nigeria odds ranges):
  Football  — Strong home favourite (W1 ≤ 1.65):
                DC 1X odds in range 1.05–1.40  (lower risk)
                OR Over 2.5 Goals odds in range 1.50–2.00  (attacking edge)
  Basketball — Clear favourite (W1 or W2 ≤ 1.45), Moneyline odds 1.10–1.45
  Tennis     — Strong favourite (W1 or W2 ≤ 1.50), Match Winner odds 1.15–1.60
"""
import concurrent.futures
from scanner.fetcher import (
    fetch_fixture_detail,
    safe_odds,
    find_market,
    MARKET_1X2,
    MARKET_DOUBLE_CHANCE,
    MARKET_OVER_UNDER,
    MARKET_MONEYLINE,
)

# ── Helpers ──────────────────────────────────────────────────────────────────────────────────

def _get_1x2_odds(fixture: dict) -> tuple[float | None, float | None, float | None]:
    """
    Extract Home / Draw / Away odds from a fixture summary.
    SportyBet returns these in the primary market (id="1") of the fixture list.
    Returns (home, draw, away) as floats or None.
    """
    markets = fixture.get("markets") or []
    mkt = find_market(markets, MARKET_1X2)
    if not mkt:
        return None, None, None
    outcomes = mkt.get("outcomes") or []
    home = safe_odds(outcomes[0]) if len(outcomes) > 0 else None
    draw = safe_odds(outcomes[1]) if len(outcomes) > 1 else None
    away = safe_odds(outcomes[2]) if len(outcomes) > 2 else None
    return home, draw, away


# ── Football edge ─────────────────────────────────────────────────────────────────────────────

def _enrich_football(fixture: dict) -> dict | None:
    """
    Two football edges:
      1. DC 1X — strong home favourite (W1 ≤ 1.65), DC odds 1.05–1.40
      2. Over 2.5 Goals — attacking matchup, odds 1.50–2.00
    Fetches match detail to access DC and Over/Under markets.
    """
    home_odds, _, _ = _get_1x2_odds(fixture)
    if not home_odds or home_odds > 1.65:
        return None

    game_id = fixture.get("gameId")
    detail = fetch_fixture_detail(game_id)
    markets = detail.get("markets") or []

    # Try DC 1X first (lower risk)
    dc_mkt = find_market(markets, MARKET_DOUBLE_CHANCE)
    if dc_mkt:
        outcomes = dc_mkt.get("outcomes") or []
        # 1X is the first outcome in Double Chance
        dc_1x_odds = safe_odds(outcomes[0]) if outcomes else None
        if dc_1x_odds and (1.05 <= dc_1x_odds <= 1.40):
            return {
                "sport": "Football",
                "game_id": game_id,
                "match": f"{fixture['homeTeamName']} vs {fixture['awayTeamName']}",
                "tournament": fixture.get("tournamentName", ""),
                "start_time": fixture.get("estimateStartTime"),
                "favourite": fixture["homeTeamName"],
                "fav_odds": home_odds,
                "market": "Double Chance 1X",
                "market_id": MARKET_DOUBLE_CHANCE,
                "outcome_id": outcomes[0].get("id") if outcomes else None,
                "odds": dc_1x_odds,
                "edge_score": round((1 / dc_1x_odds) * (1 / home_odds), 4),
            }

    # Fallback: Over 2.5 Goals
    ou_mkt = find_market(markets, MARKET_OVER_UNDER)
    if ou_mkt:
        outcomes = ou_mkt.get("outcomes") or []
        # Over is typically the first outcome in Over/Under
        over_odds = safe_odds(outcomes[0]) if outcomes else None
        if over_odds and (1.50 <= over_odds <= 2.00):
            return {
                "sport": "Football",
                "game_id": game_id,
                "match": f"{fixture['homeTeamName']} vs {fixture['awayTeamName']}",
                "tournament": fixture.get("tournamentName", ""),
                "start_time": fixture.get("estimateStartTime"),
                "favourite": fixture["homeTeamName"],
                "fav_odds": home_odds,
                "market": "Goals Over 2.5",
                "market_id": MARKET_OVER_UNDER,
                "outcome_id": outcomes[0].get("id") if outcomes else None,
                "odds": over_odds,
                "edge_score": round((1 / over_odds) * (1 / home_odds), 4),
            }

    return None


# ── Basketball edge ───────────────────────────────────────────────────────────────────────────

def _enrich_basketball(fixture: dict) -> dict | None:
    """
    Moneyline edge on clear Basketball favourites.
    No detail fetch needed — moneyline odds are in the fixture summary.
    """
    markets = fixture.get("markets") or []
    # Basketball uses market id=219 (Moneyline) or id=1 (1x2 without draw)
    mkt = find_market(markets, MARKET_MONEYLINE) or find_market(markets, MARKET_1X2)
    if not mkt:
        return None
    outcomes = mkt.get("outcomes") or []
    home_odds = safe_odds(outcomes[0]) if len(outcomes) > 0 else None
    away_odds = safe_odds(outcomes[1]) if len(outcomes) > 1 else None

    if home_odds and home_odds <= 1.45:
        fav_odds = home_odds
        fav_team = fixture["homeTeamName"]
        outcome_id = outcomes[0].get("id") if outcomes else None
    elif away_odds and away_odds <= 1.45:
        fav_odds = away_odds
        fav_team = fixture["awayTeamName"]
        outcome_id = outcomes[1].get("id") if len(outcomes) > 1 else None
    else:
        return None

    if not (1.10 <= fav_odds <= 1.45):
        return None

    return {
        "sport": "Basketball",
        "game_id": fixture.get("gameId"),
        "match": f"{fixture['homeTeamName']} vs {fixture['awayTeamName']}",
        "tournament": fixture.get("tournamentName", ""),
        "start_time": fixture.get("estimateStartTime"),
        "favourite": fav_team,
        "fav_odds": fav_odds,
        "market": f"Moneyline — {fav_team}",
        "market_id": MARKET_MONEYLINE,
        "outcome_id": outcome_id,
        "odds": fav_odds,
        "edge_score": round(1 / fav_odds, 4),
    }


# ── Tennis edge ───────────────────────────────────────────────────────────────────────────────

def _enrich_tennis(fixture: dict) -> dict | None:
    """
    Match Winner edge on strong Tennis favourites.
    No detail fetch needed — match winner odds come in the fixture summary.
    """
    markets = fixture.get("markets") or []
    mkt = find_market(markets, MARKET_1X2) or find_market(markets, MARKET_MONEYLINE)
    if not mkt:
        return None
    outcomes = mkt.get("outcomes") or []
    p1_odds = safe_odds(outcomes[0]) if len(outcomes) > 0 else None
    p2_odds = safe_odds(outcomes[1]) if len(outcomes) > 1 else None

    if p1_odds and p1_odds <= 1.50:
        fav_odds = p1_odds
        fav_player = fixture.get("homeTeamName", "Player 1")
        outcome_id = outcomes[0].get("id") if outcomes else None
    elif p2_odds and p2_odds <= 1.50:
        fav_odds = p2_odds
        fav_player = fixture.get("awayTeamName", "Player 2")
        outcome_id = outcomes[1].get("id") if len(outcomes) > 1 else None
    else:
        return None

    if not (1.15 <= fav_odds <= 1.60):
        return None

    return {
        "sport": "Tennis",
        "game_id": fixture.get("gameId"),
        "match": f"{fixture.get('homeTeamName', 'P1')} vs {fixture.get('awayTeamName', 'P2')}",
        "tournament": fixture.get("tournamentName", ""),
        "start_time": fixture.get("estimateStartTime"),
        "favourite": fav_player,
        "fav_odds": fav_odds,
        "market": f"Match Winner — {fav_player}",
        "market_id": MARKET_1X2,
        "outcome_id": outcome_id,
        "odds": fav_odds,
        "edge_score": round(1 / fav_odds, 4),
    }


# ── Public interface ──────────────────────────────────────────────────────────────────────────

def filter_edges(raw: dict) -> dict[str, list]:
    """
    Run all three sport enrichment functions concurrently.
    Returns dict with 'football', 'basketball', 'tennis' edge lists,
    sorted by edge_score descending.

    Football needs match-detail API calls so it runs in a thread pool.
    Basketball and Tennis use fixture-summary odds only (fast / no extra calls).
    """
    results: dict[str, list] = {
        "football": [],
        "basketball": [],
        "tennis": [],
    }

    # Basketball and Tennis: fast inline (no detail fetch)
    for fixture in raw.get("basketball", []):
        sel = _enrich_basketball(fixture)
        if sel:
            results["basketball"].append(sel)

    for fixture in raw.get("tennis", []):
        sel = _enrich_tennis(fixture)
        if sel:
            results["tennis"].append(sel)

    # Football: needs detail fetch — run top candidates in parallel
    def enrich_all_football():
        candidates = [
            f for f in raw.get("football", [])
            if _get_1x2_odds(f)[0] is not None
            and _get_1x2_odds(f)[0] <= 1.65
        ][:20]  # top 20 candidates
        out = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            for sel in pool.map(_enrich_football, candidates):
                if sel:
                    out.append(sel)
        return out

    results["football"] = sorted(
        enrich_all_football(), key=lambda x: x["edge_score"], reverse=True
    )
    results["basketball"] = sorted(
        results["basketball"], key=lambda x: x["edge_score"], reverse=True
    )
    results["tennis"] = sorted(
        results["tennis"], key=lambda x: x["edge_score"], reverse=True
    )

    print(f"[strategy] Edges found: "
          f"Football={len(results['football'])} "
          f"Basketball={len(results['basketball'])} "
          f"Tennis={len(results['tennis'])}")
    return results
