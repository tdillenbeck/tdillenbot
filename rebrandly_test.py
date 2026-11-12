import unittest
from unittest import mock

import requests

import rebrandly


class TestPointRebrandly(unittest.TestCase):
    ENV = {"REBRANDLY_API_KEY": "k", "REBRANDLY_LINK_ID": "l"}

    def test_http_error_raises(self):
        resp = mock.Mock()
        resp.raise_for_status.side_effect = requests.HTTPError("401")
        with mock.patch.dict("os.environ", self.ENV), mock.patch(
            "rebrandly.requests.post", return_value=resp
        ):
            with self.assertRaises(requests.HTTPError):
                rebrandly.point_rebrandly("abc")

    def test_success_sends_watch_url(self):
        with mock.patch.dict("os.environ", self.ENV), mock.patch(
            "rebrandly.requests.post"
        ) as post:
            rebrandly.point_rebrandly("https://youtu.be/abc")
        self.assertEqual(
            {"destination": "https://www.youtube.com/watch?v=abc"}, post.call_args.kwargs["json"]
        )


if __name__ == "__main__":
    unittest.main()
