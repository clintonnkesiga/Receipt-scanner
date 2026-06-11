"""SMTP email sender + branded HTML template builder.

Sending is opt-in: until SMTP_HOST is configured in .env, `email_configured()`
returns False and callers should skip/preview instead of sending.
"""
import smtplib
from email.message import EmailMessage

from .config import settings

# ── Brand colours ─────────────────────────────────────────────────────────────
_BRAND_COLOR = "#2563EB"      # blue-600
_BRAND_DARK  = "#1D4ED8"      # blue-700
_TEXT_PRIMARY = "#0f172a"     # slate-900
_TEXT_MUTED   = "#64748b"     # slate-500
_BG           = "#f1f5f9"     # slate-100
_CARD_BG      = "#ffffff"
_BORDER       = "#e2e8f0"     # slate-200

# ─────────────────────────────────────────────────────────────────────────────

def email_html(
    *,
    heading: str,
    body_lines: list[str],
    cta_label: str | None = None,
    cta_url: str | None = None,
    footer_note: str | None = None,
) -> str:
    """Render a full transactional email in a branded Receipt Scanner wrapper.

    Args:
        heading:     Large heading at the top of the card (e.g. "Reset your password").
        body_lines:  List of paragraph strings shown above the CTA button.
        cta_label:   Button label (omit to skip the button entirely).
        cta_url:     Button href.
        footer_note: Optional small note below the card (e.g. "If you didn't …").
    """
    paras = "\n".join(
        f'<p style="margin:0 0 16px;line-height:1.6;color:{_TEXT_PRIMARY};font-size:15px;">{p}</p>'
        for p in body_lines
    )

    cta_block = ""
    if cta_label and cta_url:
        cta_block = f"""
        <div style="text-align:center;margin:32px 0 8px;">
          <a href="{cta_url}"
             style="display:inline-block;background:{_BRAND_COLOR};color:#fff;
                    text-decoration:none;font-size:15px;font-weight:600;
                    padding:14px 32px;border-radius:8px;letter-spacing:0.01em;">
            {cta_label}
          </a>
        </div>
        <p style="text-align:center;margin:12px 0 0;font-size:12px;color:{_TEXT_MUTED};">
          Or copy this link into your browser:<br>
          <a href="{cta_url}" style="color:{_BRAND_COLOR};word-break:break-all;">{cta_url}</a>
        </p>"""

    footer_html = ""
    if footer_note:
        footer_html = f"""
        <p style="text-align:center;font-size:12px;color:{_TEXT_MUTED};
                  margin:24px auto 0;max-width:440px;line-height:1.5;">
          {footer_note}
        </p>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>{heading}</title>
</head>
<body style="margin:0;padding:0;background:{_BG};
             font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Arial,sans-serif;">

  <!-- Outer wrapper -->
  <table width="100%" cellpadding="0" cellspacing="0" border="0"
         style="background:{_BG};padding:40px 16px;">
    <tr>
      <td align="center">

        <!-- Card -->
        <table width="100%" cellpadding="0" cellspacing="0" border="0"
               style="max-width:560px;background:{_CARD_BG};border-radius:12px;
                      border:1px solid {_BORDER};overflow:hidden;">

          <!-- Header bar -->
          <tr>
            <td style="background:{_BRAND_COLOR};padding:24px 32px;">
              <table cellpadding="0" cellspacing="0" border="0">
                <tr>
                  <td style="font-size:28px;line-height:1;padding-right:10px;">🧾</td>
                  <td style="color:#fff;font-size:17px;font-weight:700;
                              letter-spacing:0.01em;">Receipt Scanner</td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Body -->
          <tr>
            <td style="padding:36px 36px 8px;">
              <h1 style="margin:0 0 20px;font-size:22px;font-weight:700;
                          color:{_TEXT_PRIMARY};line-height:1.3;">
                {heading}
              </h1>
              {paras}
              {cta_block}
            </td>
          </tr>

          <!-- Divider + footer -->
          <tr>
            <td style="padding:24px 36px 32px;">
              <hr style="border:none;border-top:1px solid {_BORDER};margin:0 0 20px;" />
              <p style="margin:0;font-size:12px;color:{_TEXT_MUTED};line-height:1.6;">
                This email was sent by <strong style="color:{_TEXT_PRIMARY};">Receipt Scanner</strong>.
                Please do not reply — this address is not monitored.
              </p>
            </td>
          </tr>

        </table>
        <!-- /Card -->

        {footer_html}

      </td>
    </tr>
  </table>
  <!-- /Outer wrapper -->

</body>
</html>"""


# ─────────────────────────────────────────────────────────────────────────────

def email_configured() -> bool:
    return bool(settings.smtp_host)


def send_email(to: str, subject: str, html: str, text: str | None = None) -> None:
    """Send a single HTML email via SMTP. Raises if SMTP isn't configured."""
    if not email_configured():
        raise RuntimeError("Email is not configured (set SMTP_HOST in .env)")

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from
    msg["To"] = to
    msg.set_content(text or "Please view this email in an HTML-capable email client.")
    msg.add_alternative(html, subtype="html")

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as server:
        if settings.smtp_use_tls:
            server.starttls()
        if settings.smtp_user:
            server.login(settings.smtp_user, settings.smtp_password or "")
        server.send_message(msg)
