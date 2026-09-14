import os
import sys
from typing import Dict, Any
import requests

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

def send_phone_otp(phone_number: str, otp_code: str) -> Dict[str, Any]:
    """
    Send a 6-digit OTP code to the user's mobile phone via SMS.
    Uses Twilio REST API if TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, and TWILIO_FROM_NUMBER are set in .env.
    Otherwise gracefully logs the OTP to server console and provides simulated fallback.
    """
    account_sid = (os.getenv("TWILIO_ACCOUNT_SID") or "").strip()
    auth_token = (os.getenv("TWILIO_AUTH_TOKEN") or "").strip()
    from_number = (os.getenv("TWILIO_FROM_NUMBER") or os.getenv("TWILIO_PHONE_NUMBER") or "").strip()

    message_body = (
        f"⚜ Siluria Agent Sacred Cipher: {otp_code}\n"
        f"Valid for 5 minutes. Enter this code to kindle thy vessel."
    )

    # If Twilio credentials are configured, dispatch real SMS
    if account_sid and auth_token and from_number:
        try:
            url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
            resp = requests.post(
                url,
                data={
                    "From": from_number,
                    "To": phone_number,
                    "Body": message_body,
                },
                auth=(account_sid, auth_token),
                timeout=8,
            )
            if resp.status_code in (200, 201):
                print(f"[AUTH SMS] Real SMS dispatched successfully to {phone_number}")
                return {
                    "success": True,
                    "sent": True,
                    "message": f"Sacred SMS cipher dispatched to {phone_number}."
                }
            else:
                err_text = resp.text
                print(f"[AUTH SMS ERROR] Twilio returned {resp.status_code}: {err_text}")
                return {
                    "success": True,
                    "sent": False,
                    "error": err_text,
                    "otp": otp_code,
                    "message": f"Twilio SMS error. Sacred cipher simulated in console."
                }
        except Exception as e:
            print(f"[AUTH SMS ERROR] Exception sending SMS: {e}")
            return {
                "success": True,
                "sent": False,
                "error": str(e),
                "otp": otp_code,
                "message": f"SMS dispatch error: {e}. Sacred cipher simulated."
            }

    # Dev / Local Simulation Mode
    print(f"\n{'='*55}\n[AUTH SMS DEV NOTICE]\nTo: {phone_number}\nSacred Mobile OTP: {otp_code}\n(To send real SMS, set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN & TWILIO_FROM_NUMBER in .env)\n{'='*55}\n")
    return {
        "success": True,
        "sent": False,
        "simulated": True,
        "otp": otp_code,
        "message": f"Sacred SMS cipher dispatched to {phone_number}! (Dev mode: check console or use auto-fill hint)"
    }
