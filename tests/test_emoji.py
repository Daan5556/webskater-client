import unittest

from src.emoji import is_emoji


class TestEmoji(unittest.TestCase):
    def test_is_emoji(self):
        self.assertTrue(is_emoji("😅"))
        self.assertTrue(is_emoji("😅"))
        self.assertTrue(is_emoji("🦥"))
        self.assertTrue(is_emoji("📎"))
