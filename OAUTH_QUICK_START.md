# OAuth Quick Start - 5 Minutes

## TL;DR

```bash
# 1. Run setup script
python setup_google_oauth.py

# 2. Follow the prompts to:
#    - Enable APIs (Docs, Drive, Slides)
#    - Create OAuth client (Desktop app)
#    - Add redirect URI: http://localhost:9090/
#    - Download credentials.json
#    - Test authentication

# 3. Done! Now you can export to Google Docs/Slides
```

## Critical Steps

### 1. Google Cloud Console Setup (3 minutes)

**Enable APIs**: https://console.cloud.google.com/apis/library
- ✅ Google Docs API
- ✅ Google Drive API
- ✅ Google Slides API

**Create OAuth Credentials**: https://console.cloud.google.com/apis/credentials
1. Click "Create Credentials" → "OAuth client ID"
2. Configure consent screen if needed (add your email as test user)
3. Choose "Desktop app"
4. Click "Create"

### 2. Configure Redirect URI ⚠️ CRITICAL

Edit your OAuth client and add **exactly** this URI:

```
http://localhost:9090/
```

**Must have**:
- ✅ `http://` (not https)
- ✅ Port `9090`
- ✅ Trailing slash `/`

### 3. Download Credentials

1. Download the OAuth client JSON file
2. Save as `credentials.json` in your project directory

### 4. Test It

```bash
python setup_google_oauth.py
```

Browser will open → Sign in → Grant permissions → Done!

## Files You'll Have

- `credentials.json` - OAuth client credentials (from Google Cloud Console)
- `token.json` - Access token (created automatically after first auth)

**Don't commit these to git!**

## Troubleshooting

**❌ "redirect_uri_mismatch"**
→ Check the redirect URI is exactly `http://localhost:9090/`

**❌ "Access blocked"**
→ Add your email as a test user in OAuth consent screen

**❌ "Port already in use"**
→ Kill the process on port 9090: `lsof -i :9090`

## Full Documentation

See [GOOGLE_OAUTH_SETUP.md](GOOGLE_OAUTH_SETUP.md) for complete details.

## Usage After Setup

### Export Dashboard to Google Docs

Via web UI:
1. Generate dashboard
2. Click "Export to Google Docs"
3. Browser opens (first time only)
4. Document URL returned

Via Python:
```python
from export_utils import export_to_google_docs

doc_url = export_to_google_docs(
    html_content="<html>...</html>",
    document_title="My Dashboard"
)
print(doc_url)
```

### Create Google Slides Presentation

```python
from google_slides_creator import create_presentation

slides_url = create_presentation(
    title="Customer Analysis",
    slides_data=[...],
    credentials_path='credentials.json'
)
```

## Next Steps

Once OAuth is working:
1. Export your dashboards to Google Docs ✅
2. Create customer presentations with Google Slides ✅
3. Share documents with your team ✅

All set! 🚀
