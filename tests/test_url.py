import unittest

from src.browser import URL


class TestUrl(unittest.TestCase):
    def test_about_url(self):
        url = URL("about:test")

        self.assertEqual(url.scheme, "about")

    def test_invalid_protocol(self):
        url = URL("invalid:test")

        self.assertEqual(url.scheme, "about")

    def test_empty_url(self):
        url = URL("")

        self.assertEqual(url.scheme, "about")

    def test_data_url(self):
        content = "<h1>test</h1>"
        url = URL(f"data:text/html,{content}")

        self.assertEqual(url.scheme, "data")
        self.assertEqual(url.data, content)

    def test_http_url(self):
        url = URL("http://example.net")

        self.assertEqual(url.scheme, "http")
        self.assertEqual(url.path, "/")
        self.assertEqual(url.port, 80)
