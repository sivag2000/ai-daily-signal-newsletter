"""
Manual test harness for TELEGRAM subscription delivery.

Why this exists: it lets you confirm Telegram delivery works BEFORE a real run,
and it reads the bot token from an ENVIRONMENT VARIABLE so nothing secret is
written to disk or committed. It does NOT scrape the web or call Gemini — it
sends a short, clearly-marked TEST edition so it is fast and safe.

------------------------------------------------------------------
USAGE (PowerShell on your machine)
------------------------------------------------------------------
$env:TELEGRAM_BOT_TOKEN = "123456:ABC...your bot token..."
python test_subscriptions.py --telegram
#   (first send /start to your bot in Telegram, then run the lines above)

# To also send to a specific chat id (e.g. your own) even before /start:
$env:TELEGRAM_CHAT_ID = "your_chat_id"
python test_subscriptions.py --telegram
------------------------------------------------------------------

Notes:
- Broadcasts to everyone who has /start-ed the bot (and TELEGRAM_CHAT_ID if set).
- Discovered ids are saved to subscribers/telegram.json.
- The token stays in your terminal session only; nothing is written to disk.
"""

import os
import sys
import scheduler  # Reuse the real delivery functions so we test the actual code path.


SAMPLE = """# Test Edition — Delivery Check

**Issue #TEST · Subscription Test**

*This is a one-off test message to confirm delivery is working.*

## TL;DR
- If you can read this on Telegram, delivery works.
- This was sent by test_subscriptions.py, not the daily scheduler.
- You can safely ignore it.

## THE SIGNAL
Everything is wired correctly. Reply if you received this.
"""


def build_config():
    """Assemble a minimal config from environment variables (no secrets on disk)."""
    return {
        "telegram_bot_token": os.environ.get("TELEGRAM_BOT_TOKEN", ""),
        "telegram_chat_id": os.environ.get("TELEGRAM_CHAT_ID", ""),
    }


def test_telegram(config):
    print("\n=== TELEGRAM TEST ===")
    if not config["telegram_bot_token"]:
        print("SKIP: set $env:TELEGRAM_BOT_TOKEN first.")
        return
    ids = scheduler.update_telegram_subscribers(config)
    if not ids:
        print("No subscribers found. In Telegram, send /start to your bot, then re-run.")
        return
    print(f"Broadcasting test edition to {len(ids)} chat(s): {ids}")
    scheduler.send_telegram(config, SAMPLE, ids)


def main():
    args = sys.argv[1:]
    if "--telegram" not in args:
        print(__doc__)
        return
    test_telegram(build_config())
    print("\nDone.")


if __name__ == "__main__":
    main()
