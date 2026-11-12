import datetime as dt
import unittest
from unittest import mock

import youtube
from youtube import parse_newlive_args

FUTURE = (dt.datetime.now() + dt.timedelta(days=30)).strftime("%Y-%m-%d %H:%M")


class TestParseNewliveArgs(unittest.TestCase):
    def test_empty(self):
        self.assertEqual((None, None), parse_newlive_args("  "))

    def test_title_only(self):
        self.assertEqual(("Friday Show", None), parse_newlive_args("Friday Show"))

    def test_time_only(self):
        title, start = parse_newlive_args(FUTURE)
        self.assertIsNone(title)
        self.assertEqual(FUTURE, start.strftime("%Y-%m-%d %H:%M"))

    def test_title_and_time(self):
        title, start = parse_newlive_args(f"Friday Show | {FUTURE}")
        self.assertEqual("Friday Show", title)
        self.assertIsNotNone(start)

    def test_bad_time(self):
        with self.assertRaises(ValueError):
            parse_newlive_args("Show | tomorrow")

    def test_past_time(self):
        with self.assertRaises(ValueError):
            parse_newlive_args("Show | 2020-01-01 10:00")


class TestCreateBroadcast(unittest.TestCase):
    def test_binds_to_reusable_stream(self):
        yt = mock.MagicMock()
        yt.liveBroadcasts().insert().execute.return_value = {"id": "abc123"}
        yt.liveStreams().list().execute.return_value = {
            "items": [
                {"id": "s1", "contentDetails": {"isReusable": False}},
                {"id": "s2", "contentDetails": {"isReusable": True}},
            ]
        }
        env = {"YOUTUBE_REFRESH_TOKEN": "r", "YOUTUBE_CLIENT_ID": "i", "YOUTUBE_CLIENT_SECRET": "s"}
        with mock.patch.dict("os.environ", env), mock.patch.object(
            youtube, "build", return_value=yt
        ), mock.patch.object(youtube, "_credentials"):
            result = youtube.create_live_broadcast(title="T")
        self.assertEqual("https://www.youtube.com/watch?v=abc123", result["url"])
        yt.liveBroadcasts().bind.assert_called_with(
            id="abc123", part="id,contentDetails", streamId="s2"
        )


if __name__ == "__main__":
    unittest.main()
