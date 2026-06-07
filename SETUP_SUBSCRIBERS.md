# Subscriber Setup — Email + Telegram

This guide connects the website's **Subscribe** box to real delivery. Do it once.

There are two channels and they work differently:

| Channel | How someone subscribes | Where the list lives |
|---|---|---|
| **Telegram** | Taps your bot and sends `/start` | `subscribers/telegram.json` (auto-managed) |
| **Email** | Fills the form on the website | `EmailSubscribers` tab in your Google Sheet |

---

## Part 1 — Telegram (5 minutes, no external service)

Telegram is almost automatic. The scheduler checks who has messaged your bot and adds them to the broadcast list every run.

1. **Find your bot's public username.** In Telegram, open **@BotFather → /mybots → (your bot)**. The link looks like `https://t.me/AiDailySignalBot`.
2. **Put that link in the website.** Open `docs/index.html`, find this line near the top of the `<script>`:
   ```js
   const TELEGRAM_BOT_URL = 'https://t.me/YOUR_BOT_USERNAME';
   ```
   Replace `YOUR_BOT_USERNAME` with your real bot username.
3. Done. When a visitor clicks **Join on Telegram**, they land on your bot and tap **Start**. On the next scheduler run they're added to `subscribers/telegram.json` and receive every edition.

> The list is committed back to the repo each run, so subscribers are never lost — even though Telegram only remembers `/start` messages for 24 hours.

---

## Part 2 — Email (about 10 minutes)

A static website can't store data, so the form hands sign-ups to a tiny Google Apps Script that writes them into your Sheet. The scheduler already reads that Sheet.

### Step A — Add the sign-up script to your Sheet
1. Open your Google Sheet named exactly **`AI News Daily Tracker`** (the name in `config.json → google_sheet_name`).
2. **Extensions → Apps Script.** Delete any sample code in the editor.
3. Open `google_apps_script_signup.gs` from this repo, copy **everything**, and paste it in. Click **Save**.

### Step B — Deploy it as a Web App
1. Click **Deploy → New deployment**.
2. Click the gear → choose **Web app**.
3. Set:
   - **Execute as:** Me
   - **Who has access:** **Anyone**
4. Click **Deploy**, then **Authorize access** and approve the permissions.
5. Copy the **Web app URL** (it ends in `/exec`).

### Step C — Connect the website
Open `docs/index.html`, find:
```js
const SIGNUP_ENDPOINT = 'YOUR_APPS_SCRIPT_WEB_APP_URL';
```
Paste your `/exec` URL between the quotes.

### Step D — Let the scheduler send email
Email delivery needs a working Gmail App Password (the current `config.json` has placeholders):
1. Create one at **myaccount.google.com → Security → App passwords** (requires 2-Step Verification).
2. In **GitHub → repo Settings → Secrets and variables → Actions**, the scheduler reads Gmail creds from `config.json` via the `CONFIG_JSON` secret. Update that secret's `gmail_sender`, `gmail_app_password`, and `gmail_receiver` with real values.
3. Make sure the **service account** (from `google_credentials.json`) has at least **Viewer** access to the Sheet — share the Sheet with the service-account email so the scheduler can read `EmailSubscribers`.

> Gmail allows ~500 emails/day — plenty to start. If the list grows large, switch to a sending service (e.g. SendGrid/Mailgun) later.

---

## How a daily run flows

```
scheduler.py --now
   ├─ generates the edition (Gemini)
   ├─ load_email_subscribers()      → reads EmailSubscribers tab
   ├─ send_summary_email(...)        → one BCC email to all subscribers + owner
   ├─ update_telegram_subscribers()  → adds new /start users, saves telegram.json
   └─ send_telegram(...)             → broadcasts to every Telegram subscriber
```

## Quick test
- **Telegram:** send `/start` to your bot, then run `python scheduler.py --now`. You should see `New Telegram subscriber:` in the logs and receive the message.
- **Email:** submit the website form, confirm a row appears in the `EmailSubscribers` tab, then run the scheduler and check your inbox.
