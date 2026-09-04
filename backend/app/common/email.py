
import asyncio
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import logging
import uuid

import aiosmtplib

from app.common.config import get_settings
from app.common.template_renderer import (
    RenderedTemplate,
    render_platform_template,
    render_template,
)

logger = logging.getLogger("app.email")


def _markdown_to_simple_html(text: str) -> str:
    """Convert basic markdown bold, code, and linebreaks into clean HTML."""
    import html
    import re

    # Escape raw HTML
    escaped = html.escape(text)
    # Bold **text** -> <strong>text</strong>
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)
    # Monospace `code` -> <code style="...">code</code>
    escaped = re.sub(
        r"`(.+?)`",
        r'<code style="background-color:#f1f5f9;color:#0f172a;padding:2px 6px;border-radius:4px;font-family:monospace;font-size:13px;">\1</code>',
        escaped,
    )
    # URLs -> links
    escaped = re.sub(
        r"(https?://[^\s<>]+)",
        r'<a href="\1" style="color:#2563eb;text-decoration:underline;">\1</a>',
        escaped,
    )
    # Line breaks -> <br/>
    html_body = escaped.replace("\n", "<br/>\n")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0;padding:24px;background-color:#f8fafc;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;color:#1e293b;line-height:1.6;">
  <div style="max-width:580px;margin:0 auto;background-color:#ffffff;border:1px solid #e2e8f0;border-radius:8px;padding:32px;box-shadow:0 1px 3px rgba(0,0,0,0.05);">
    <div style="margin-bottom:20px;padding-bottom:16px;border-bottom:1px solid #f1f5f9;">
      <span style="font-weight:700;font-size:18px;color:#0f172a;letter-spacing:-0.02em;">SmartSkale HRMS</span>
    </div>
    <div style="font-size:14px;color:#334155;">
      {html_body}
    </div>
    <div style="margin-top:32px;padding-top:16px;border-top:1px solid #f1f5f9;font-size:12px;color:#94a3b8;">
      <p style="margin:0;">This is an automated system notification from SmartSkale. Please do not reply directly to this email.</p>
    </div>
  </div>
</body>
</html>"""


async def send_email(
    *,
    to_email: str,
    subject: str,
    body: str,
    html_body: str | None = None,
) -> bool:
    """Send an email via Google SMTP (or log to console if unconfigured).

    Returns True if sent/handled successfully, False otherwise.
    """
    settings = get_settings()

    from_email = settings.smtp_from_email or settings.smtp_user or "hrms.smartskale@gmail.com"
    from_header = f"{settings.smtp_from_name} <{from_email}>"

    # Email bodies can contain temporary credentials. Never write them to logs.
    if not settings.smtp_password or not settings.smtp_enabled:
        logger.info(
            "[EMAIL SERVICE - DRY RUN / UNCONFIGURED] To: %s Subject: %s From: %s Body: [SUPPRESSED]",
            to_email,
            subject,
            from_header,
        )
        return True

    # Construct standard MIME multipart email
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = from_header
    msg["To"] = to_email

    # Attach plain text
    part_text = MIMEText(body, "plain", "utf-8")
    msg.attach(part_text)

    # Attach HTML version
    rendered_html = html_body or _markdown_to_simple_html(body)
    part_html = MIMEText(rendered_html, "html", "utf-8")
    msg.attach(part_html)

    try:
        await aiosmtplib.send(
            msg,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            start_tls=settings.smtp_use_tls,
            username=settings.smtp_user,
            password=settings.smtp_password.replace(" ", ""),
            timeout=settings.smtp_timeout_seconds,
        )
        logger.info("Email sent successfully to %s with subject '%s'", to_email, subject)
        return True
    except Exception as exc:
        logger.exception("Failed to send email to %s via Google SMTP: %s", to_email, exc)
        return False


async def send_templated_email(
    db,
    *,
    tenant_id: uuid.UUID,
    template_code: str,
    context: dict[str, str | object],
    to_email: str,
) -> bool:
    """Render a tenant-scoped template and dispatch the email in the background."""
    try:
        rendered: RenderedTemplate = await render_template(
            db,
            tenant_id=tenant_id,
            template_code=template_code,
            context=context,
        )
        subject = rendered.subject or "Notification from SmartSkale"
        asyncio.create_task(
            send_email(
                to_email=to_email,
                subject=subject,
                body=rendered.body,
            )
        )
        return True
    except Exception as exc:
        logger.warning(
            "Could not render or send template '%s' for tenant %s: %s",
            template_code,
            tenant_id,
            exc,
        )
        return False


async def send_platform_templated_email(
    db,
    *,
    template_code: str,
    context: dict[str, str | object],
    to_email: str,
) -> bool:
    """Render a platform-level template and dispatch the email in the background."""
    try:
        rendered: RenderedTemplate = await render_platform_template(
            db,
            template_code=template_code,
            context=context,
        )
        subject = rendered.subject or "Notification from SmartSkale Platform"
        asyncio.create_task(
            send_email(
                to_email=to_email,
                subject=subject,
                body=rendered.body,
            )
        )
        return True
    except Exception as exc:
        logger.warning(
            "Could not render or send platform template '%s': %s",
            template_code,
            exc,
        )
        return False
