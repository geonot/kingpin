import os

class Config:
    # Use BigInteger for balance, so default URI might need adjustment if using specific drivers
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'postgresql:///rome')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'super-secret-kingpin-key') # Changed default key
    JWT_ACCESS_TOKEN_EXPIRES = 3600  # 1 hour
    JWT_REFRESH_TOKEN_EXPIRES = 86400 * 7 # 7 days
    JWT_BLACKLIST_ENABLED = True
    JWT_BLACKLIST_TOKEN_CHECKS = ['access', 'refresh'] # Check both token types

    # Satoshi Conversion Factor (1 BTC = 100,000,000 Satoshis)
    SATOSHI_FACTOR = 100_000_000

    # Admin settings
    ADMIN_USERNAME = os.getenv('ADMIN_USERNAME', 'admin')
    ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'ChangeMe123!') # Make sure to change this!
    ADMIN_EMAIL = os.getenv('ADMIN_EMAIL', 'admin@kingpincasino.local')


