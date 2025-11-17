import unittest

from src.browser import URL


class TestUrl(unittest.TestCase):
    def test_about_url(self):
        url = URL("about:test")

        self.assertEqual(url.scheme, "about")

    def test_invalid_protocol(self):
        url = URL("invalid:test")
        self.assertEqual(url.scheme, "about")
