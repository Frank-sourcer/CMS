import logging
import os

from dotenv import load_dotenv
import africastalking

load_dotenv()

logger = logging.getLogger(__name__)

_initialized = False


def _init():
    global _initialized
    if not _initialized:
        africastalking.initialize(
            username=os.getenv("AT_USERNAME", "sandbox"),
            api_key=os.getenv("AT_API_KEY"),
        )
        _initialized = True


def normalize_phone(phone: str) -> str:
    """Turn 0716936604 or 254716936604 into +254716936604."""
    p = phone.strip().replace(" ", "").replace("-", "")
    if p.startswith("0"):
        p = "254" + p[1:]
    if not p.startswith("+"):
        p = "+" + p
    return p

def send_sms(to: str, message: str) -> dict:
    """Send an SMS via Africa's Talking. Returns a dict with status info."""
    _init()
    phone = normalize_phone(to)
    sender = os.getenv("AT_SENDER_ID") or None

    try:
        sms = africastalking.SMS
        kwargs = {"sender_id": sender} if sender else {}
        response = sms.send(message, [phone], **kwargs)
        logger.info("SMS sent to %s: %s", phone, response)
        return {"ok": True, "response": response}
    except Exception as exc:
        logger.exception("SMS send failed to %s", phone)
        return {"ok": False, "error": str(exc)}
