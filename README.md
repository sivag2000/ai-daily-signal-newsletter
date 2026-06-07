# Daily AI News Scheduler Setup Guide

Welcome! This project is a Python-based automatic scheduler that runs every day at 6:00 PM to scrape the latest AI-related news articles, search for today's top AI YouTube videos, save them to Google Sheets, generate a newsletter with Gemini, broadcast it to your Telegram subscribers, and back up a text file to your Windows Desktop.

Since you are a beginner, this guide will walk you through every single step required to get this working from scratch!

---

## Prerequisites: Install Python on Windows

1. **Download Python**: Go to the official website [python.org/downloads](https://www.python.org/downloads/) and click the yellow **Download Python** button.
2. **Install Python**: Double-click the downloaded `.exe` installer.
   > [!IMPORTANT]
   > On the first installer screen, make sure to check the box that says **"Add python.exe to PATH"** at the bottom. This allows you to run Python from your command prompt.
3. Click **Install Now** and wait for the setup to complete.

---

## Step 1: Connect Telegram (Create a Bot)

The newsletter is delivered to subscribers over **Telegram**. You need a bot:

1. In Telegram, open **@BotFather** and send `/newbot`.
2. Follow the prompts to name your bot and choose a username (it must end in `bot`).
3. BotFather gives you a **bot token** like `123456789:AAG...`. Keep it safe.
4. Add the token to GitHub Secrets as `TELEGRAM_BOT_TOKEN` (see Step 5). For local runs you can set `telegram_bot_token` in `config.json`.
5. Send `/start` to your bot so it can message you — your chat id is discovered automatically and saved to `subscribers/telegram.json`.
   > [!NOTE]
   > Anyone who taps your bot and sends `/start` is auto-subscribed on the next run. See `SETUP_SUBSCRIBERS.md` for details.

---

## Step 2: Get a YouTube Data API Key

To search YouTube programmatically, you need a free API Key from Google Cloud:

1. Visit the [Google Cloud Console](https://console.cloud.google.com/).
2. Log in with your Google account.
3. Click **Select a project** (top-left corner) and select **New Project**. Name it `AI News Tracker` and click **Create**.
4. Make sure your new project is selected in the top dropdown.
5. In the search bar at the top, type `YouTube Data API v3` and click on it.
6. Click the blue **Enable** button.
7. Once enabled, click the **Credentials** tab on the left menu.
8. Click **+ Create Credentials** at the top and select **API key**.
9. Your new API key will be displayed. Copy this key and save it in `config.json` as `youtube_api_key`.

---

## Step 2.5: Get a Free Gemini API Key (Optional)

To enable the custom newsletter generator using your expert editor prompt:
1. Visit [Google AI Studio](https://aistudio.google.com/).
2. Log in with your Google Account.
3. Click the blue **Get API key** button.
4. Click **Create API key**.
5. Copy the generated API key.
6. Open `config.json` and paste your key in `"gemini_api_key"`.
   *(If not set, the script will automatically fallback to the default text newsletter formatting).*

---

## Step 3: Connect Google Sheets (Service Account Credentials)

To allow the Python script to write to Google Sheets:

### 1. Create a Service Account in Google Cloud
1. Remaining in the Google Cloud Console, click the menu button (three horizontal lines) -> **IAM & Admin** -> **Service Accounts**.
2. Click **+ Create Service Account** at the top.
3. Enter a name (e.g., `sheets-scheduler`) and click **Create and Continue**.
4. Skip the optional role selection and click **Done**.
5. In the Service Accounts list, click on the service account you just created.
6. Go to the **Keys** tab, click **Add Key** -> **Create new key**.
7. Select **JSON** and click **Create**.
8. A credentials JSON file will download to your computer.
9. **Rename this downloaded file** to `google_credentials.json` and move it into the project directory (`e:\my project\daily scheduler`).

### 2. Enable Google Sheets and Drive APIs
1. In the Google Cloud search bar at the top, search for `Google Sheets API` and click **Enable**.
2. Search for `Google Drive API` and click **Enable**.

### 3. Share Your Google Sheet
1. Open Google Sheets (https://sheets.google.com) and create a **New Blank Spreadsheet**.
2. Name it exactly: `AI News Daily Tracker` (or choose another name and edit the `"google_sheet_name"` inside `config.json`).
3. Open your `google_credentials.json` file in a text editor (like Notepad) and look for the `"client_email"` field (it will look like `sheets-scheduler@...iam.gserviceaccount.com`). Copy that email address.
4. Go to your Google Sheet, click the green **Share** button in the top-right corner.
5. Paste the Service Account's email address, make sure the permission level is set to **Editor**, uncheck "Notify people", and click **Share**.

---

## Step 4: Run and Test the Script

### 1. Open Terminal/PowerShell
1. Click the Windows Start menu, type `cmd` or `PowerShell`, and open it.
2. Navigate to your project directory:
   ```cmd
   cd "e:\my project\daily scheduler"
   ```

### 2. Set Up a Virtual Environment (Recommended)
This isolates the project libraries so they don't interfere with other Python projects:
```cmd
python -m venv venv
```
Activate the virtual environment:
- On Windows (Command Prompt):
  ```cmd
  venv\Scripts\activate
  ```
- On Windows (PowerShell):
  ```powershell
  .\venv\Scripts\activate
  ```
*(You will see `(venv)` appear at the beginning of your terminal line).*

### 3. Install Requirements
Run the following command to install the required libraries:
```cmd
pip install -r requirements.txt
```

### 4. Configure details in `config.json`
Make sure you have edited `config.json` with Notepad or VS Code, pasting your YouTube API key and Telegram bot token, and ensuring `google_credentials.json` is present in the workspace.

### 5. Running and Testing
You can run the script in two modes:

* **Test Immediately (Run Once Now)**:
  Run the script with the `--now` flag. This will run the collection immediately, save to Google Sheets, broadcast to your Telegram subscribers, create the desktop backup, and exit.
  ```cmd
  python scheduler.py --now
  ```

* **Scheduling Mode (Run Daily at 6:00 PM)**:
  Run the script without any arguments. It will stay open, check the time, and run the collection automatically at 6:00 PM every day.
  ```cmd
  python scheduler.py
  ```
  *(Keep the terminal window open for the scheduler to continue running daily).*


---

## Step 5: Run in the Cloud for Free (Optional - GitHub Actions)

If you do not want to keep your laptop turned on and awake 24/7, you can host the scheduler completely for free in the cloud using **GitHub Actions**:

1. **Upload your project to GitHub**: Create a repository on GitHub and push your code files (your secrets in `config.json` and `google_credentials.json` are automatically hidden and ignored via `.gitignore` to keep them safe).
2. **Add GitHub Secrets**:
   * Open your GitHub repository in your web browser.
   * Go to **Settings** -> **Secrets and variables** -> **Actions**.
   * Click the **New repository secret** button.
   * Create a secret named **`CONFIG_JSON`** and paste the entire contents of your local `config.json` file as the value.
   * Click **New repository secret** again.
   * Create a secret named **`GOOGLE_CREDENTIALS_JSON`** and paste the entire contents of your local `google_credentials.json` file as the value.
3. **Enjoy Automatic Runs**:
   * The included `.github/workflows/daily_newsletter.yml` workflow file will automatically recreate the config files in the cloud using your secrets.
   * It will run the news collection every day at **6:00 PM IST (12:30 PM UTC)** completely in the cloud.
   * You can also trigger it manually at any time by going to the **Actions** tab on your GitHub repository, clicking **Daily AI News Scheduler** on the left, and clicking the **Run workflow** button.

---

## Troubleshooting Common Errors

* **ModuleNotFoundError**: Run `pip install -r requirements.txt` again. Make sure your virtual environment `(venv)` is active.
* **gspread.exceptions.SpreadsheetNotFound**: Make sure you shared the Google Sheet with the Service Account email (`client_email`) and that the sheet name in `config.json` matches the actual Google Sheet title exactly.
* **Telegram messages not arriving**: Make sure you sent `/start` to your bot, that `TELEGRAM_BOT_TOKEN` is set correctly, and that no webhook is configured on the bot (the scheduler uses `getUpdates`).
* **API key not valid / YouTube quota exceeded**: Ensure the YouTube API key in `config.json` is entered correctly and that you have enabled `YouTube Data API v3` in the Google Cloud Console.
