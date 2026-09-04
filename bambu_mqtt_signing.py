import base64
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

ROOT = Path(__file__).resolve().parent
DEFAULT_KEY = ROOT / "data" / "bambu_signing" / "private_key.pem"
DEFAULT_CERT = ROOT / "data" / "bambu_signing" / "certificate.pem"
AUTH_STATE = ROOT / "data" / "bambu_cloud_auth.json"


def _read(env, path_env, default):
    value = os.getenv(env)
    if value: return value.replace("\\n", "\n")
    path = Path(os.getenv(path_env) or default)
    return path.read_text(encoding="utf-8") if path.exists() else None


def _material():
    kp = _read("BAMBU_APP_PRIVATE_KEY", "BAMBU_APP_PRIVATE_KEY_PATH", DEFAULT_KEY)
    cp = _read("BAMBU_APP_CERTIFICATE", "BAMBU_APP_CERTIFICATE_PATH", DEFAULT_CERT)
    if not kp or not cp: raise ValueError("Signing key/certificate not configured")
    return serialization.load_pem_private_key(kp.encode(), password=None), x509.load_pem_x509_certificate(cp.encode()), cp


def _uid():
    if os.getenv("BAMBU_LAB_USER_ID"): return os.getenv("BAMBU_LAB_USER_ID")
    try: return str(json.loads(AUTH_STATE.read_text(encoding="utf-8")).get("uid") or "")
    except Exception: return ""


def certificate_is_valid():
    try:
        key, cert, _ = _material(); now = datetime.now(timezone.utc)
        nb = getattr(cert, "not_valid_before_utc", cert.not_valid_before.replace(tzinfo=timezone.utc))
        na = getattr(cert, "not_valid_after_utc", cert.not_valid_after.replace(tzinfo=timezone.utc))
        if not nb <= now <= na: return False
        a = key.public_key().public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
        b = cert.public_key().public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
        return a == b and bool(_uid())
    except Exception: return False


def signing_available(): return certificate_is_valid()


def _cert_id(cert, pem):
    override = os.getenv("BAMBU_LAB_APP_CERT_ID")
    if override:
        return override
    # Bambu MQTT cert_id = certificate serial number (lower-case hex) +
    # RFC4514 issuer string, with no separator.
    return f"{cert.serial_number:x}{cert.issuer.rfc4514_string()}"


def sign_message_json(message):
    """Return the exact signed MQTT wire JSON for a top-level print command."""
    if not certificate_is_valid():
        raise ValueError("No valid signing certificate/key/user-id")
    if not isinstance(message, dict) or "print" not in message:
        return json.dumps(message, ensure_ascii=False, separators=(",", ":"))

    key, cert, pem = _material()

    # Serialize print exactly once. These exact bytes are both signed and emitted.
    print_text = json.dumps(message["print"], ensure_ascii=False, separators=(",", ":"))
    signed_text = '{"print":' + print_text + '}'
    signed_bytes = signed_text.encode("utf-8")
    sig = key.sign(signed_bytes, padding.PKCS1v15(), hashes.SHA256())

    header = {
        "sign_ver": "v1.0",
        "sign_alg": "RSA_SHA256",
        "sign_string": base64.b64encode(sig).decode("ascii"),
        "cert_id": _cert_id(cert, pem),
        "payload_len": len(signed_bytes),
    }
    header_text = json.dumps(header, ensure_ascii=False, separators=(",", ":"))
    return '{"header":' + header_text + ',"print":' + print_text + '}'


def sign_message(message):
    """Compatibility helper for callers that still expect a dict."""
    return json.loads(sign_message_json(message))
