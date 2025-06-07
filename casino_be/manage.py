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

import click # For prompting user input

# Optional: Command to create admin user (if needed outside app run)
@manager.option('-u', '--username', dest='username', default=None, help='Admin username')
@manager.option('-e', '--email', dest='email', default=None, help='Admin email')
@manager.option('-p', '--password', dest='password', default=None, help='Admin password (will be prompted if not provided)')
def create_admin(username, email, password):
    """Creates an admin user with the given credentials."""
    from models import User # Import locally to avoid circular dependency issues
    from utils.bitcoin import generate_bitcoin_wallet # Ensure this utility is available

    if not username:
        username = click.prompt("Enter admin username")
    if not email:
        email = click.prompt("Enter admin email")
    if not password:
        password = click.prompt("Enter admin password", hide_input=True, confirmation_prompt=True)

    existing_user = User.query.filter((User.username == username) | (User.email == email)).first()
    if existing_user:
        if existing_user.username == username:
            print(f"Error: User with username '{username}' already exists.")
        if existing_user.email == email: # Check separately to provide specific message if email also matches
            print(f"Error: User with email '{email}' already exists.")
        return

    print(f"Creating admin user: {username}")
    try:
        admin_wallet_addr = generate_bitcoin_wallet() # Now only returns address
        if not admin_wallet_addr:
            print("Failed to generate wallet address for admin user. Aborting.")
            return

        admin_user = User(
            username=username,
            email=email,
            password=User.hash_password(password), # Hash the provided password
            is_admin=True,
            balance=1_000_000_000, # Default 10 BTC in Sats, can be adjusted later
            deposit_wallet_address=admin_wallet_addr
        )
        db.session.add(admin_user)
        db.session.commit()
        print(f"Admin user '{username}' created successfully with email '{email}'.")
    except Exception as e:
         db.session.rollback()
         print(f"Failed to create admin user: {e}")

# The flask_script manager.run() will only execute flask_script commands.
# The new command 'db_cleanup_expired_tokens' needs to be run via `flask db_cleanup_expired_tokens`.
# That command has been moved to app.py for Flask's native CLI discovery.
if __name__ == '__main__':
    # Note: This will only run flask_script commands.
    # To run app.cli commands, use `flask <command_name>`.
    manager.run()
    # Usage:
    # python manage.py db init (only once)
    # python manage.py db migrate -m "Description of changes"
    # python manage.py db upgrade
    # python manage.py runserver
    # python manage.py create_admin
