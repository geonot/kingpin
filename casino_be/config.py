"""
Secure configuration module with fail-fast validation.

All configuration values are validated at startup with no insecure defaults.
Production environments must provide all required environment variables.
"""
import os
from config_validator import validate_production_config

class Config:
    """Production-ready configuration with fail-fast validation."""
    
    # Validate configuration and get secure values
    _validated_config = validate_production_config()
    
    # Database Configuration
    SQLALCHEMY_DATABASE_URI = _validated_config['SQLALCHEMY_DATABASE_URI']
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # JWT Configuration - Enhanced Security
    JWT_SECRET_KEY = _validated_config['JWT_SECRET_KEY']
    JWT_ACCESS_TOKEN_EXPIRES = _validated_config['JWT_ACCESS_TOKEN_EXPIRES']
    JWT_REFRESH_TOKEN_EXPIRES = _validated_config['JWT_REFRESH_TOKEN_EXPIRES']
    JWT_BLACKLIST_ENABLED = True
    JWT_BLACKLIST_TOKEN_CHECKS = ['access', 'refresh']
    
    # JWT Cookie Configuration for enhanced security
    JWT_TOKEN_LOCATION = ['cookies']
    JWT_COOKIE_SECURE = _validated_config['JWT_COOKIE_SECURE']
    JWT_COOKIE_HTTPONLY = True
    JWT_COOKIE_SAMESITE = 'Strict'
    JWT_COOKIE_CSRF_PROTECT = True
    JWT_ACCESS_COOKIE_NAME = 'access_token_cookie'
    JWT_REFRESH_COOKIE_NAME = 'refresh_token_cookie'
    JWT_ACCESS_CSRF_HEADER_NAME = 'X-CSRF-Token'
    JWT_REFRESH_CSRF_HEADER_NAME = 'X-CSRF-Token'
    
    # Session Configuration
    SESSION_COOKIE_SECURE = JWT_COOKIE_SECURE
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Strict'
    
    # Security Headers
    SECURITY_HEADERS = True

    # Rate Limiter Storage URI - Validated for production
    RATELIMIT_STORAGE_URI = _validated_config['RATELIMIT_STORAGE_URI']

    # Flask Debug Mode - Validated and secure
    DEBUG = _validated_config['DEBUG']

    # Satoshi Conversion Factor (1 BTC = 100,000,000 Satoshis)
    SATOSHI_FACTOR = 100_000_000

    # Admin settings - Validated with fail-fast for production
    ADMIN_USERNAME = _validated_config['ADMIN_USERNAME']
    ADMIN_PASSWORD = _validated_config['ADMIN_PASSWORD']
    ADMIN_EMAIL = _validated_config['ADMIN_EMAIL']

    # Service API Token - Validated for production security
    SERVICE_API_TOKEN = _validated_config['SERVICE_API_TOKEN']

    # Encryption key for private key storage - Validated and secure
    ENCRYPTION_SECRET = _validated_config['ENCRYPTION_SECRET']
    
    # CORS Configuration - Validated for production
    CORS_ORIGINS_LIST = _validated_config['CORS_ORIGINS']
    
    # Feature Flags
    CRYSTAL_GARDEN_ENABLED = _validated_config['CRYSTAL_GARDEN_ENABLED']

    # Feature Flags
    CRYSTAL_GARDEN_ENABLED = os.getenv('CRYSTAL_GARDEN_ENABLED', 'True').lower() in ('true', '1', 't')


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///./test_casino_be_isolated.db' # File-based for test isolation using SQLite
    # Define a key to store the database file path for easy cleanup
    DATABASE_FILE_PATH = SQLALCHEMY_DATABASE_URI.replace('sqlite:///', '') # Adjusted for SQLite
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JWT_SECRET_KEY = 'test-jwt-secret-key'
    # Disable CSRF protection for tests if applicable (e.g., if using Flask-WTF)
    WTF_CSRF_ENABLED = False
    JWT_COOKIE_CSRF_PROTECT = False # Disable JWT CSRF for tests
    # Disable rate limiting for tests
    RATELIMIT_ENABLED = False
    RATELIMIT_DEFAULT_LIMITS_ENABLED = False
    # Ensure engine options for SQLite are appropriate if not using in-memory
    SQLALCHEMY_ENGINE_OPTIONS = {
        'connect_args': {'check_same_thread': False}
        # StaticPool is not typically needed for file-based DBs,
        # as file ensures persistence across connections.
    }
