# Google OAuth Setup Guide

This guide walks you through setting up OAuth authentication for exporting dashboards to Google Docs and creating Google Slides presentations.

## Quick Setup (Automated)

Run the interactive setup script:

```bash
python setup_google_oauth.py
```

This script will guide you through all the steps below and test the OAuth flow.

## Manual Setup

### Step 1: Create Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Note your project name

### Step 2: Enable Required APIs

Enable these APIs in your project:

1. Go to [API Library](https://console.cloud.google.com/apis/library)
2. Search for and enable:
   - **Google Docs API**
   - **Google Drive API**
   - **Google Slides API** (optional, for presentation exports)

### Step 3: Configure OAuth Consent Screen

1. Go to [OAuth consent screen](https://console.cloud.google.com/apis/credentials/consent)
2. Choose **External** (for personal use) or **Internal** (for Google Workspace)
3. Fill in required fields:
   - **App name**: Ticket Dashboard
   - **User support email**: Your email
   - **Developer contact**: Your email
4. Click "Save and Continue"
5. On the Scopes screen, click "+ ADD OR REMOVE SCOPES"
6. Add these scopes:
   - `https://www.googleapis.com/auth/documents`
   - `https://www.googleapis.com/auth/drive.file`
   - `https://www.googleapis.com/auth/presentations` (optional)
7. Click "Update" then "Save and Continue"
8. If using External, add test users (your email address)
9. Click "Save and Continue" through remaining screens

### Step 4: Create OAuth 2.0 Credentials

1. Go to [Credentials](https://console.cloud.google.com/apis/credentials)
2. Click "**Create Credentials**" → "**OAuth client ID**"
3. Choose **Desktop app** as the application type
4. **Name**: Ticket Dashboard Desktop Client
5. Click "**Create**"
6. A dialog appears with your client ID and secret - you can close it

### Step 5: Configure Redirect URI

**This is the most important step!**

1. On the credentials page, find your new OAuth 2.0 Client ID
2. Click the **edit icon** (pencil) next to it
3. Under "**Authorized redirect URIs**", click "+ ADD URI"
4. Enter exactly: `http://localhost:9090/`
   - ⚠️ **Must include the trailing slash**: `http://localhost:9090/`
   - ⚠️ **Must use http, not https**
   - ⚠️ **Must use port 9090** (hardcoded in export_utils.py)
5. Click "**Save**"

**Common Mistakes:**
- ❌ `http://localhost:9090` (missing trailing slash)
- ❌ `https://localhost:9090/` (https instead of http)
- ❌ `http://localhost:8000/` (wrong port)
- ✅ `http://localhost:9090/` (correct)

### Step 6: Download Credentials

1. On the credentials page, find your OAuth 2.0 Client ID
2. Click the **download icon** (⬇) on the far right
3. This downloads a JSON file (usually named `client_secret_xxx.json`)
4. **Rename and move** this file to your project directory as: `credentials.json`

File location should be:
```
/data/dev/td/ticket-dashboard/credentials.json
```

### Step 7: Test OAuth Flow

Run the setup script to test:

```bash
python setup_google_oauth.py
```

Or test manually:

```bash
python -c "from export_utils import export_to_google_docs; print('OAuth test - browser will open...')"
```

The first time you run an export:
1. Your browser will open to Google's authorization page
2. Sign in with the Google account you added as a test user
3. Review and grant the requested permissions
4. You'll be redirected to `http://localhost:9090/`
5. A `token.json` file will be created automatically
6. You can close the browser tab

## Usage

### Export Dashboard to Google Docs

Using the web UI:
1. Generate a dashboard (ticket, chat, or combined analytics)
2. Click "Export to Google Docs"
3. First time: Browser opens for authentication
4. Subsequent times: Uses saved token automatically

Using the Python API:

```python
from export_utils import export_to_google_docs

html_content = "<html>...</html>"  # Your dashboard HTML
doc_url = export_to_google_docs(
    html_content,
    "My Dashboard Export",
    credentials_path='credentials.json'  # Optional, defaults to credentials.json
)

if doc_url:
    print(f"Document created: {doc_url}")
```

### Create Google Slides Presentation

```python
from google_slides_creator import create_presentation

slides_url = create_presentation(
    title="My Presentation",
    slides_data=[...],
    credentials_path='credentials.json'
)
```

## Files Created

After setup, you'll have these files:

- **`credentials.json`**: OAuth client credentials from Google Cloud Console
  - Contains client ID and client secret
  - Keep secure, don't commit to version control
  - Required for OAuth flow

- **`token.json`**: Access and refresh tokens
  - Created automatically after first successful authentication
  - Allows access without re-authenticating
  - Keep secure, don't commit to version control
  - Delete this file to force re-authentication

## Troubleshooting

### Error: "redirect_uri_mismatch"

**Problem**: The redirect URI doesn't match what's configured in Google Cloud Console.

**Solution**:
1. Go to [Credentials](https://console.cloud.google.com/apis/credentials)
2. Edit your OAuth 2.0 Client ID
3. Ensure redirect URI is exactly: `http://localhost:9090/`
4. Save changes
5. Wait 1-2 minutes for changes to propagate
6. Try again

### Error: "Access blocked: This app's request is invalid"

**Problem**: OAuth consent screen not configured or scopes missing.

**Solution**:
1. Complete OAuth consent screen configuration (Step 3 above)
2. Add your email as a test user (if using External)
3. Ensure all required scopes are added

### Error: "The user did not grant your application the requested scopes"

**Problem**: You didn't grant all permissions during authentication.

**Solution**:
1. Delete `token.json` file
2. Run the export again
3. When the browser opens, carefully review and accept all permissions

### Error: "Port 9090 already in use"

**Problem**: Another application is using port 9090.

**Solution**:
1. Find and stop the application using port 9090:
   ```bash
   lsof -i :9090
   kill <PID>
   ```
2. Or change the port in `export_utils.py` (lines 555, 829)
3. Update the redirect URI in Google Cloud Console to match

### Browser doesn't open automatically

**Problem**: Running in a headless environment or browser detection fails.

**Solution**:
1. The script will print a URL
2. Manually copy and paste the URL into your browser
3. Complete the authentication flow
4. Copy the authorization code from the final redirect
5. Paste it back into the terminal prompt

### "Invalid grant" or "Token expired" errors

**Problem**: The refresh token has expired or been revoked.

**Solution**:
1. Delete `token.json`
2. Re-authenticate by running an export

## Security Best Practices

1. **Never commit credentials to version control**:
   ```bash
   # Add to .gitignore
   credentials.json
   token.json
   ```

2. **Keep credentials secure**:
   - Don't share `credentials.json` or `token.json`
   - Store them in a secure location
   - Rotate credentials if compromised

3. **Use minimal scopes**:
   - Only request permissions you need
   - Current scopes: `documents`, `drive.file`, `presentations`

4. **For production deployment**:
   - Use service accounts instead of OAuth for server-to-server
   - Store credentials in environment variables or secret manager
   - Implement proper access controls

## Testing OAuth Setup

Test with the setup script:

```bash
python setup_google_oauth.py
```

Or test individual components:

```bash
# Test Google Docs export
python -c "
from export_utils import export_to_google_docs
url = export_to_google_docs('<html><body><h1>Test</h1></body></html>', 'Test Doc')
print(f'Success: {url}' if url else 'Failed')
"

# Test token refresh
python -c "
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
creds = Credentials.from_authorized_user_file('token.json')
creds.refresh(Request())
print('Token refresh successful')
"
```

## FAQ

**Q: Can I use the same credentials for multiple users?**

A: No, each user needs their own OAuth flow. The `token.json` is user-specific.

**Q: How long does the token last?**

A: Access tokens expire after 1 hour, but refresh tokens last indefinitely (unless revoked). The code automatically refreshes tokens.

**Q: Can I run this on a server without a browser?**

A: Yes, but you need to configure OAuth with a different flow (e.g., service account) or manually handle the authorization URL.

**Q: What if I want to change the port from 9090?**

A:
1. Edit `export_utils.py`, search for `port=9090` (2 occurrences)
2. Change to your desired port
3. Update the redirect URI in Google Cloud Console
4. Delete `token.json` to force re-authentication

**Q: Can I revoke access?**

A: Yes, go to [Google Account Permissions](https://myaccount.google.com/permissions) and remove "Ticket Dashboard" access.

## Additional Resources

- [Google OAuth 2.0 Documentation](https://developers.google.com/identity/protocols/oauth2)
- [Google Docs API Documentation](https://developers.google.com/docs/api)
- [Google Drive API Documentation](https://developers.google.com/drive/api)
- [Google Slides API Documentation](https://developers.google.com/slides/api)

## Support

If you encounter issues not covered in this guide:

1. Check the troubleshooting section above
2. Review error messages in the terminal
3. Verify all steps were completed correctly
4. Check Google Cloud Console for any error messages or warnings
