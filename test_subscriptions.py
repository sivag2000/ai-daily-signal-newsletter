"""
Manual test harness for EMAIL + TELEGRAM subscription delivery.

Why this exists: it lets you confirm delivery works BEFORE committing, and it
reads every credential from ENVIRONMENT VARIABLES so nothing secret is ever
written to disk or committed. It does NOT scrape the web or call Gemini — it
sends a short, clearly-marked TEST edition so it is fast and safe.

------------------------------------------------------------------
USAGE (PowerShell on your machine)
------------------------------------------------------------------
# --- Telegram only ---
$env:TELEGRAM_BOT_TOKEN = "123456:ABC...your bot token..."
python test_subscriptions.py --telegram
#   (first send /start to your bot in Telegram, then run the line above)

# --- Email only (sends a test edition to YOUR inbox) ---
$env:GMAIL_SENDER = "you@gmail.com"
$env:GMAIL_APP_PASSWORD = "xxxx xxxx xxxx xxxx"   # a Gmail App Password, not your login password
python test_subscriptions.py --email --to you@gmail.com

# --- Both at once ---
python test_subscriptions.py --telegram --email --to you@gmail.com
------------------------------------------------------------------

Notes:
- Telegram: broadcasts to everyone who has /start-ed the bot (and your own chat
  id if you set TELEGRAM_CHAT_ID). Their ids are saved to subscribers/telegram.json.
- Email: by design this only emails the --to address you pass (your own inbox),
  so a test never spams real subscribers. It will, however, READ and report how
  many email subscribers are in your Google Sheet if google_credentials.json is
  present — read-only, nobody is emailed except --to.
"""

import os
import sys
import scheduler  # Reuse the real delivery functions so we test the actual code path.


SAMPLE = """# Test Edition — Delivery Check

**Issue #TEST · Subscription Test**

*This is a one-off test message to confirm delivery is working.*

## TL;DR
- If you can read this on Telegram or in your inbox, delivery works.
- This was sent by test_subscriptions.py, not the daily scheduler.
- You can safely ignore it.

## THE SIGNAL
Everything is wired correctly. Reply if you received this.

Subject: AI Daily Signal — Delivery Test
"""


def build_config():
    """Assemble a config dict purely from environment variables (no secrets on disk)."""
    return {
        "gmail_sender": os.environ.get("GMAIL_SENDER", "your_email@gmail.com"),
        "gmail_app_password": os.environ.get("GMAIL_APP_PASSWORD", "your_gmail_app_password"),
        "gmail_receiver": os.environ.get("GMAIL_RECEIVER", ""),
        "google_sheet_name": os.environ.get("GOOGLE_SHEET_NAME", "AI News Daily Tracker"),
        "google_credentials_file": os.environ.get("GOOGLE_CREDENTIALS_FILE", "google_credentials.json"),
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


def test_email(config, to_addr):
    print("\n=== EMAIL TEST ===")
    if config["gmail_sender"] == "your_email@gmail.com" or config["gmail_app_password"] == "your_gmail_app_password":
        print("SKIP: set $env:GMAIL_SENDER and $env:GMAIL_APP_PASSWORD first.")
        return
    if not to_addr:
        print("SKIP: pass --to your@email.com so the test only emails you.")
        return
    # Read-only: report how many real subscribers are in the Sheet (nobody is emailed but --to).
    try:
        subs = scheduler.load_email_subscribers(config)
        print(f"(info) Google Sheet currently lists {len(subs)} email subscriber(s).")
    except Exception as e:
        print(f"(info) Could not read Sheet subscribers (fine for this test): {e}")
    # Send the test edition only to the --to address.
    config = dict(config, gmail_receiver=to_addr)
    scheduler.send_summary_email(config, [], [], SAMPLE, [])  # recipients=[] => goes to gmail_receiver only


def main():
    args = sys.argv[1:]
    do_telegram = "--telegram" in args
    do_email = "--email" in args
    to_addr = ""
    if "--to" in args:
        i = args.index("--to")
        if i + 1 < len(args):
            to_addr = args[i + 1]
    if not (do_telegram or do_email):
        print(__doc__)
        return
    config = build_config()
    if do_telegram:
        test_telegram(config)
    if do_email:
        test_email(config, to_addr)
    print("\nDone.")


if __name__ == "__main__":
    main()
