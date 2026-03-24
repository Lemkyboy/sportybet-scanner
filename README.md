# sportybet-scanner

Autonomous SportyBet edge scanner — fetches Football/Basketball/Tennis odds, filters value edges, and builds 3-tier accumulator slips (A/B/C) via Telegram.

## Features

- Fetches live fixtures from SportyBet's API for Football, Basketball, and Tennis
- Identifies value edges using implied probability vs market odds
- Builds 3 tiered accumulator slips:
  - **Slip A** — Low-risk, 3-5 legs, odds 1.50–3.50
  - **Slip B** — Mid-tier, 4-6 legs, odds 2.50–6.00
  - **Slip C** — High-value, 5-8 legs, odds 5.00–15.00
- Sends formatted HTML messages to Telegram
- Logs all picks to a JSON history file
- Runs automatically every 30 minutes via GitHub Actions

## Setup

### 1. Fork or clone this repo

### 2. Add GitHub Secrets

Go to **Settings > Secrets and variables > Actions** and add:

| Secret | Description |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Your Telegram bot token from @BotFather |
| `TELEGRAM_CHAT_ID` | Your Telegram chat/channel ID |

### 3. Enable GitHub Actions

The workflow in `.github/workflows/scanner.yml` runs automatically every 30 minutes.
You can also trigger it manually from the **Actions** tab using **workflow_dispatch**.

## Project Structure

```
sportybet-scanner/
├── .github/
│   └── workflows/
│       └── scanner.yml       # Scheduled GitHub Actions workflow
├── scanner/
│   ├── __init__.py
│   ├── fetcher.py            # SportyBet API client
│   ├── strategy.py           # Edge detection logic
│   ├── slip_builder.py       # 3-tier slip assembler
│   ├── logger.py             # JSON pick history logger
│   └── notifier.py           # Telegram message sender
├── main.py                   # Orchestrator entry point
├── requirements.txt
└── README.md
```

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | required | Telegram bot token |
| `TELEGRAM_CHAT_ID` | required | Target chat/channel ID |
| `SCAN_INTERVAL_SECONDS` | `300` | Seconds between cycles (local run) |
| `MAX_RUNS` | `0` (infinite) | Set to `1` for single-shot mode |

## Local Development

```bash
pip install -r requirements.txt
export TELEGRAM_BOT_TOKEN=your_token
export TELEGRAM_CHAT_ID=your_chat_id
export MAX_RUNS=1
python main.py
```
