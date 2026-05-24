from __future__ import annotations

import unittest

from telegram import TelegramClient, TelegramSettings, build_digest_message


class TelegramTests(unittest.TestCase):
    def test_build_digest_message_contains_header_and_digest(self) -> None:
        message = build_digest_message("Короткий дайджест новин.")

        self.assertIn("🗞️ <b>Дайджест новин</b>", message)
        self.assertIn("Короткий дайджест новин.", message)

    def test_send_message_posts_to_telegram_api(self) -> None:
        client = TelegramClient(TelegramSettings(bot_token="token", chat_id="chat"))

        calls = []
        client._post = lambda method, payload: calls.append((method, payload))  # type: ignore[method-assign]

        client.send_message("Привіт, Telegram!")

        self.assertEqual(calls[0][0], "sendMessage")
        self.assertEqual(calls[0][1]["chat_id"], "chat")
        self.assertEqual(calls[0][1]["parse_mode"], "HTML")


if __name__ == "__main__":
    unittest.main()
