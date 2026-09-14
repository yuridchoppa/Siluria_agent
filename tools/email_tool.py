import os
import sys
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Any

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

def send_otp_email(to_email: str, otp_code: str, provider: str = "Google") -> Dict[str, Any]:
    """
    Send a 6-digit OTP code to the user's Gmail/Google or Apple ID email address.
    Uses standard SMTP if SMTP_USER and SMTP_PASSWORD / GMAIL_APP_PASSWORD are configured in .env.
    Otherwise gracefully logs the OTP to server console and provides simulated fallback.
    """
    smtp_host = (os.getenv("SMTP_HOST") or "smtp.gmail.com").strip()
    smtp_port = int(os.getenv("SMTP_PORT") or 587)
    smtp_user = (os.getenv("SMTP_USER") or os.getenv("GMAIL_USER") or "").strip()
    smtp_password = (os.getenv("SMTP_PASSWORD") or os.getenv("GMAIL_APP_PASSWORD") or "").strip()
    from_name = os.getenv("SMTP_FROM_NAME") or "Siluria Agent (AnakinForge)"

    provider_label = "Apple ID Sanctuary" if provider.lower() == "apple" else "Google / Gmail Realm"

    # If SMTP is configured, attempt real email transmission
    if smtp_user and smtp_password:
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = f"⚜ {otp_code} - Thy Sacred {provider_label} Access Cipher"
            msg["From"] = f"{from_name} <{smtp_user}>"
            msg["To"] = to_email

            text_body = (
                f"Greetings, Traveler.\n\n"
                f"Thy sacred one-time passcode for Siluria Agent ({provider_label}) is: {otp_code}\n\n"
                f"This rune cipher expires in 5 minutes.\n"
                f"If thou didst not request this communion, disregard this parchment."
            )

            html_body = f"""
            <!DOCTYPE html>
            <html>
            <head>
              <meta charset="utf-8">
              <style>
                body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #0b0c10; color: #f5eedc; margin: 0; padding: 20px; }}
                .card {{ max-width: 480px; margin: auto; background: #13151b; border: 1px solid #d4af37; border-radius: 8px; padding: 32px; box-shadow: 0 8px 30px rgba(0,0,0,0.7); text-align: center; }}
                .title {{ color: #e5c158; font-size: 22px; font-weight: bold; letter-spacing: 2px; margin-bottom: 4px; }}
                .subtitle {{ color: #8e7943; font-size: 12px; letter-spacing: 1.5px; margin-bottom: 24px; text-transform: uppercase; }}
                .divider {{ border: 0; height: 1px; background: linear-gradient(90deg, transparent, #e5c158, transparent); margin: 20px 0; }}
                .otp-box {{ margin: 28px 0; }}
                .otp-code {{ font-size: 36px; font-weight: 800; letter-spacing: 10px; color: #facc15; background: rgba(229,193,88,0.12); border: 2px dashed #e5c158; border-radius: 6px; padding: 12px 24px; display: inline-block; }}
                .footer {{ font-size: 12px; color: #71717a; margin-top: 24px; line-height: 1.5; }}
              </style>
            </head>
            <body>
              <div class="card">
                <div class="title">⚜ SILURIA AGENT ⚜</div>
                <div class="subtitle">{provider_label} Authentication</div>
                <div class="divider"></div>
                <p style="font-size: 14px; color: #d4d4d8; line-height: 1.6;">
                  Greetings, Traveler. A request to commune with the sanctuary was initiated for thy {provider} vessel (<strong>{to_email}</strong>).
                </p>
                <div class="otp-box">
                  <div class="otp-code">{otp_code}</div>
                </div>
                <p style="font-size: 13px; color: #a1a1aa;">
                  This sacred rune cipher will expire in <strong>5 minutes</strong>.
                </p>
                <div class="divider"></div>
                <div class="footer">
                  If thou didst not request this communion, ignore this dispatch.<br>
                  © Siluria Agent • AnakinForge Sanctuary
                </div>
              </div>
            </body>
            </html>
            """

            msg.attach(MIMEText(text_body, "plain"))
            msg.attach(MIMEText(html_body, "html"))

            with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
                server.starttls()
                server.login(smtp_user, smtp_password)
                server.send_message(msg)

            print(f"[AUTH OTP] Real email dispatched successfully to {to_email}")
            return {"success": True, "sent": True, "message": f"Sacred OTP dispatched to {to_email}"}

        except Exception as e:
            print(f"[AUTH OTP ERROR] Failed to send email via SMTP: {e}")
            # Fall back to simulated mode
            return {
                "success": True,
                "sent": False,
                "error": str(e),
                "otp": otp_code,
                "message": f"SMTP dispatch error: {e}. Simulated cipher generated.",
            }

    # Simulated / Dev Mode (when SMTP is not configured yet in .env)
    print(f"\n{'='*55}\n[AUTH OTP DEV NOTICE]\nTo: {to_email}\nSacred OTP Code: {otp_code}\n(To send real emails, set SMTP_USER & SMTP_PASSWORD in .env)\n{'='*55}\n")
    return {
        "success": True,
        "sent": False,
        "simulated": True,
        "otp": otp_code,
        "message": f"Sacred cipher dispatched! (Dev mode active: check server log or use auto-fill hint)",
    }
