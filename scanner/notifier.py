"""
notifier.py
Sends formatted Telegram messages for each slip tier.
Requires two GitHub Actions secrets:
  TELEGRAM_BOT_TOKEN  — your bot token from @BotFather
  TELEGRAM_CHAT_ID    — target chat / channel ID
"""
import os
import requests

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID", "")

RISK_EMOJI = {
    "LOW":    "🟢",
    "MEDIUM": "🟡",
    "HIGH":   "🔴",
}


def _send(text: str) -> bool:
    """Post a message to the configured Telegram chat. Returns True on success."""
    if not BOT_TOKEN or not CHAT_ID:
        print("[notifier] TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set — skipping send")
        return False
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    try:
        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        return True
    except requests.exceptions.RequestException as exc:
        print(f"[notifier] Telegram send failed: {exc}")
        return False


def _format_slip(slip: dict) -> str:
    """Build a rich HTML message for a single slip."""
    emoji = RISK_EMOJI.get(slip["risk"], "🟤")
    lines = [
        f"{emoji} <b>SportyBet — {slip['label']} ({slip['tag']})</b>",
        f"Risk: <b>{slip['risk']}</b>  |  Combined odds: <b>{slip['combined_odds']}×</b>",
        f"Sports mix: {slip['sports_mix']}",
        f"Stake suggestion: ₦{slip['stake']:,}  →  Potential payout: ₦{slip['potential_payout']:,.2f}",
        "",
        "<b>Legs:</b>",
    ]
    for i, leg in enumerate(slip["legs"], 1):
        lines.append(
            f"  {i}. [{leg['sport']}] {leg['match']}\n"
            f"     → {leg['market']} @ <b>{leg['odds']}</b>\n"
            f"     Tournament: {leg.get('tournament', 'N/A')}"
        )
    lines += [
        "",
        "⚡ Powered by SportyBet Scanner",
    ]
    return "\n".join(lines)


def send_telegram(slips: list[dict]) -> None:
    """
    Send one Telegram message per slip.
    If no slips are produced, sends a brief alert message instead.
    """
    if not slips:
        _send("⚠️ <b>SportyBet Scanner</b>: No qualifying edges found in this scan. Will retry next cycle.")
        return
    for slip in slips:
        msg = _format_slip(slip)
        ok = _send(msg)
        status = "sent" if ok else "FAILED"
        print(f"[notifier] {slip['label']} — Telegram {status}")
