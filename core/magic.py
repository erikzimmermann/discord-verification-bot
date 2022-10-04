import hashlib

COLOR_PREMIUM = 0xDAA520
COLOR_WARNING = 0xff1500

PAYPAL_UPDATE_DELAY = 30


def encode(text: str) -> str:
    return hashlib.sha256(text.lower().encode("utf-8")).hexdigest()
