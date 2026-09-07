import base64
import hashlib
from django.conf import settings
from cryptography.fernet import Fernet


class TokenEncryptionService:
    """
    Symmetric Encryption abstraction for sensitive Telegram Bot tokens.
    Uses Fernet (AES-128-CBC + HMAC-SHA256 authentication).
    """

    @classmethod
    def _get_fernet_instance(cls) -> Fernet:
        raw_key = getattr(settings, 'ENCRYPTION_KEY', 'default-fallback-secret-key-32bytes!')
        # Derive valid 32-byte base64 key using SHA-256
        key_bytes = hashlib.sha256(raw_key.encode('utf-8')).digest()
        base64_key = base64.urlsafe_b64encode(key_bytes)
        return Fernet(base64_key)

    @classmethod
    def encrypt_token(cls, plain_token: str) -> str:
        """Encrypts plain bot token into encrypted Fernet token string."""
        if not plain_token:
            return ""
        fernet = cls._get_fernet_instance()
        encrypted_bytes = fernet.encrypt(plain_token.encode('utf-8'))
        return encrypted_bytes.decode('utf-8')

    @classmethod
    def decrypt_token(cls, encrypted_token: str) -> str:
        """Decrypts Fernet token back into plaintext token."""
        if not encrypted_token:
            return ""
        fernet = cls._get_fernet_instance()
        decrypted_bytes = fernet.decrypt(encrypted_token.encode('utf-8'))
        return decrypted_bytes.decode('utf-8')

    @classmethod
    def mask_token(cls, plain_token: str) -> str:
        """
        Masks plain token for API presentation.
        Example: 8741801900:AAHtCUxO2zvG737po1_2mTOEW_hr8lA657g -> 8741****657g
        """
        if not plain_token or len(plain_token) < 10:
            return "****"
        return f"{plain_token[:4]}****{plain_token[-4:]}"
