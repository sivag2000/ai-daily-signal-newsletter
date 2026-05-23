# Daily AI News Scheduler Setup Guide

Welcome! This project is a Python-based automatic scheduler that runs every day at 6:00 PM to scrape the latest AI-related news articles, search for today's top AI YouTube videos, save them to Google Sheets, email you a summary, and back up a text file to your Windows Desktop.

Since you are a beginner, this guide will walk you through every single step required to get this working from scratch!

---

## Prerequisites: Install Python on Windows

1. **Download Python**: Go to the official website [python.org/downloads](https://www.python.org/downloads/) and click the yellow **Download Python** button.
2. **Install Python**: Double-click the downloaded `.exe` installer.
   > [!IMPORTANT]
   > On the first installer screen, make sure to check the box that says **"Add python.exe to PATH"** at the bottom. This allows you to run Python from your command prompt.
3. Click **Install Now** and wait for the setup to complete.

---

## Step 1: Connect Gmail (Enable App Password)

Google does not allow automated scripts to log in to your account with your normal password. To allow Python to send emails, you need to create an **App Password**:

1. Go to your **Google Account** settings (https://myaccount.google.com/).
2. Click on **Security** on the left menu.
3. Under *How you sign in to Google*, make sure **2-Step Verification** is turned **ON**. (If not, set it up first).
4. Click on **2-Step Verification**. Scroll down to the bottom of the page and click **App passwords**.
5. Enter a name for your app (e.g., `AI News Scheduler`).
6. Click **Create**. Google will show you a **16-character password** (e.g., `abcd efgh ijkl mnop`).
7. **Copy this password!** You will put this in your `config.json` as `gmail_app_password`.
   > [!NOTE]
   > Do not include spaces when copying it; copy it as a single string of 16 characters.

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
Make sure you have edited `config.json` with Notepad or VS Code, pasting your YouTube API key, Gmail details, and ensuring `google_credentials.json` is present in the workspace.

### 5. Running and Testing
You can run the script in two modes:

* **Test Immediately (Run Once Now)**:
  Run the script with the `--now` flag. This will run the collection immediately, save to Google Sheets, send the email, create the desktop backup, and exit.
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

## Troubleshooting Common Errors

* **ModuleNotFoundError**: Run `pip install -r requirements.txt` again. Make sure your virtual environment `(venv)` is active.
* **gspread.exceptions.SpreadsheetNotFound**: Make sure you shared the Google Sheet with the Service Account email (`client_email`) and that the sheet name in `config.json` matches the actual Google Sheet title exactly.
* **smtplib.SMTPAuthenticationError**: Check that your Gmail App Password is correct, that 2-Step Verification is active, and that you are using a 16-character App Password (not your personal password).
* **API key not valid / YouTube quota exceeded**: Ensure the YouTube API key in `config.json` is entered correctly and that you have enabled `YouTube Data API v3` in the Google Cloud Console.
