"""
API key encryption at rest (DEC-12).

Windows DPAPI (``CryptProtectData`` / ``CryptUnprotectData`` via ``ctypes``) is the only
sanctioned mechanism: it binds the ciphertext to the current user account, needs no master
key, and adds no dependency.

There is deliberately **no non-Windows implementation.** DPAPI has no cross-platform
equivalent that satisfies DEC-12, and the previous fallback here returned
``"MOCK_ENC:" + base64(plaintext)`` — reversible by anyone with the DB file, i.e. plaintext
at rest, which is exactly what DEC-12 forbids ("never store the key in plaintext"). It was
labelled "for unit tests" but nothing confined it to tests: ``ConfigManager.set_api_key``
called it on any host, so a developer entering a real key on macOS wrote a recoverable key
to disk.

Off Windows, persistence raises ``SecretStorageUnavailableError``. A developer who needs to
exercise Option A supplies the key through ``CORPBRAIN_ANTHROPIC_API_KEY``, which is read
into memory at call time and never written anywhere — see ``ConfigManager.get_api_key``.
"""

import base64
import sys

from src.backend.utils.platform_compat import IS_WINDOWS


class SecretStorageUnavailableError(RuntimeError):
    """
    Raised when secret storage is requested on a host that has no DPAPI.

    Distinct from a DPAPI *failure* (wrong account/PC), which DEC-12 requires to surface as a
    re-entry prompt. This one means "this host can never store it", so the caller must not
    offer re-entry — it would fail identically every time.
    """


if IS_WINDOWS:
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
    _UNAVAILABLE = (
        f"API key storage requires Windows DPAPI (DEC-12) and this host is {sys.platform}. "
        "Set CORPBRAIN_ANTHROPIC_API_KEY in the environment to exercise Option A during "
        "development; the key is held in memory only and never written to the database."
    )

    def encrypt_secret(plaintext: str) -> str:
        raise SecretStorageUnavailableError(_UNAVAILABLE)

    def decrypt_secret(ciphertext_b64: str) -> str:
        raise SecretStorageUnavailableError(_UNAVAILABLE)
