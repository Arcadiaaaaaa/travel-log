"""保持既有PBKDF2格式；WASM使用经维护的加密库，避免降低迭代次数。"""
import hashlib
import hmac

import server


def verify_password(password, stored):
    if callable(getattr(hashlib, "pbkdf2_hmac", None)):
        return server.verify_password(password, stored)
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    try:
        algorithm, iterations, salt_hex, digest_hex = stored.split("$")
        if algorithm != "pbkdf2_sha256" or int(iterations) < 1:
            return False
        kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32,
                        salt=bytes.fromhex(salt_hex), iterations=int(iterations))
        digest = kdf.derive(password.encode("utf-8"))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(digest.hex(), digest_hex)
