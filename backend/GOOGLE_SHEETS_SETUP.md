# Google Sheets Service Account Setup Guide

## Quick Setup (No Google Cloud Project Needed)

If you don't want to set up a full Google Cloud project, you can use a simpler approach with your personal Google account. However, for production use, I recommend the service account approach below.

---

## Option 1: Service Account (Recommended for Production)

### Step 1: Create Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click "Select a project" → "New Project"
3. Name it "MapsScraper" → Click "Create"

### Step 2: Enable Google Sheets API

1. In the Cloud Console, go to "APIs & Services" → "Library"
2. Search for "Google Sheets API"
3. Click on it → Click "Enable"

### Step 3: Create Service Account

1. Go to "APIs & Services" → "Credentials"
2. Click "Create Credentials" → "Service Account"
3. Name: `maps-scraper-service`
4. Click "Create and Continue"
5. Skip role assignment (click "Continue")
6. Click "Done"

### Step 4: Create Service Account Key

1. Click on the service account you just created
2. Go to "Keys" tab
3. Click "Add Key" → "Create new key"
4. Choose "JSON" format
5. Click "Create"
6. **Save the downloaded JSON file as:**
   ```
   /backend/credentials/service_account.json
   ```

### Step 5: Share Google Sheet

1. Open the downloaded JSON file
2. Find the `client_email` field (looks like: `maps-scraper-service@project-id.iam.gserviceaccount.com`)
3. Copy this email address
4. Go to Google Sheets
5. Create a new sheet named "MapsScraperResults" (or the system will create it automatically)
6. Click "Share" button
7. Paste the service account email
8. Give it "Editor" permissions
9. Click "Send"

---

## Option 2: OAuth (Personal Account - Simpler but Less Secure)

If you prefer to use your personal Google account instead of a service account:

1. I can modify the code to use OAuth instead
2. You'll need to authorize the app once
3. Credentials will be stored locally
4. **Downside:** Requires manual re-authorization periodically

Let me know if you prefer this approach!

---

## Testing the Setup

Once you have the `service_account.json` file in place:

1. The scraper will automatically connect to Google Sheets on start
2. Check the logs for: `"Google Sheets connection established"`
3. If credentials are missing, it will fall back to local backup only

---

## Troubleshooting

### "Credentials file not found"
- Make sure the file is at: `/backend/credentials/service_account.json`
- Check file permissions (should be readable)

### "Permission denied" or "403 Forbidden"
- Make sure you shared the Google Sheet with the service account email
- Give it "Editor" permissions, not just "Viewer"

### "API not enabled"
- Go back to Google Cloud Console
- Enable both "Google Sheets API" and "Google Drive API"

---

## Security Notes

⚠️ **Never commit `service_account.json` to Git!**

The `.gitignore` file should already exclude it, but double-check:
```bash
# In /backend/.gitignore
credentials/
*.json
```

---

## What Happens Without Credentials?

If you don't set up Google Sheets:
- ✅ Scraper will still work
- ✅ Data will be saved to local Excel backup
- ❌ No cloud storage
- ❌ No real-time Google Sheets updates

The system is designed to work offline-first, so it's not required for basic functionality.
