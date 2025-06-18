import base64
import os
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from flask import current_app
import logging

logger = logging.getLogger(__name__)

def get_encryption_key():
    """
    Generate or retrieve encryption key for private key storage.
    
    WARNING: This is a basic implementation for development.
    In production, use proper key management services like AWS KMS, 
    Azure Key Vault, or HashiCorp Vault.
    """
    # Use a secret from config or environment
    secret = current_app.config.get('ENCRYPTION_SECRET', 'default-encryption-secret-change-in-production')
    
    # Generate a salt (in production, this should be stored securely)
    salt = b'kingpin_casino_salt_2024'  # Use a consistent salt for now
    
    # Derive key from secret
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(secret.encode()))
    return key

def encrypt_private_key(private_key_wif: str) -> str:
    """
    Encrypt a private key WIF string.
    
    Args:
        private_key_wif (str): The private key in WIF format
        
    Returns:
        str: Base64 encoded encrypted private key
    """
    try:
        key = get_encryption_key()
        f = Fernet(key)
        encrypted_data = f.encrypt(private_key_wif.encode())
        return base64.urlsafe_b64encode(encrypted_data).decode()
    except Exception as e:
        logger.error(f"Failed to encrypt private key: {e}")
        raise

def decrypt_private_key(encrypted_private_key: str) -> str:
    """
    Decrypt an encrypted private key.
    
    Args:
        encrypted_private_key (str): Base64 encoded encrypted private key
        
    Returns:
        str: Decrypted private key in WIF format
    """
    try:
        key = get_encryption_key()
        f = Fernet(key)
        encrypted_data = base64.urlsafe_b64decode(encrypted_private_key.encode())
        decrypted_data = f.decrypt(encrypted_data)
        return decrypted_data.decode()
    except Exception as e:
        logger.error(f"Failed to decrypt private key: {e}")
        raise
