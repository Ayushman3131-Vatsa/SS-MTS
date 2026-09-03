import unittest
from unittest.mock import AsyncMock, patch

from app.common.email import send_email, _markdown_to_simple_html


class EmailServiceUnitTests(unittest.IsolatedAsyncioTestCase):
    def test_markdown_to_html_formatting(self) -> None:
        raw_text = "Hi **John Doe**,\nYour code is `12345`.\nVisit https://example.com"
        html_out = _markdown_to_simple_html(raw_text)
        self.assertIn("<strong>John Doe</strong>", html_out)
        self.assertIn("<code", html_out)
        self.assertIn("href=\"https://example.com\"", html_out)

    async def test_send_email_dry_run_when_password_empty(self) -> None:
        with patch("app.common.email.get_settings") as mock_settings:
            mock_settings.return_value.smtp_password = None
            mock_settings.return_value.smtp_enabled = True
            mock_settings.return_value.smtp_from_email = "hrms.smartskale@gmail.com"
            mock_settings.return_value.smtp_from_name = "SmartSkale HRMS"
            mock_settings.return_value.smtp_user = "hrms.smartskale@gmail.com"

            result = await send_email(
                to_email="test@example.com",
                subject="Test Subject",
                body="Hello world",
            )
            self.assertTrue(result)

    async def test_send_email_calls_aiosmtplib(self) -> None:
        with (
            patch("app.common.email.get_settings") as mock_settings,
            patch("app.common.email.aiosmtplib.send", new_callable=AsyncMock) as mock_send,
        ):
            mock_settings.return_value.smtp_password = "test-app-password"
            mock_settings.return_value.smtp_enabled = True
            mock_settings.return_value.smtp_host = "smtp.gmail.com"
            mock_settings.return_value.smtp_port = 587
            mock_settings.return_value.smtp_use_tls = True
            mock_settings.return_value.smtp_timeout_seconds = 10
            mock_settings.return_value.smtp_from_email = "hrms.smartskale@gmail.com"
            mock_settings.return_value.smtp_from_name = "SmartSkale HRMS"
            mock_settings.return_value.smtp_user = "hrms.smartskale@gmail.com"

            result = await send_email(
                to_email="recipient@example.com",
                subject="Test Subject",
                body="Hello world with **bold**",
            )
            self.assertTrue(result)
            mock_send.assert_awaited_once()
