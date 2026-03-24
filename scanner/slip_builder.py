"""
slip_builder.py
Constructs 3-tier accumulator slips from the filtered SportyBet edge selections.

Sports: Football, Basketball, Tennis
Odds ranges (SportyBet Nigeria):
  Football DC 1X:    1.05 – 1.40
  Football Over 2.5: 1.50 – 2.00
  Basketball ML:     1.10 – 1.45
  Tennis MW:         1.15 – 1.60

Slip tiers:
  Slip A — 3-fold,   ~1.80–3.50×  combined odds  (safe / daily)
  Slip B — 4–6-fold, ~2.50–6.00×  combined odds  (medium risk)
  Slip C — 6–10-fold, ~5.00–20.0× combined odds  (high risk / weekend special)

Logic:
  1. Pool all edges across sports and sort by individual odds (ascending)
  2. Each tier independently searches the full pool for the best combo
  3. 3-pass search: strict diversity → relax diversity → relax lower odds bound
  4. Return slip objects with full metadata for notifier and logger
"""
from itertools import combinations
from math import prod

# ── Slip tier configuration ──────────────────────────────────────────────────────────────────
SLIP_TARGETS = [
    {
        "label": "Slip A",
        "tag": "3-fold",
        "min_legs": 3,
        "max_legs": 3,
        "odds_min": 1.80,
        "odds_max": 3.50,
        "risk": "LOW",
        "stake_suggestion": 1000,
    },
    {
        "label": "Slip B",
        "tag": "5-fold ~5x",
        "min_legs": 4,
        "max_legs": 6,
        "odds_min": 2.50,
        "odds_max": 6.00,
        "risk": "MEDIUM",
        "stake_suggestion": 500,
    },
    {
        "label": "Slip C",
        "tag": "8-fold ~12x",
        "min_legs": 6,
        "max_legs": 10,
        "odds_min": 5.00,
        "odds_max": 20.0,
        "risk": "HIGH",
        "stake_suggestion": 200,
    },
]

# ── Helpers ──────────────────────────────────────────────────────────────────────────────────────
def _combined_odds(legs: list) -> float:
    return round(prod(l["odds"] for l in legs), 3)


def _is_diverse_enough(legs: list, strict: bool = True) -> bool:
    """
    Diversity guard:
      strict=True  — require at least 2 different sports
      strict=False — allow any sport mix (single-sport fallback)
    Football legs are limited to max 60% of the slip to avoid football-only accas.
    """
    sports = [l["sport"] for l in legs]
    fb_count = sports.count("Football")
    sport_types = len(set(sports))
    n = len(legs)
    max_fb = max(2, round(n * 0.6))
    if fb_count > max_fb:
        return False
    if strict:
        return sport_types >= 2
    return True


def _build_one_slip(pool: list, tier: dict) -> dict | None:
    """
    3-pass combo search:
      Pass 1: strict diversity + exact odds band
      Pass 2: relaxed diversity + exact odds band
      Pass 3: relaxed diversity + odds_min lowered 20%
    Returns the combo whose combined odds sit closest to the band midpoint.
    """
    target_mid = (tier["odds_min"] + tier["odds_max"]) / 2

    def _search(strict: bool, odds_min: float, odds_max: float) -> list | None:
        best = None
        best_dist = float("inf")
        for n in range(tier["min_legs"], tier["max_legs"] + 1):
            for combo in combinations(pool, n):
                legs = list(combo)
                co = _combined_odds(legs)
                if odds_min <= co <= odds_max and _is_diverse_enough(legs, strict):
                    dist = abs(co - target_mid)
                    if dist < best_dist:
                        best_dist = dist
                        best = legs
        return best

    best = _search(strict=True,  odds_min=tier["odds_min"], odds_max=tier["odds_max"])
    if best is None:
        best = _search(strict=False, odds_min=tier["odds_min"], odds_max=tier["odds_max"])
    if best is None:
        relaxed_min = round(tier["odds_min"] * 0.80, 3)
        best = _search(strict=False, odds_min=relaxed_min, odds_max=tier["odds_max"])
    if best is None:
        return None

    combined = _combined_odds(best)
    stake = tier["stake_suggestion"]
    return {
        "label":           tier["label"],
        "tag":             tier["tag"],
        "risk":            tier["risk"],
        "legs":            best,
        "n_legs":          len(best),
        "combined_odds":   combined,
        "stake":           stake,
        "potential_payout": round(combined * stake, 2),
        "sports_mix":      _describe_mix(best),
    }


def _describe_mix(legs: list) -> str:
    """e.g. 'Football×2 + Basketball×1 + Tennis×1'"""
    from collections import Counter
    counts = Counter(l["sport"] for l in legs)
    return " + ".join(f"{sport}×{cnt}" for sport, cnt in counts.items())


# ── Public interface ──────────────────────────────────────────────────────────────────────────────────────
def build_slips(
    football_edges: list,
    basketball_edges: list,
    tennis_edges: list,
) -> list[dict]:
    """
    Build all three slip tiers from available edge selections.
    Each tier independently searches the full pool — legs are not consumed.

    Pool: top 8 Football + top 6 Basketball + top 6 Tennis = up to 20 candidates.
    Sorted ascending by odds (lowest-risk legs tried first in combos).
    """
    pool = (
        football_edges[:8] +
        basketball_edges[:6] +
        tennis_edges[:6]
    )
    pool.sort(key=lambda x: x["odds"])

    print(f"[slip_builder] Pool size: {len(pool)} "
          f"(FB:{len(football_edges[:8])} "
          f"BB:{len(basketball_edges[:6])} "
          f"TN:{len(tennis_edges[:6])})")

    slips = []
    for tier in SLIP_TARGETS:
        slip = _build_one_slip(pool, tier)
        if slip:
            slips.append(slip)
            print(f"  ✅ {tier['label']} built: {slip['combined_odds']}× odds, "
                  f"{slip['n_legs']} legs [{slip['sports_mix']}]")
        else:
            print(f"  ⚠️ {tier['label']} — no combination hit target band "
                  f"{tier['odds_min']}–{tier['odds_max']} "
                  f"(pool has {len(pool)} legs)")
    return slips
