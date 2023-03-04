import unittest
from tdillenbot import extract_video_id


class TestExtractVideo(unittest.TestCase):

    def test_bare(self):
        input = "5K3ienV3ZqQ"
        id = extract_video_id(input)
        self.assertEqual("5K3ienV3ZqQ", id)

    def test_full(self):
        input = "https://www.youtube.com/watch?v=5K3ienV3ZqQ"
        id = extract_video_id(input)
        self.assertEqual("5K3ienV3ZqQ", id)

    def test_short(self):
        input = "https://youtu.be/5K3ienV3ZqQ"
        id = extract_video_id(input)
        self.assertEqual("5K3ienV3ZqQ", id)

    def test_live(self):
        input = "https://youtube.com/live/C5ScdRcW8II"
        id = extract_video_id(input)
        self.assertEqual("C5ScdRcW8II", id)


if __name__ == '__main__':
    unittest.main()
