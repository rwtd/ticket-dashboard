#!/usr/bin/env python3
"""
Google OAuth Setup Helper
Guides you through setting up OAuth credentials for Google Docs/Slides API access
"""

import os
import sys
import webbrowser
from pathlib import Path

def print_header(text):
    """Print formatted header"""
    print(f"\n{'='*70}")
    print(f"  {text}")
    print(f"{'='*70}\n")

def print_step(number, text):
    """Print formatted step"""
    print(f"\n[Step {number}] {text}")
    print("-" * 70)

def main():
    print_header("Google OAuth Setup for Ticket Dashboard")

    print("This script will guide you through setting up Google OAuth credentials")
    print("for exporting dashboards to Google Docs and Google Slides.")

    # Check if credentials already exist
    if os.path.exists('credentials.json'):
        print("\n✅ credentials.json already exists in the project directory")
        response = input("\nDo you want to reconfigure? (y/n): ")
        if response.lower() != 'y':
            print("\nSetup cancelled. Using existing credentials.json")
            sys.exit(0)

    print_step(1, "Create/Select Google Cloud Project")
    print("""
1. Go to: https://console.cloud.google.com/
2. Create a new project or select an existing one
3. Note your project name
    """)

    project_name = input("Enter your Google Cloud project name: ").strip()

    print_step(2, "Enable Required APIs")
    print("""
You need to enable the following APIs:
- Google Docs API
- Google Drive API
- Google Slides API (if you plan to create presentations)

Enable APIs at: https://console.cloud.google.com/apis/library
    """)

    input("Press Enter when APIs are enabled...")

    print_step(3, "Create OAuth 2.0 Credentials")
    print("""
1. Go to: https://console.cloud.google.com/apis/credentials
2. Click "Create Credentials" → "OAuth client ID"
3. If prompted, configure OAuth consent screen first:
   - User Type: External (for personal use) or Internal (for workspace)
   - App name: Ticket Dashboard
   - User support email: your email
   - Developer contact: your email
   - Add scopes: .../auth/documents, .../auth/drive.file, .../auth/presentations
   - Add test users (your email) if using External
4. Back to Create OAuth client ID:
   - Application type: Desktop app
   - Name: Ticket Dashboard Desktop Client
5. Click "Create"
    """)

    input("Press Enter when OAuth client is created...")

    print_step(4, "Configure Authorized Redirect URIs")
    print(f"""
IMPORTANT: You need to add this redirect URI to your OAuth client:

    http://localhost:9090/

Steps:
1. In the credentials page, find your OAuth 2.0 Client ID
2. Click the edit icon (pencil)
3. Under "Authorized redirect URIs", click "+ ADD URI"
4. Enter: http://localhost:9090/
5. Click "Save"

Note: The redirect URI MUST be exactly: http://localhost:9090/
      (with the trailing slash)
    """)

    input("Press Enter when redirect URI is configured...")

    print_step(5, "Download Credentials")
    print("""
1. On the credentials page, find your OAuth 2.0 Client ID
2. Click the download icon (⬇) on the right side
3. This downloads a JSON file (usually named like: client_secret_xxx.json)
4. Save it to this project directory as: credentials.json
    """)

    # Wait for file
    while not os.path.exists('credentials.json'):
        response = input("\nHave you saved credentials.json to this directory? (y/n): ")
        if response.lower() == 'y':
            if not os.path.exists('credentials.json'):
                print("❌ File not found. Please ensure credentials.json is in:")
                print(f"   {os.getcwd()}")
            else:
                break
        else:
            print("\nPlease download and save the credentials file as 'credentials.json'")

    print("\n✅ credentials.json found!")

    print_step(6, "Test OAuth Flow")
    print("""
Now let's test the OAuth authentication flow.
This will:
1. Open your browser for Google authentication
2. Create a token.json file (stores your access token)
3. Test creating a simple Google Doc
    """)

    response = input("\nRun test now? (y/n): ")
    if response.lower() == 'y':
        print("\nRunning OAuth test...")
        try:
            from export_utils import export_to_google_docs

            test_html = """
            <html>
            <head><title>Test Dashboard Export</title></head>
            <body>
            <h1>Test Dashboard</h1>
            <p>This is a test export from the Ticket Dashboard.</p>
            <p>If you can see this, OAuth is working correctly!</p>
            </body>
            </html>
            """

            print("\n🔐 Opening browser for Google authentication...")
            print("Please sign in and grant permissions.")

            doc_url = export_to_google_docs(
                test_html,
                "Ticket Dashboard OAuth Test",
                credentials_path='credentials.json'
            )

            if doc_url:
                print(f"\n✅ Success! Test document created:")
                print(f"   {doc_url}")
                print("\n✅ OAuth setup complete!")
                print("\nYou can now:")
                print("- Export dashboards to Google Docs")
                print("- Create Google Slides presentations")
                print("- The token.json file has been saved for future use")
            else:
                print("\n❌ OAuth test failed. Check the error messages above.")

        except ImportError as e:
            print(f"\n❌ Missing required packages: {e}")
            print("Install with: pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib")
        except Exception as e:
            print(f"\n❌ OAuth test failed: {e}")
            print("\nCommon issues:")
            print("1. Make sure redirect URI is exactly: http://localhost:9090/")
            print("2. Ensure all required APIs are enabled")
            print("3. Check that you granted all requested permissions")
    else:
        print("\nSetup complete. You can test OAuth later by running:")
        print("  python setup_google_oauth.py")

    print_header("Setup Complete")
    print("""
Your OAuth credentials are now configured!

Files created:
- credentials.json (OAuth client credentials - keep secure)
- token.json (access token - created after authentication)

Next steps:
1. Use the web UI to export dashboards to Google Docs
2. The first export will open a browser for authentication
3. Subsequent exports will use the saved token

For Google Slides presentations, you'll use the same credentials.
    """)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nSetup cancelled by user.")
        sys.exit(1)
