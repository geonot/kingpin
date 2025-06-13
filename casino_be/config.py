import os

class Config:
    # Database configuration - PostgreSQL for both development and production
    DATABASE_URL = os.getenv('DATABASE_URL')
    
    if DATABASE_URL:
        # Use provided DATABASE_URL
        SQLALCHEMY_DATABASE_URI = DATABASE_URL
    else:
        # Build from individual components for local development
        DB_HOST = os.getenv('DB_HOST', 'localhost')
        DB_PORT = os.getenv('DB_PORT', '5432')
        DB_NAME = os.getenv('DB_NAME', 'kingpin_casino')
        DB_USER = os.getenv('DB_USER', 'kingpin_user')
        DB_PASSWORD = os.getenv('DB_PASSWORD', 'password123')
        
        SQLALCHEMY_DATABASE_URI = f'postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}'
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # JWT Secret - use default for development
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'dev-secret-key-change-in-production')
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
    DEBUG = os.getenv('FLASK_DEBUG', 'True').lower() in ('true', '1', 't')

    # Satoshi Conversion Factor (1 BTC = 100,000,000 Satoshis)
    SATOSHI_FACTOR = 100_000_000
