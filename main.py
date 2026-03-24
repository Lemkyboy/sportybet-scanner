import os
import time
import logging
from scanner.fetcher import SportyBetFetcher
from scanner.strategy import EdgeStrategy
from scanner.slip_builder import SlipBuilder
from scanner.logger import PickLogger
from scanner.notifier import TelegramNotifier

logging.basicConfig(
  level=logging.INFO,
  format="%(asctime)s [%(levelname)s] %(message)s",
  datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)


def run_once():
  """Single scan cycle: fetch → filter → build → log → notify."""
  token = os.environ["TELEGRAM_BOT_TOKEN"]
  chat_id = os.environ["TELEGRAM_CHAT_ID"]
  scan_interval = int(os.environ.get("SCAN_INTERVAL_SECONDS", "300"))

  fetcher = SportyBetFetcher()
  strategy = EdgeStrategy()
  builder = SlipBuilder()
  logger = PickLogger()
  notifier = TelegramNotifier(token=token, chat_id=chat_id)

  log.info("Starting SportyBet scanner cycle...")

  # Fetch fixtures for all supported sports
  all_fixtures = []
  for sport in ["football", "basketball", "tennis"]:
    try:
      fixtures = fetcher.get_fixtures(sport=sport)
      log.info("Fetched %d %s fixtures.", len(fixtures), sport)
      all_fixtures.extend(fixtures)
    except Exception as exc:
      log.warning("Failed to fetch %s fixtures: %s", sport, exc)

  if not all_fixtures:
    log.warning("No fixtures fetched — skipping cycle.")
    notifier.send_slips([])
    return

  # Filter for value edges
  edges = strategy.find_edges(all_fixtures)
  log.info("Found %d edge picks across all sports.", len(edges))

  # Build tiered slips
  slips = builder.build_slips(edges)
  log.info("Built %d slip(s): %s", len(slips), [s['tier'] for s in slips])

  # Log picks to JSON history
  for slip in slips:
    logger.log_slip(slip)

  # Send Telegram notifications
  notifier.send_slips(slips)
  log.info("Cycle complete. Next run in %ds.", scan_interval)


def main():
  """Entry point — runs continuously with configurable interval."""
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
