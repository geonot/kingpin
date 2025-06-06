import os

class Config:
    # PostgreSQL Database URI
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL')
    if SQLALCHEMY_DATABASE_URI is None:
        raise ValueError("DATABASE_URL environment variable not set.")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # JWT Secret
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY')
    if JWT_SECRET_KEY is None:
        raise ValueError("JWT_SECRET_KEY environment variable not set.")
    JWT_ACCESS_TOKEN_EXPIRES = 3600  # 1 hour
    JWT_REFRESH_TOKEN_EXPIRES = 86400 * 7 # 7 days
    JWT_BLACKLIST_ENABLED = True
    JWT_BLACKLIST_TOKEN_CHECKS = ['access', 'refresh'] # Check both token types

    # Rate Limiter Storage URI
    # For production, set e.g., RATELIMIT_STORAGE_URI='redis://localhost:6379/0'
    # Changed from memory:// to redis://localhost:6379/0.
    # It's recommended to use a persistent Redis instance in production.
    RATELIMIT_STORAGE_URI = 'redis://localhost:6379/0'

    # Flask Debug Mode
    # For production, ensure FLASK_DEBUG is not set or set to 'False'.
    # Set FLASK_DEBUG to 'True' or '1' for development.
    DEBUG = os.getenv('FLASK_DEBUG', 'False').lower() in ('true', '1', 't')

    # Satoshi Conversion Factor (1 BTC = 100,000,000 Satoshis)
    SATOSHI_FACTOR = 100_000_000

    # Admin settings
    ADMIN_USERNAME = os.getenv('ADMIN_USERNAME', 'admin') # Fallback for username is acceptable for now
    ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD')
    if ADMIN_PASSWORD is None:
        raise ValueError("ADMIN_PASSWORD environment variable not set. This is required for initial admin setup if no admin user exists or if using a default admin creation process that relies on it.")
    ADMIN_EMAIL = os.getenv('ADMIN_EMAIL', 'admin@kingpincasino.local') # Fallback for email is acceptable for now
