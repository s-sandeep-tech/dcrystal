import base64
import hashlib
import html
import logging
import os
import secrets
import smtplib
from datetime import datetime, timedelta
from email.message import EmailMessage
from urllib.parse import urlencode

logger = logging.getLogger(__name__)


def _env_flag(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {'1', 'true', 'yes', 'on'}


def hash_verification_token(token):
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


def issue_verification_token(user):
    token = secrets.token_urlsafe(32)
    now = datetime.utcnow()
    ttl_hours = int(os.getenv('EMAIL_VERIFICATION_TTL_HOURS', '24'))
    user.email_verification_token_hash = hash_verification_token(token)
    user.email_verification_sent_at = now
    user.email_verification_expires_at = now + timedelta(hours=ttl_hours)
    return token


def _get_service_account_path():
    sa_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
    if sa_path and os.path.exists(sa_path):
        return sa_path
    
    candidates = [
        os.path.join(os.path.dirname(__file__), '..', '..', 'service_account.json'),
        os.path.join(os.getcwd(), 'service_account.json'),
        os.path.join(os.getcwd(), 'server', 'service_account.json'),
    ]
    for path in candidates:
        abs_path = os.path.abspath(path)
        if os.path.exists(abs_path):
            return abs_path
    return None


def _send_via_gmail_api(message, sender):
    sa_path = _get_service_account_path()
    if not sa_path:
        return False
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build

        scopes = ['https://www.googleapis.com/auth/gmail.send']
        creds = service_account.Credentials.from_service_account_file(sa_path, scopes=scopes)
        delegated_creds = creds.with_subject(sender)
        service = build('gmail', 'v1', credentials=delegated_creds, cache_discovery=False)
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
        service.users().messages().send(userId='me', body={'raw': raw_message}).execute()
        logger.info(f"Email sent via Gmail API using service account ({sa_path})")
        return True
    except Exception as e:
        logger.warning(f"Gmail API delivery attempt failed: {e}. Falling back to SMTP if configured.")
        return False


def _send_via_smtp(message):
    smtp_host = os.getenv('SMTP_HOST')
    if not smtp_host:
        raise RuntimeError('Neither Gmail API credentials nor SMTP_HOST is configured')

    use_ssl = _env_flag('SMTP_USE_SSL')
    smtp_port = int(os.getenv('SMTP_PORT', '465' if use_ssl else '587'))
    smtp_timeout = int(os.getenv('SMTP_TIMEOUT', '15'))
    smtp_class = smtplib.SMTP_SSL if use_ssl else smtplib.SMTP

    with smtp_class(smtp_host, smtp_port, timeout=smtp_timeout) as smtp:
        if not use_ssl and _env_flag('SMTP_USE_TLS', True):
            smtp.starttls()
        smtp_username = os.getenv('SMTP_USERNAME')
        smtp_password = os.getenv('SMTP_PASSWORD')
        if smtp_username:
            smtp.login(smtp_username, smtp_password or '')
        smtp.send_message(message)


def send_verification_email(user, token):
    public_base_url = os.getenv('PUBLIC_BASE_URL')
    if not public_base_url:
        raise RuntimeError('PUBLIC_BASE_URL is not configured')

    verify_url = (
        f"{public_base_url.rstrip('/')}/api/auth/verify-email?"
        f"{urlencode({'token': token})}"
    )
    sender = os.getenv('MAIL_FROM', 'admin.services@kalyanjewellers.tech')
    display_name = html.escape(user.username or user.user_id)
    safe_url = html.escape(verify_url, quote=True)
    ttl_hours = int(os.getenv('EMAIL_VERIFICATION_TTL_HOURS', '24'))

    message = EmailMessage()
    message['Subject'] = 'Activate your MIS account'
    message['From'] = sender
    message['To'] = user.email
    message.set_content(
        f"Hello {user.username},\n\n"
        f"Activate your MIS account using this link:\n{verify_url}\n\n"
        f"This link expires in {ttl_hours} hours. If you did not expect this account, ignore this email."
    )
    preheader = f"Activate your MIS account - Verification link expires in {ttl_hours} hours."
    html_content = f'''<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
  <meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>MIS Account Activation</title>
</head>
<body style="margin: 0; padding: 0; background-color: #f1f5f9; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #1e293b; -webkit-font-smoothing: antialiased;">
  <!-- Preheader preview text in inbox -->
  <div style="display: none; font-size: 1px; color: #f1f5f9; line-height: 1px; max-height: 0px; max-width: 0px; opacity: 0; overflow: hidden;">
    {preheader} &zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;
  </div>

  <table border="0" cellpadding="0" cellspacing="0" width="100%" style="background-color: #f1f5f9; padding: 36px 12px;">
    <tr>
      <td align="center">
        <!-- Main Card Container -->
        <table border="0" cellpadding="0" cellspacing="0" width="100%" style="max-width: 580px; background-color: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 12px rgba(15, 23, 42, 0.05);">
          
          <!-- Header Banner -->
          <tr>
            <td style="background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%); background-color: #0f172a; padding: 28px 36px; border-bottom: 3px solid #2563eb;">
              <table border="0" cellpadding="0" cellspacing="0" width="100%">
                <tr>
                  <td>
                    <div style="font-size: 22px; font-weight: 800; color: #ffffff; letter-spacing: -0.5px; text-transform: uppercase;">
                      <span style="color: #60a5fa;">◆</span> MIS
                    </div>
                    <div style="font-size: 12px; color: #94a3b8; margin-top: 4px; font-weight: 500; letter-spacing: 0.3px;">
                      Kalyan Jewellers Portal
                    </div>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Main Content -->
          <tr>
            <td style="padding: 36px 36px 28px 36px;">
              <h1 style="margin: 0 0 16px 0; font-size: 20px; font-weight: 700; color: #0f172a; line-height: 1.3;">
                Account Activation Request
              </h1>
              
              <p style="margin: 0 0 18px 0; font-size: 15px; line-height: 1.6; color: #334155;">
                Hello <strong>{display_name}</strong>,
              </p>
              
              <p style="margin: 0 0 24px 0; font-size: 14px; line-height: 1.6; color: #475569;">
                Your user account has been registered on the <strong>MIS</strong> management portal. To activate your access and verify your corporate email address, please click the button below.
              </p>

              <!-- Call to Action Button -->
              <table border="0" cellpadding="0" cellspacing="0" width="100%" style="margin: 28px 0 32px 0;">
                <tr>
                  <td align="center">
                    <table border="0" cellpadding="0" cellspacing="0">
                      <tr>
                        <td align="center" style="border-radius: 8px; background-color: #2563eb;">
                          <a href="{safe_url}" target="_blank" style="font-size: 15px; font-weight: 700; color: #ffffff; text-decoration: none; padding: 14px 32px; border-radius: 8px; display: inline-block; letter-spacing: 0.2px; background-color: #2563eb; border: 1px solid #1d4ed8;">
                            Activate My Account &rarr;
                          </a>
                        </td>
                      </tr>
                    </table>
                  </td>
                </tr>
              </table>

              <!-- Notice Box -->
              <table border="0" cellpadding="0" cellspacing="0" width="100%" style="background-color: #f8fafc; border: 1px solid #e2e8f0; border-left: 4px solid #3b82f6; border-radius: 6px; margin: 0 0 24px 0;">
                <tr>
                  <td style="padding: 14px 18px;">
                    <table border="0" cellpadding="0" cellspacing="0" width="100%">
                      <tr>
                        <td style="font-size: 13px; color: #475569; line-height: 1.5;">
                          <strong style="color: #1e293b;">Security Note:</strong> This single-use verification link will expire in <strong>{ttl_hours} hours</strong>. If you did not request this account, please ignore this email.
                        </td>
                      </tr>
                    </table>
                  </td>
                </tr>
              </table>

              <!-- Fallback Direct Link -->
              <div style="border-top: 1px solid #e2e8f0; padding-top: 20px; margin-top: 24px;">
                <p style="margin: 0 0 8px 0; font-size: 12px; color: #64748b; line-height: 1.4;">
                  If the button above does not work, copy and paste this link into your browser:
                </p>
                <p style="margin: 0; font-size: 12px; line-height: 1.4; word-break: break-all;">
                  <a href="{safe_url}" style="color: #2563eb; text-decoration: underline;">{safe_url}</a>
                </p>
              </div>

            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="background-color: #f8fafc; padding: 22px 36px; border-top: 1px solid #e2e8f0; text-align: center;">
              <p style="margin: 0 0 6px 0; font-size: 12px; font-weight: 600; color: #475569;">
                Kalyan Jewellers India Limited
              </p>
              <p style="margin: 0; font-size: 11px; color: #94a3b8; line-height: 1.4;">
                This is an automated administrative notification. Please do not reply to this email.
              </p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>'''

    message.add_alternative(html_content, subtype='html')

    # 1. Try Gmail API via Service Account
    if _send_via_gmail_api(message, sender):
        return

    # 2. Fall back to SMTP
    _send_via_smtp(message)
