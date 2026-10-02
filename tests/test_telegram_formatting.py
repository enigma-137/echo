import unittest

from app.services.telegram import format_telegram_html


class TelegramFormattingTests(unittest.TestCase):
    def test_formats_markdown_table_as_mobile_friendly_bullets(self) -> None:
        source = """Got a handful of unread messages:
| From | Subject | When |
|---|---|---|
| **Adrian** | **Build a platform** | 11:05 AM |
| OPay | Transfer Successful | 4:24 PM |"""

        result = format_telegram_html(source)

        self.assertIn("<b>From · Subject · When</b>", result)
        self.assertIn("• <b>Adrian</b>\n  <b>Build a platform</b> · 11:05 AM", result)
        self.assertNotIn("|---|", result)

    def test_escapes_model_generated_html(self) -> None:
        result = format_telegram_html("<script>alert('x')</script> **safe**")
        self.assertIn("&lt;script&gt;", result)
        self.assertIn("<b>safe</b>", result)
        self.assertNotIn("<script>", result)

    def test_formats_headings_lists_italics_and_code(self) -> None:
        result = format_telegram_html("## Inbox\n- *Important* `message`")
        self.assertEqual(result, "<b>Inbox</b>\n• <i>Important</i> <code>message</code>")


if __name__ == "__main__":
    unittest.main()
