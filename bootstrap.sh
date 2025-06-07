#!/usr/bin/env bash

# Exit immediately if a command exits with a non-zero status.
set -e

# Bootstrap script for setting up the casino application
echo "Starting application setup..."
echo "This script will guide you through setting up the Casino application."
echo "It will install dependencies, configure the database, and set up the frontend."
echo "---------------------------------------------------------------------"

# --- Tooling Checks ---
echo "Checking for required tools..."

# Check for Python 3 and pip
echo "Checking for Python 3 and pip..."
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is not installed. Please install Python 3 and try again."
    exit 1
fi
if ! command -v pip &> /dev/null; then
    echo "Error: pip (Python package installer) is not installed. Please install pip and try again."
    exit 1
fi
echo "Python 3 and pip found."

# Check for PostgreSQL
echo "Checking for PostgreSQL..."
if ! command -v pg_isready &> /dev/null; then
    echo "Error: pg_isready command not found. Please install PostgreSQL client tools."
    exit 1
fi
if ! pg_isready -q; then
    echo "Error: PostgreSQL is not running or not accessible. Please ensure PostgreSQL is installed, running, and accessible."
    echo "You can typically start PostgreSQL using a command like: sudo systemctl start postgresql"
    exit 1
fi
echo "PostgreSQL is running and accessible."

# Check for openssl
echo "Checking for openssl..."
if ! command -v openssl &> /dev/null; then
    echo "Error: openssl command not found. Please install openssl."
    exit 1
fi
echo "openssl found."

# Check for Node.js and npm
echo "Checking for Node.js and npm..."
if ! command -v node &> /dev/null; then
    echo "Error: Node.js is not installed. Please install Node.js and try again."
    exit 1
fi
if ! command -v npm &> /dev/null; then
    echo "Error: npm (Node Package Manager) is not installed. Please install npm and try again."
    exit 1
fi
echo "Node.js and npm found."
echo "All required tools are available."
echo "---------------------------------------------------------------------"

# --- Backend Setup ---
echo "Setting up backend..."

# Install Python dependencies
echo "Installing Python dependencies for the backend..."
cd casino_be
echo "Current directory: $(pwd)"
echo "Attempting to install dependencies from requirements.txt..."
if ! pip install -r requirements.txt; then
    echo "Error: Failed to install Python dependencies. Please check requirements.txt and ensure pip is working correctly."
    cd ..
    exit 1
fi
cd ..
echo "Python dependencies installed successfully."
echo "---------------------------------------------------------------------"

# Database Configuration
echo "Configuring the database..."
echo "Please enter your PostgreSQL database credentials. The script will use these to connect to your database."
read -p "DB_USER (e.g., postgres): " DB_USER
read -s -p "DB_PASSWORD: " DB_PASSWORD
echo
read -p "DB_NAME (e.g., casino_db): " DB_NAME

export DATABASE_URL="postgresql://$DB_USER:$DB_PASSWORD@localhost/$DB_NAME"
echo "DATABASE_URL has been set for this session: postgresql://$DB_USER:********@localhost/$DB_NAME"
echo "Note: You might need to set this environment variable manually in your shell profile for future sessions."

echo "Please provide a JWT_SECRET_KEY. This key is used for signing authentication tokens."
read -p "Enter JWT_SECRET_KEY (leave blank to generate a random one automatically): " JWT_SECRET_KEY
if [ -z "$JWT_SECRET_KEY" ]; then
    echo "Generating a random JWT_SECRET_KEY..."
    JWT_SECRET_KEY=$(openssl rand -hex 32)
    echo "Generated JWT_SECRET_KEY: $JWT_SECRET_KEY"
fi
export JWT_SECRET_KEY
echo "JWT_SECRET_KEY has been set for this session."
echo "Note: You might need to set this environment variable manually in your shell profile for future sessions."
echo "---------------------------------------------------------------------"

# Initialize the database
echo "Initializing the database..."
cd casino_be
echo "Current directory: $(pwd)"
echo "Running database initialization (db init)..."
if ! python manage.py db init; then
    echo "Warning: 'python manage.py db init' failed. This might be because the database is already initialized. Continuing..."
fi
echo "Running database migrations (db migrate)..."
if ! python manage.py db migrate; then
    echo "Error: Failed to migrate database. Please check your database connection, models, and the DATABASE_URL environment variable."
    cd ..
    exit 1
fi
echo "Applying database upgrades (db upgrade)..."
if ! python manage.py db upgrade; then
    echo "Error: Failed to upgrade database. Please check your database connection and migration scripts."
    cd ..
    exit 1
fi
cd ..
echo "Database initialized and migrations applied successfully."
echo "---------------------------------------------------------------------"

# Create an admin user
echo "Creating an admin user for the application..."
cd casino_be
echo "Current directory: $(pwd)"
echo "Please provide details for the admin user:"
read -p "Admin username: " ADMIN_USERNAME
read -p "Admin email: " ADMIN_EMAIL
read -s -p "Admin password: " ADMIN_PASSWORD
echo
echo "Attempting to create admin user..."
if ! python manage.py create_admin --username "$ADMIN_USERNAME" --email "$ADMIN_EMAIL" --password "$ADMIN_PASSWORD"; then
    echo "Error: Failed to create admin user. Please check your input and ensure the database is set up correctly."
    cd ..
    exit 1
fi
cd ..
echo "Admin user created successfully."
echo "Backend setup complete."
echo "---------------------------------------------------------------------"

# --- Frontend Setup ---
echo "Setting up frontend..."

# Install Node.js dependencies
echo "Installing Node.js dependencies for the frontend..."
cd casino_fe
echo "Current directory: $(pwd)"
echo "Attempting to install dependencies using npm install..."
if ! npm install; then
    echo "Error: Failed to install Node.js dependencies. Please check package.json and ensure npm is working correctly."
    cd ..
    exit 1
fi
cd ..
echo "Node.js dependencies installed successfully."
echo "Frontend setup complete."
echo "---------------------------------------------------------------------"

echo "🎉 Application setup successful! 🎉"
echo ""
echo "Next steps to run the application:"
echo "1. Ensure your PostgreSQL server is running."
echo "2. Open a new terminal for the backend server:"
echo "   cd casino_be"
echo "   export DATABASE_URL=\"postgresql://$DB_USER:$DB_PASSWORD@localhost/$DB_NAME\"  # (Use the credentials you provided)"
echo "   export JWT_SECRET_KEY=\"$JWT_SECRET_KEY\"  # (Use the key you provided or was generated)"
echo "   python app.py"
echo ""
echo "3. Open another new terminal for the frontend server:"
echo "   cd casino_fe"
echo "   npm run serve"
echo ""
echo "Enjoy the Casino App!"
