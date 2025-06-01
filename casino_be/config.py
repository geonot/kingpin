import os

class Config:
    # Mandatory: Database URI. Must be set in the environment.
    # Example: export DATABASE_URL='postgresql://user:password@host:port/dbname'
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL')
    if not SQLALCHEMY_DATABASE_URI:
        raise ValueError("No DATABASE_URL set for Flask application. Please set it in your environment.")

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Mandatory: Secret key for JWT. Must be set in the environment.
    # Example: export JWT_SECRET_KEY='your-super-strong-secret-key'
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY')
    if not JWT_SECRET_KEY:
        raise ValueError("No JWT_SECRET_KEY set for Flask application. Please set it in your environment.")

    JWT_ACCESS_TOKEN_EXPIRES = 3600  # 1 hour
    JWT_REFRESH_TOKEN_EXPIRES = 86400 * 7 # 7 days
    JWT_BLACKLIST_ENABLED = True
    JWT_BLACKLIST_TOKEN_CHECKS = ['access', 'refresh'] # Check both token types

    # Satoshi Conversion Factor (1 BTC = 100,000,000 Satoshis)
    SATOSHI_FACTOR = 100_000_000

    # Admin settings
    # Optional: Admin username. Can be set in the environment. Defaults to 'admin'.
    # Example: export ADMIN_USERNAME='myadmin'
    ADMIN_USERNAME = os.getenv('ADMIN_USERNAME', 'admin')

    # Mandatory: Admin password. Must be set in the environment.
    # Example: export ADMIN_PASSWORD='your-secure-admin-password'
    ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD')
    if not ADMIN_PASSWORD:
        raise ValueError("No ADMIN_PASSWORD set for Flask application. Please set it in your environment.")

    # Optional: Admin email. Can be set in the environment. Defaults to 'admin@kingpincasino.local'.
    # Example: export ADMIN_EMAIL='admin@example.com'
    ADMIN_EMAIL = os.getenv('ADMIN_EMAIL', 'admin@kingpincasino.local')
