#! /usr/bin/env python
import os
from flask_migrate import Migrate, MigrateCommand
from flask_script import Manager, Server # Use flask_script's Server for consistency

# Set FLASK_APP environment variable if not set
if not os.environ.get('FLASK_APP'):
    os.environ['FLASK_APP'] = 'app.py' # Point to your Flask app file

try:
    from app import app, db
except ImportError as e:
    print(f"Error importing Flask app: {e}")
    print("Ensure your Flask app instance is named 'app' in app.py and PYTHONPATH is correct.")
    exit(1)
except Exception as e:
    print(f"An unexpected error occurred during import: {e}")
    exit(1)

migrate = Migrate(app, db)
manager = Manager(app)

# Add 'db' command group for migrations
manager.add_command('db', MigrateCommand)

# Add 'runserver' command - more explicit than default 'run'
# Use host='0.0.0.0' to make it accessible externally if needed (e.g., in Docker)
manager.add_command("runserver", Server(host="127.0.0.1", port=5000, use_debugger=True, use_reloader=True))

# Optional: Command to create admin user (if needed outside app run)
@manager.command
def create_admin():
    """Creates the default admin user if it doesn't exist."""
    from models import User # Import locally to avoid circular dependency issues
    from config import Config
    from utils.bitcoin import generate_bitcoin_wallet

    if not User.query.filter_by(username=Config.ADMIN_USERNAME).first():
        print(f"Creating default admin user: {Config.ADMIN_USERNAME}")
        try:
            admin_wallet_addr, admin_priv_key = generate_bitcoin_wallet()
            admin_user = User(
                username=Config.ADMIN_USERNAME,
                email=Config.ADMIN_EMAIL,
                password=User.hash_password(Config.ADMIN_PASSWORD),
                is_admin=True,
                balance=1_000_000_000, # 10 BTC in Sats
                deposit_wallet_address=admin_wallet_addr,
                deposit_wallet_private_key=admin_priv_key # Insecure for production
            )
            db.session.add(admin_user)
            db.session.commit()
            print(f"Admin user '{Config.ADMIN_USERNAME}' created successfully.")
        except Exception as e:
             db.session.rollback()
             print(f"Failed to create admin user: {e}")
    else:
        print(f"Admin user '{Config.ADMIN_USERNAME}' already exists.")

if __name__ == '__main__':
    manager.run()
    # Usage:
    # python manage.py db init (only once)
    # python manage.py db migrate -m "Description of changes"
    # python manage.py db upgrade
    # python manage.py runserver
    # python manage.py create_admin

