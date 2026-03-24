import os
import time
import logging
from scanner.fetcher import fetch_all_sports
from scanner.strategy import filter_edges
from scanner.slip_builder import build_slips
from scanner.logger import log_picks
from scanner.notifier import send_telegram

logging.basicConfig(
  level=logging.INFO,
  format="%(asctime)s [%(levelname)s] %(message)s",
  datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)


def run_once():
  """Single scan cycle: fetch -> filter -> build -> log -> notify."""
  log.info("Starting SportyBet scanner cycle...")

  # Fetch fixtures for all sports
  raw = fetch_all_sports()
  total = sum(len(v) for v in raw.values())
  log.info("Fetched %d total fixtures across all sports.", total)

  if not total:
    log.warning("No fixtures fetched - skipping cycle.")
    send_telegram([])
    return

  # Filter for value edges
  edges = filter_edges(raw)
  n_edges = sum(len(v) for v in edges.values())
  log.info("Found %d edge picks total (FB=%d, BB=%d, TN=%d).",
    n_edges,
    len(edges.get("football", [])),
    len(edges.get("basketball", [])),
    len(edges.get("tennis", [])),
  )

  # Build tiered slips
  slips = build_slips(
    football_edges=edges.get("football", []),
    basketball_edges=edges.get("basketball", []),
    tennis_edges=edges.get("tennis", []),
  )
  log.info("Built %d slip(s): %s", len(slips), [s['label'] for s in slips])

  # Log picks to JSON history
  log_picks(slips)

  # Send Telegram notifications
  send_telegram(slips)

  scan_interval = int(os.environ.get("SCAN_INTERVAL_SECONDS", "300"))
  log.info("Cycle complete. Next run in %ds.", scan_interval)


def main():
  """Entry point - runs continuously with configurable interval."""
  scan_interval = int(os.environ.get("SCAN_INTERVAL_SECONDS", "300"))
  runs = int(os.environ.get("MAX_RUNS", "0"))  # 0 = infinite
  count = 0

  while True:
    try:
      run_once()
    except Exception as exc:
      log.error("Unhandled error in scan cycle: %s", exc, exc_info=True)

    count += 1
    if runs and count >= runs:
      log.info("Reached MAX_RUNS=%d. Exiting.", runs)
      break

    log.info("Sleeping %ds before next cycle...", scan_interval)
    time.sleep(scan_interval)


if __name__ == "__main__":
  main()
