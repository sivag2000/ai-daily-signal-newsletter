# Subscriber Setup — Telegram

Subscriptions are delivered over **Telegram**. There's nothing for a subscriber
to fill in — they just tap the bot and send `/start`, and the scheduler adds them
to the broadcast automatically.

| | |
|---|---|
| **How someone subscribes** | Taps the bot and sends `/start` |
| **Where the list lives** | A private `TelegramSubscribers` tab in your Google Sheet (never in the repo) |
| **What the website shows** | A "Join on Telegram" button linking to your bot |

> **Privacy:** subscriber chat IDs are stored in your private Google Sheet, not committed to
> this public repository. The scheduler reads/writes that tab automatically each run, so the
> list persists without ever being exposed. This requires the Google Sheets setup
> (service account + shared sheet) from `README.md` Step 3.

---

## One-time setup (about 2 minutes)

1. **Find your bot's public username.** In Telegram, open **@BotFather → /mybots → (your bot)**. The link looks like `https://t.me/Aidaikysignal_bot`.
2. **Make sure it's set in the website.** In `docs/index.html`, near the top of the `<script>`:
   ```js
   const TELEGRAM_BOT_URL = 'https://t.me/Aidaikysignal_bot';
   ```
   (Already set — only change it if your bot username changes.)
3. Done. When a visitor clicks **Join on Telegram**, they land on your bot and tap **Start**. On the next scheduler run they're added to the private `TelegramSubscribers` tab in your Google Sheet and receive every edition.

> The list is stored in your private Google Sheet (never in the repo), so subscribers are
> never lost — even though Telegram only remembers `/start` messages for 24 hours.

---

## How a daily run flows

```
scheduler.py --now
   ├─ generates the edition (Gemini)
   ├─ update_telegram_subscribers()  → adds new /start users to the private Google Sheet
   └─ send_telegram(...)             → broadcasts to every Telegram subscriber
```

## Quick test

```powershell
# In PowerShell, with the bot token from @BotFather:
$env:TELEGRAM_BOT_TOKEN = "123456:ABC...your token..."
python test_subscriptions.py --telegram
```

Send `/start` to your bot first, then run the command — you should see
`Telegram newsletter delivered to N/N subscriber(s).` and receive the test message.
