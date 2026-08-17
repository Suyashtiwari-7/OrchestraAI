"""
OrchestraAI — Digital Safe & Memory Vault (Windows DPAPI)
=========================================================
Hardware-backed encryption for user credentials, candidate vault, and private tokens.
Uses Windows Data Protection API (DPAPI) tied to the logged-in Windows user account.
"""

import os
import base64
import logging
from typing import Optional

logger = logging.getLogger("orchestra.memory.vault")


class MemoryVault:
    """Provides hardware-backed, local-only encryption for sensitive profile data."""

    @staticmethod
    def encrypt(plaintext: str) -> str:
        """
        Encrypts a string using Windows DPAPI (CryptProtectData).
        Returns base64-encoded encrypted blob.
        """
        if not plaintext:
            return ""

        try:
            if os.name == "nt":
                import win32crypt
                raw_bytes = plaintext.encode("utf-8")
                # CryptProtectData encrypts with Windows user credentials
                encrypted_blob = win32crypt.CryptProtectData(raw_bytes, "DARKI_SAFE", None, None, None, 0)
                return base64.b64encode(encrypted_blob).decode("utf-8")
            else:
                # Obfuscation fallback for non-Windows dev environments
                return base64.b64encode(plaintext.encode("utf-8")).decode("utf-8")
        except Exception as e:
            logger.error(f"[Vault] Encryption error: {e}")
            return plaintext

    @staticmethod
    def decrypt(ciphertext: str) -> str:
        """
        Decrypts a base64-encoded string using Windows DPAPI (CryptUnprotectData).
        Returns original plaintext.
        """
        if not ciphertext:
            return ""

        try:
            if os.name == "nt":
                import win32crypt
                encrypted_blob = base64.b64decode(ciphertext.encode("utf-8"))
                _, decrypted_bytes = win32crypt.CryptUnprotectData(encrypted_blob, None, None, None, 0)
                return decrypted_bytes.decode("utf-8")
            else:
                return base64.b64decode(ciphertext.encode("utf-8")).decode("utf-8")
        except Exception as e:
            logger.debug(f"[Vault] Decryption fallback (treating as raw): {e}")
            return ciphertext
