#!/usr/bin/env python3
"""Run this locally (not on the CT) to obtain a YouTube refresh token.

Prerequisites:
  1. Create a Google Cloud project at https://console.cloud.google.com/
  2. Enable the "YouTube Data API v3"
  3. Create OAuth 2.0 credentials of type "Desktop application"
  4. Note the Client ID and Client Secret
  5. pip install google-auth-oauthlib

Usage:
  python oauth_setup.py
"""

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/youtube"]


def main() -> None:
    print("Sign in with the Google account that owns the YouTube channel.\n")

    client_id = input("OAuth Client ID: ").strip()
    client_secret = input("OAuth Client Secret: ").strip()

    client_config = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    }

    flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
    creds = flow.run_local_server(port=0)

    print()
    print("=" * 60)
    print("Add these lines to /opt/tdillenbot/.env on the CT, then restart:")
    print("=" * 60)
    print(f"YOUTUBE_CLIENT_ID={client_id}")
    print(f"YOUTUBE_CLIENT_SECRET={client_secret}")
    print(f"YOUTUBE_REFRESH_TOKEN={creds.refresh_token}")
    print()
    print("Then: sudo systemctl restart tdillenbot")


if __name__ == "__main__":
    main()
