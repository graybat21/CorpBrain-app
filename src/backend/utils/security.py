import base64
import os
import sys
from typing import Optional

if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]

    def _bytes_to_blob(data: bytes) -> DATA_BLOB:
        blob = DATA_BLOB()
        blob.cbData = len(data)
        if len(data) > 0:
            buffer = (ctypes.c_byte * len(data)).from_buffer_copy(data)
            blob.pbData = ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte))
        else:
            blob.pbData = None
        return blob

    def encrypt_secret(plaintext: str) -> str:
        """Encrypt plaintext secret using Windows DPAPI (CryptProtectData) and return Base64 string."""
        if not plaintext:
            return ""

        data_bytes = plaintext.encode("utf-8")
        in_blob = _bytes_to_blob(data_bytes)
        out_blob = DATA_BLOB()

        CryptProtectData = ctypes.windll.crypt32.CryptProtectData
        CryptProtectData.argtypes = [
            ctypes.POINTER(DATA_BLOB),
            wintypes.LPCWSTR,
            ctypes.POINTER(DATA_BLOB),
            ctypes.c_void_p,
            ctypes.c_void_p,
            wintypes.DWORD,
            ctypes.POINTER(DATA_BLOB),
        ]
        CryptProtectData.restype = wintypes.BOOL

        # CRYPTPROTECT_UI_FORBIDDEN = 0x01
        success = CryptProtectData(ctypes.byref(in_blob), "CorpBrainSecret", None, None, None, 1, ctypes.byref(out_blob))
        if not success:
            raise OSError("Windows DPAPI Encryption failed")

        try:
            encrypted_bytes = ctypes.string_at(out_blob.pbData, out_blob.cbData)
            return base64.b64encode(encrypted_bytes).decode("utf-8")
        finally:
            ctypes.windll.kernel32.LocalFree(out_blob.pbData)

    def decrypt_secret(ciphertext_b64: str) -> str:
        """Decrypt Base64 DPAPI encrypted secret using Windows DPAPI (CryptUnprotectData)."""
        if not ciphertext_b64:
            return ""

        encrypted_bytes = base64.b64decode(ciphertext_b64.encode("utf-8"))
        in_blob = _bytes_to_blob(encrypted_bytes)
        out_blob = DATA_BLOB()

        CryptUnprotectData = ctypes.windll.crypt32.CryptUnprotectData
        CryptUnprotectData.argtypes = [
            ctypes.POINTER(DATA_BLOB),
            ctypes.POINTER(wintypes.LPCWSTR),
            ctypes.POINTER(DATA_BLOB),
            ctypes.c_void_p,
            ctypes.c_void_p,
            wintypes.DWORD,
            ctypes.POINTER(DATA_BLOB),
        ]
        CryptUnprotectData.restype = wintypes.BOOL

        success = CryptUnprotectData(ctypes.byref(in_blob), None, None, None, None, 1, ctypes.byref(out_blob))
        if not success:
            raise OSError("Windows DPAPI Decryption failed")

        try:
            decrypted_bytes = ctypes.string_at(out_blob.pbData, out_blob.cbData)
            return decrypted_bytes.decode("utf-8")
        finally:
            ctypes.windll.kernel32.LocalFree(out_blob.pbData)

else:
    # Non-Windows fallback for unit tests
    def encrypt_secret(plaintext: str) -> str:
        return "MOCK_ENC:" + base64.b64encode(plaintext.encode("utf-8")).decode("utf-8")

    def decrypt_secret(ciphertext_b64: str) -> str:
        if ciphertext_b64.startswith("MOCK_ENC:"):
            return base64.b64decode(ciphertext_b64[9:].encode("utf-8")).decode("utf-8")
        return ciphertext_b64
