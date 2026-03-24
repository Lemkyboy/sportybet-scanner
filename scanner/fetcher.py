"""
fetcher.py
SportyBet API client — reverse-engineered from the SportyBet Nigeria web app.

SportyBet exposes an internal REST API at:
  https://www.sportybet.com/api/ng/factsCenter/

Key endpoints discovered via Chrome DevTools:
  GET /api/ng/factsCenter/sportList
      → Returns list of sports with IDs
  GET /api/ng/factsCenter/tournamentsWithLiveCount?sportId={id}&gameType=0
      → Top-level tournament list for a sport
  GET /api/ng/factsCenter/fixtures?sportId={id}&marketId=1&gameType=0&page=1&pageSize=100
      → Paginated list of upcoming fixture summaries (includes home odds, draw, away)
  GET /api/ng/factsCenter/fixtureDetails?fixtureId={id}
      → Full market detail for a single fixture

Response shape (fixtures):
  {
    "bizCode": 0,
    "data": {
      "fixtures": [
        {
          "gameId": "1234567",
          "homeTeamName": "Man Utd",
          "awayTeamName": "Arsenal",
          "sportId": "sr:sport:1",
          "tournamentName": "Premier League",
          "estimateStartTime": 1700000000000,
          "markets": [
            {
              "id": "1",           # 1x2 / Match Winner
              "desc": "1x2",
              "outcomes": [
                {"id": "1", "desc": "1", "odds": "2.10"},   # Home win
                {"id": "2", "desc": "X", "odds": "3.40"},   # Draw
                {"id": "3", "desc": "2", "odds": "3.20"},   # Away win
              ]
            }
          ]
        }
      ]
    }
  }

Response shape (fixtureDetails):
  {
    "bizCode": 0,
    "data": {
      "fixture": {
        "gameId": ...,
        "markets": [ ... full market list with all outcomes ... ]
      }
    }
  }
"""
import time
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ── Base configuration ─────────────────────────────────────────────────────────────────────
BASE_URL = "https://www.sportybet.com/api/ng/factsCenter"

# SportyBet sport IDs (decoded from Chrome network panel)
SPORT_ID_FOOTBALL   = "sr:sport:1"
SPORT_ID_BASKETBALL = "sr:sport:2"
SPORT_ID_TENNIS     = "sr:sport:5"

# Market IDs used by SportyBet
MARKET_1X2          = "1"   # Football: Match Winner (Home / Draw / Away)
MARKET_DOUBLE_CHANCE = "10" # Football: Double Chance (1X / 12 / X2)
MARKET_OVER_UNDER   = "18" # Football: Goals Over/Under (Over 2.5)
MARKET_MONEYLINE    = "219" # Basketball / Tennis: Match Winner (Home / Away)
MARKET_HANDICAP     = "2"   # All sports: Handicap

HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": "https://www.sportybet.com",
    "Referer": "https://www.sportybet.com/ng/",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
}

REQUEST_TIMEOUT = 15  # seconds per request
MAX_RETRIES     = 3


def _make_session() -> requests.Session:
    """Create a session with retry logic."""
    session = requests.Session()
    retry = Retry(
        total=MAX_RETRIES,
        backoff_factor=1.0,
        status_forcelist=[429, 500, 502, 503, 504],
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.headers.update(HEADERS)
    return session


_session = _make_session()


def _get(path: str, params: dict | None = None) -> dict:
    """Low-level GET with error handling."""
    url = f"{BASE_URL}/{path}"
    try:
        resp = _session.get(url, params=params, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        if data.get("bizCode") != 0:
            print(f"[fetcher] SportyBet bizCode error: {data.get('bizCode')} on {url}")
            return {}
        return data.get("data") or {}
    except requests.exceptions.RequestException as exc:
        print(f"[fetcher] Request failed for {url}: {exc}")
        return {}


# ── Public fetch functions ───────────────────────────────────────────────────────────────────────

def fetch_fixtures(sport_id: str, page_size: int = 200) -> list[dict]:
    """
    Fetch upcoming pre-match fixtures for a given sport.
    Returns a list of raw fixture dicts from the SportyBet API.
    Paginates automatically until all fixtures are collected or
    until there are no more pages.
    """
    all_fixtures: list[dict] = []
    page = 1
    while True:
        data = _get("fixtures", params={
            "sportId": sport_id,
            "marketId": MARKET_1X2,
            "gameType": 0,   # 0 = pre-match
            "page": page,
            "pageSize": page_size,
        })
        fixtures = data.get("fixtures") or []
        all_fixtures.extend(fixtures)
        total = data.get("total") or 0
        if len(all_fixtures) >= total or not fixtures:
            break
        page += 1
        time.sleep(0.3)  # gentle rate-limit
    return all_fixtures


def fetch_fixture_detail(game_id: str) -> dict:
    """
    Fetch full market detail for a single fixture.
    Returns the fixture dict (with all markets), or {} on failure.
    """
    data = _get("fixtureDetails", params={"fixtureId": game_id})
    return data.get("fixture") or {}


def fetch_all_sports() -> dict[str, list[dict]]:
    """
    Fetch upcoming fixtures across Football, Basketball, and Tennis.
    Returns dict with keys 'football', 'basketball', 'tennis'.
    """
    print("[fetcher] Fetching Football fixtures...")
    football = fetch_fixtures(SPORT_ID_FOOTBALL)
    print(f"[fetcher]   Football: {len(football)} fixtures")

    print("[fetcher] Fetching Basketball fixtures...")
    basketball = fetch_fixtures(SPORT_ID_BASKETBALL)
    print(f"[fetcher]   Basketball: {len(basketball)} fixtures")

    print("[fetcher] Fetching Tennis fixtures...")
    tennis = fetch_fixtures(SPORT_ID_TENNIS)
    print(f"[fetcher]   Tennis: {len(tennis)} fixtures")

    return {
        "football":   football,
        "basketball": basketball,
        "tennis":     tennis,
    }


def safe_odds(outcome: dict) -> float | None:
    """Parse odds string from a SportyBet outcome dict. Returns float or None."""
    try:
        return float(outcome.get("odds") or 0) or None
    except (TypeError, ValueError):
        return None


def find_market(markets: list, market_id: str) -> dict | None:
    """Find a market by its string ID from a fixture's market list."""
    return next((m for m in markets if str(m.get("id")) == str(market_id)), None)
