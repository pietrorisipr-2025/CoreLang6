"""
CL6 signing helpers.
Prefer Ed25519 (requires 'cryptography'), fallback to HMAC-SHA256 (shared secret).
"""
from pathlib import Path
import hmac, hashlib, json

_has_crypto = False
try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
    from cryptography.hazmat.primitives import serialization
    _has_crypto = True
except Exception:
    _has_crypto = False

def crypto_available(): return _has_crypto

# --- Ed25519 ---
def ed25519_gen(priv_path: str, pub_path: str):
    if not _has_crypto: raise RuntimeError("cryptography non disponibile")
    sk = Ed25519PrivateKey.generate()
    pk = sk.public_key()
    priv_bytes = sk.private_bytes(encoding=serialization.Encoding.PEM,
                                  format=serialization.PrivateFormat.PKCS8,
                                  encryption_algorithm=serialization.NoEncryption())
    pub_bytes = pk.public_bytes(encoding=serialization.Encoding.PEM,
                                format=serialization.PublicFormat.SubjectPublicKeyInfo)
    Path(priv_path).write_bytes(priv_bytes)
    Path(pub_path).write_bytes(pub_bytes)

def ed25519_sign(priv_path: str, file_path: str, sig_path: str):
    if not _has_crypto: raise RuntimeError("cryptography non disponibile")
    from cryptography.hazmat.primitives import serialization
    sk = serialization.load_pem_private_key(Path(priv_path).read_bytes(), password=None)
    data = Path(file_path).read_bytes()
    sig = sk.sign(data)
    Path(sig_path).write_bytes(sig)

def ed25519_verify(pub_path: str, file_path: str, sig_path: str) -> bool:
    if not _has_crypto: raise RuntimeError("cryptography non disponibile")
    from cryptography.hazmat.primitives import serialization
    pk = serialization.load_pem_public_key(Path(pub_path).read_bytes())
    data = Path(file_path).read_bytes()
    sig = Path(sig_path).read_bytes()
    try:
        pk.verify(sig, data)
        return True
    except Exception:
        return False

# --- HMAC (fallback) ---
def hmac_sign(secret: str, file_path: str, sig_path: str):
    key = secret.encode("utf-8")
    h = hmac.new(key, digestmod=hashlib.sha256)
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(1024*256), b""):
            h.update(chunk)
    Path(sig_path).write_text(json.dumps({"alg":"HMAC-SHA256","sig":h.hexdigest()}))

def hmac_verify(secret: str, file_path: str, sig_path: str) -> bool:
    key = secret.encode("utf-8")
    obj = json.loads(Path(sig_path).read_text())
    exp = obj.get("sig","")
    h = hmac.new(key, digestmod=hashlib.sha256)
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(1024*256), b""):
            h.update(chunk)
    return h.hexdigest() == exp
