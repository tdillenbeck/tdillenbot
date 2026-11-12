#!/usr/bin/env python3
"""Create a scheduled YouTube live broadcast bound to the persistent stream key."""

import datetime as dt
import os
import re
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


def parse_newlive_args(text: str) -> tuple[str | None, dt.datetime | None]:
    """Parse "<title> | <YYYY-MM-DD HH:MM>" (both parts optional) into (title, start).

    A lone date/time with no title is accepted too. The time is interpreted in
    BROADCAST_TIMEZONE. Raises ValueError if a time is given but is invalid or
    in the past.
    """
    text = text.strip()
    if not text:
        return None, None

    if "|" not in text:  # either a bare time or a bare title
        if re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}", text):
            return None, _parse_time(text)
        return text, None

    title, _, when = text.rpartition("|")
    title, when = title.strip(), when.strip()
    return (title or None), (_parse_time(when) if when else None)


def _parse_time(value: str) -> dt.datetime:
    try:
        naive = dt.datetime.strptime(value, "%Y-%m-%d %H:%M")
    except ValueError:
        raise ValueError("Time must look like YYYY-MM-DD HH:MM") from None
    start = naive.replace(tzinfo=ZoneInfo(BROADCAST_TIMEZONE))
    if start <= dt.datetime.now(ZoneInfo(BROADCAST_TIMEZONE)):
        raise ValueError("Start time must be in the future")
    return start


def _find_stream_id(youtube) -> str:
    """Return the persistent (reusable) stream to bind broadcasts to."""
    configured = os.environ.get("YOUTUBE_STREAM_ID")
    if configured:
        return configured
    response = (
        youtube.liveStreams().list(part="id,contentDetails", mine=True).execute()
    )
    for stream in response.get("items", []):
        if stream.get("contentDetails", {}).get("isReusable"):
            return stream["id"]
    raise RuntimeError(
        "No live stream found on this channel. Create one in YouTube Studio or set YOUTUBE_STREAM_ID."
    )


def _credentials() -> Credentials:
    return Credentials(
        token=None,
        refresh_token=os.environ["YOUTUBE_REFRESH_TOKEN"],
        client_id=os.environ["YOUTUBE_CLIENT_ID"],
        client_secret=os.environ["YOUTUBE_CLIENT_SECRET"],
        token_uri="https://oauth2.googleapis.com/token",
        scopes=SCOPES,
    )


def create_live_broadcast(
    title: str | None = None, start: dt.datetime | None = None
) -> dict:
    """Create a scheduled live broadcast and bind it to the persistent stream key.

    Returns dict with video_id, url, scheduled_start.
    """
    creds = _credentials()
    youtube = build("youtube", "v3", credentials=creds, cache_discovery=False)

    start = start or next_scheduled_time()

    request = youtube.liveBroadcasts().insert(
        part="snippet,status,contentDetails",
        body={
            "snippet": {
                "title": title or BROADCAST_TITLE,
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

    youtube.liveBroadcasts().bind(
        id=video_id, part="id,contentDetails", streamId=_find_stream_id(youtube)
    ).execute()
    return {
        "video_id": video_id,
        "url": f"https://www.youtube.com/watch?v={video_id}",
        "scheduled_start": start.isoformat(),
    }
