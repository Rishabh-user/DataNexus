from cryptography.fernet import Fernet

from app.core.config import settings


def get_fernet() -> Fernet:
    if not settings.fernet_key:
        raise ValueError("FERNET_KEY not configured. Generate one with: python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'")
    return Fernet(settings.fernet_key.encode())


def encrypt_value(value: str) -> str:
    return get_fernet().encrypt(value.encode()).decode()


def decrypt_value(encrypted_value: str) -> str:
    return get_fernet().decrypt(encrypted_value.encode()).decode()
