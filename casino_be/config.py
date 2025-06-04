import os

class Config:
    # PostgreSQL Database URI with fallback for development
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL') or 'postgresql://postgres:password@localhost:5432/kingpin_casino_dev'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # JWT Secret with fallback for development (change in production!)
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY') or 'dev-secret-key-change-in-production'
    JWT_ACCESS_TOKEN_EXPIRES = 3600  # 1 hour
    JWT_REFRESH_TOKEN_EXPIRES = 86400 * 7 # 7 days
    JWT_BLACKLIST_ENABLED = True
    JWT_BLACKLIST_TOKEN_CHECKS = ['access', 'refresh'] # Check both token types

    # Rate Limiter Storage URI
    # For production, set e.g., RATELIMIT_STORAGE_URI='redis://localhost:6379/0'
    RATELIMIT_STORAGE_URI = os.getenv('RATELIMIT_STORAGE_URI', 'memory://')

    # Flask Debug Mode
    # For production, ensure FLASK_DEBUG is not set or set to 'False'.
    # Set FLASK_DEBUG to 'True' or '1' for development.
    DEBUG = os.getenv('FLASK_DEBUG', 'False').lower() in ('true', '1', 't')

    # Satoshi Conversion Factor (1 BTC = 100,000,000 Satoshis)
    SATOSHI_FACTOR = 100_000_000

    # Admin settings with fallbacks for development
    ADMIN_USERNAME = os.getenv('ADMIN_USERNAME', 'admin')
    ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'admin123')  # Change in production!
    ADMIN_EMAIL = os.getenv('ADMIN_EMAIL', 'admin@kingpincasino.local')
