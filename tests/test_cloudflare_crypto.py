"""WASM 缺少 OpenSSL 时，保持现有 PBKDF2 格式与60万次参数。"""
import hashlib
import importlib.util
import unittest
from unittest.mock import patch

import server
from cloudflare_crypto import verify_password


class CloudflareCryptoTest(unittest.TestCase):
    def test_native_hash_and_wrong_password(self):
        stored = server.hash_password("temporary-crypto-fixture")
        self.assertTrue(verify_password("temporary-crypto-fixture", stored))
        self.assertFalse(verify_password("wrong", stored))

    @unittest.skipUnless(importlib.util.find_spec("cryptography"), "Cloudflare加密依赖需通过uv sync安装")
    def test_wasm_backend_matches_existing_hashes(self):
        for password in ["temporary-crypto-fixture", "临时Unicode密码"]:
            stored = server.hash_password(password)
            self.assertIn("$600000$", stored)
            with patch.object(hashlib, "pbkdf2_hmac", None):
                self.assertTrue(verify_password(password, stored))
                self.assertFalse(verify_password("wrong", stored))

    @unittest.skipUnless(importlib.util.find_spec("cryptography"), "Cloudflare加密依赖需通过uv sync安装")
    def test_wasm_known_sha256_pbkdf2_vector_and_bad_format(self):
        stored = "pbkdf2_sha256$1$73616c74$120fb6cffcf8b32c43e7225256c4f837a86548c92ccc35480805987cb70be17b"
        with patch.object(hashlib, "pbkdf2_hmac", None):
            self.assertTrue(verify_password("password", stored))
            self.assertFalse(verify_password("password", "invalid"))
            self.assertFalse(verify_password("password", stored.replace("$1$", "$0$")))
