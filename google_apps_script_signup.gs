/**
 * AI Daily Signal — email sign-up endpoint (Google Apps Script)
 * ------------------------------------------------------------------
 * This tiny web app receives sign-ups from the website form and writes
 * them into the "EmailSubscribers" tab of THIS spreadsheet. The Python
 * scheduler then reads that tab and emails every subscriber each day.
 *
 * SETUP (one time, ~5 minutes — see SETUP_SUBSCRIBERS.md for screenshots-level detail):
 *   1. Open your Google Sheet named "AI News Daily Tracker".
 *   2. Extensions → Apps Script. Delete any sample code.
 *   3. Paste THIS entire file. Save.
 *   4. Deploy → New deployment → type "Web app".
 *        - Execute as: Me
 *        - Who has access: Anyone
 *   5. Authorize when prompted. Copy the Web app URL (ends in /exec).
 *   6. Paste that URL into docs/index.html as SIGNUP_ENDPOINT.
 */

function doPost(e) {
  try {
    var ss = SpreadsheetApp.getActiveSpreadsheet();           // The sheet this script is attached to.
    var sheet = ss.getSheetByName('EmailSubscribers');        // The subscribers tab.
    if (!sheet) {                                             // Create it the first time with headers.
      sheet = ss.insertSheet('EmailSubscribers');
      sheet.appendRow(['Timestamp', 'Email', 'Name', 'Source']);
    }

    var params = (e && e.parameter) ? e.parameter : {};
    var email = String(params.email || '').trim().toLowerCase();
    var name = String(params.name || '').trim();
    var source = String(params.source || 'website').trim();

    if (email && email.indexOf('@') > 0) {
      // De-duplicate: only add an email that isn't already in column B.
      var lastRow = sheet.getLastRow();
      var existing = [];
      if (lastRow > 1) {
        existing = sheet.getRange(2, 2, lastRow - 1, 1).getValues()
                        .map(function (r) { return String(r[0]).trim().toLowerCase(); });
      }
      if (existing.indexOf(email) === -1) {
        sheet.appendRow([new Date(), email, name, source]);
      }
    }

    return ContentService
      .createTextOutput(JSON.stringify({ ok: true }))
      .setMimeType(ContentService.MimeType.JSON);
  } catch (err) {
    return ContentService
      .createTextOutput(JSON.stringify({ ok: false, error: String(err) }))
      .setMimeType(ContentService.MimeType.JSON);
  }
}

function doGet() {
  // Visiting the URL in a browser shows this — handy to confirm the deployment is live.
  return ContentService.createTextOutput('AI Daily Signal sign-up endpoint is live.');
}
