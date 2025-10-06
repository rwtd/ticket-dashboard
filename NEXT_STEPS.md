# 🚀 Next Steps - Google OAuth Setup

## What I've Done ✅

I've created a complete OAuth authentication system for your Ticket Dashboard:

1. ✅ **OAuth callback handler** with local server (port 9090)
2. ✅ **Setup wizard** (`setup_google_oauth.py`)
3. ✅ **Test script** (`test_oauth_setup.py`)
4. ✅ **Complete documentation** (OAUTH_QUICK_START.md, GOOGLE_OAUTH_SETUP.md)
5. ✅ **Updated README** with OAuth instructions

## What You Need to Do 🎯

### Step 1: Enable Google APIs (2 minutes)

Go to: https://console.cloud.google.com/apis/library

Enable these APIs:
- [x] Google Docs API
- [x] Google Drive API
- [x] Google Slides API

### Step 2: Create OAuth Credentials (2 minutes)

Go to: https://console.cloud.google.com/apis/credentials

1. Click "**Create Credentials**" → "**OAuth client ID**"
2. Configure consent screen (if prompted):
   - User Type: **External**
   - App name: **Ticket Dashboard**
   - Add your email as test user
3. Application type: **Desktop app**
4. Name: **Ticket Dashboard Desktop Client**
5. Click "**Create**"

### Step 3: Configure Redirect URI ⚠️ CRITICAL (1 minute)

**This is the most important step!**

1. Edit your OAuth client (pencil icon)
2. Under "**Authorized redirect URIs**", add:
   ```
   http://localhost:9090/
   ```
   ⚠️ Must include the trailing slash: `/`
3. Click "**Save**"

### Step 4: Download Credentials (1 minute)

1. Click the download icon (⬇) next to your OAuth client
2. Rename the file to: `credentials.json`
3. Move it to: `/data/dev/td/ticket-dashboard/credentials.json`

### Step 5: Run Setup Wizard

```bash
cd /data/dev/td/ticket-dashboard
python setup_google_oauth.py
```

This will:
- ✅ Verify credentials.json exists
- ✅ Open your browser for authentication
- ✅ Create token.json automatically
- ✅ Test by creating a sample Google Doc

## Quick Commands

```bash
# Run interactive setup
python setup_google_oauth.py

# Test existing OAuth setup
python test_oauth_setup.py

# Manual test
python -c "from export_utils import export_to_google_docs; print('Ready to test!')"
```

## Expected Flow

1. **Run setup script** → Browser opens
2. **Sign in to Google** → Grant permissions
3. **Browser redirects** → localhost:9090 (success page)
4. **Script confirms** → Test document created
5. **Done!** → Export dashboards anytime

## Files After Setup

```
/data/dev/td/ticket-dashboard/
├── credentials.json    ← You create (from Google Cloud Console)
├── token.json         ← Auto-created (after first auth)
├── setup_google_oauth.py
├── test_oauth_setup.py
└── export_utils.py    ← Uses OAuth (already configured)
```

## What Happens Next

Once OAuth is set up, you can:

1. **Export dashboards to Google Docs**
   - Generate analytics dashboard
   - Click "Export to Google Docs"
   - Document URL returned instantly

2. **Create Google Slides presentations**
   - Parse customer data
   - Generate presentation slides
   - Create slides in Google Slides automatically

3. **All automatic**
   - No browser prompts after first auth
   - Token refreshes automatically
   - Works seamlessly in background

## Troubleshooting

If you get stuck:

1. **Check the guides**:
   - Quick: [OAUTH_QUICK_START.md](OAUTH_QUICK_START.md)
   - Detailed: [GOOGLE_OAUTH_SETUP.md](GOOGLE_OAUTH_SETUP.md)

2. **Run diagnostics**:
   ```bash
   python test_oauth_setup.py
   ```

3. **Common issues**:
   - ❌ redirect_uri_mismatch → Check URI is exactly `http://localhost:9090/`
   - ❌ Access blocked → Add your email as test user
   - ❌ Port in use → `lsof -i :9090` and kill process

## Documentation

| File | Purpose |
|------|---------|
| [OAUTH_QUICK_START.md](OAUTH_QUICK_START.md) | 5-minute quick reference |
| [GOOGLE_OAUTH_SETUP.md](GOOGLE_OAUTH_SETUP.md) | Complete setup guide with troubleshooting |
| [OAUTH_SETUP_COMPLETE.md](OAUTH_SETUP_COMPLETE.md) | Implementation overview |
| [README.md](README.md#3-google-oauth-setup-for-docsslides-export) | Quick start section |

## Ready to Start?

```bash
python setup_google_oauth.py
```

**Estimated time: 5 minutes** ⏱️

Once complete, you'll be able to export dashboards to Google Docs and create customer presentations with Google Slides! 🎉
