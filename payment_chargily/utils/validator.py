import hmac
import hashlib


def validate_signature(signature: str, payload: str, secret: str):
    computed_signature = hmac.new(
        secret.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    if hmac.compare_digest(signature, computed_signature):
        return True
    return False
