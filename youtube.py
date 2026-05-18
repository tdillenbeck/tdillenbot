#!/usr/bin/env python3
"""Create a scheduled YouTube live broadcast."""

import datetime as dt
import os
from zoneinfo import ZoneInfo

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

# Edit these to change the broadcast metadata and schedule.
BROADCAST_TITLE = "Weekly Live Stream"
BROADCAST_DESCRIPTION = "Join us live!"
BROADCAST_PRIVACY = "public"  # "public", "unlisted", or "private"

# Schedule: weekday is Mon=0 ... Sun=6
BROADCAST_WEEKDAY = 2          # Wednesday
BROADCAST_HOUR = 19            # 7 PM
BROADCAST_MINUTE = 0
BROADCAST_TIMEZONE = "America/New_York"

SCOPES = ["https://www.googleapis.com/auth/youtube"]


def next_scheduled_time() -> dt.datetime:
    """Return the next datetime matching BROADCAST_WEEKDAY/HOUR/MINUTE in the configured tz."""
    tz = ZoneInfo(BROADCAST_TIMEZONE)
    now = dt.datetime.now(tz)
    days_ahead = (BROADCAST_WEEKDAY - now.weekday()) % 7
    candidate = now.replace(
        hour=BROADCAST_HOUR, minute=BROADCAST_MINUTE, second=0, microsecond=0
    ) + dt.timedelta(days=days_ahead)
    if candidate <= now:
        candidate += dt.timedelta(days=7)
    return candidate


def _credentials() -> Credentials:
    return Credentials(
        token=None,
        refresh_token=os.environ["YOUTUBE_REFRESH_TOKEN"],
        client_id=os.environ["YOUTUBE_CLIENT_ID"],
        client_secret=os.environ["YOUTUBE_CLIENT_SECRET"],
        token_uri="https://oauth2.googleapis.com/token",
        scopes=SCOPES,
    )


def create_live_broadcast() -> dict:
    """Create a scheduled live broadcast. Returns dict with video_id, url, scheduled_start."""
    creds = _credentials()
    youtube = build("youtube", "v3", credentials=creds, cache_discovery=False)

    start = next_scheduled_time()

    request = youtube.liveBroadcasts().insert(
        part="snippet,status,contentDetails",
        body={
            "snippet": {
                "title": BROADCAST_TITLE,
                "description": BROADCAST_DESCRIPTION,
                "scheduledStartTime": start.isoformat(),
            },
            "status": {
                "privacyStatus": BROADCAST_PRIVACY,
                "selfDeclaredMadeForKids": False,
            },
            "contentDetails": {
                "enableAutoStart": False,
                "enableAutoStop": False,
            },
        },
    )
    response = request.execute()
    video_id = response["id"]
    return {
        "video_id": video_id,
        "url": f"https://www.youtube.com/watch?v={video_id}",
        "scheduled_start": start.isoformat(),
    }
