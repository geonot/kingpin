#!/usr/bin/env bash
set -e # Exit immediately if a command exits with a non-zero status.

echo "Starting application setup..."

# --- Helper Functions ---
check_command() {
    if ! command -v "$1" &> /dev/null; then
        echo "Error: $1 is not installed or not in PATH. Please install $1 and try again."
        exit 1
    fi
    echo "$1 found."
}

# --- Backend Setup ---
echo ""
echo "=== Setting up Backend ==="

# Clean up previous test database file, if any
echo "Removing old test database file if it exists..."
rm -f casino_be/test_casino_be_isolated.db
echo "Old test database file removed."

# Check prerequisites
check_command python3
check_command pip
check_command pg_isready # Checks for PostgreSQL client tools
check_command openssl

# Install Python dependencies
echo "Installing Python dependencies for the backend..."
(cd casino_be && pip install -r requirements.txt)
echo "Backend Python dependencies installed."

# PostgreSQL setup
echo "Checking PostgreSQL server status..."
if ! pg_isready -q; then
    echo "Error: PostgreSQL server is not running or not accessible."
    echo "Please ensure PostgreSQL is installed, running, and accessible."
    exit 1
fi
echo "PostgreSQL server is ready."

echo ""
echo "Please enter PostgreSQL database details:"
read -r -p "Database User: " DB_USER
read -r -s -p "Database Password: " DB_PASSWORD
echo ""
read -r -p "Database Name: " DB_NAME

export DATABASE_URL="postgresql://${DB_USER}:${DB_PASSWORD}@localhost/${DB_NAME}"

echo ""
echo "Please enter a JWT Secret Key (or press Enter to generate one):"
read -r JWT_SECRET_KEY_INPUT
if [ -z "$JWT_SECRET_KEY_INPUT" ]; then
    echo "Generating a new JWT Secret Key..."
    export JWT_SECRET_KEY=$(openssl rand -hex 32)
    echo "Generated JWT_SECRET_KEY: $JWT_SECRET_KEY"
else
    export JWT_SECRET_KEY="$JWT_SECRET_KEY_INPUT"
fi

# Create .env file in casino_be
ENV_FILE_PATH="casino_be/.env"
echo "Saving backend environment variables to $ENV_FILE_PATH..."
echo "DATABASE_URL=${DATABASE_URL}" > "$ENV_FILE_PATH"
echo "JWT_SECRET_KEY=${JWT_SECRET_KEY}" >> "$ENV_FILE_PATH"
# Add other backend environment variables if needed, e.g. FLASK_APP, FLASK_ENV
echo "FLASK_APP=app.py" >> "$ENV_FILE_PATH"
echo "FLASK_ENV=development" >> "$ENV_FILE_PATH"
echo "Backend environment variables saved to $ENV_FILE_PATH"

# Initialize database
echo "Initializing the database..."
(cd casino_be && flask db init || echo "Database already initialized or error during init. Continuing...")
(cd casino_be && flask db migrate -m "Initial migration from bootstrap" || echo "Migration error or no changes to migrate. Continuing...")
(cd casino_be && flask db upgrade)
echo "Database initialization and upgrade complete."

# Create admin user
echo ""
echo "Let's create an admin user for the backend."
read -r -p "Admin Username: " ADMIN_USERNAME
read -r -p "Admin Email: " ADMIN_EMAIL
read -r -s -p "Admin Password: " ADMIN_PASSWORD
echo ""
echo "Creating admin user..."
(cd casino_be && flask create_admin --username "$ADMIN_USERNAME" --email "$ADMIN_EMAIL" --password "$ADMIN_PASSWORD")
echo "Admin user creation attempted."


# --- Frontend Setup ---
echo ""
echo "=== Setting up Frontend ==="

# Check prerequisites
check_command node
check_command npm

# Install Node.js dependencies
echo "Installing Node.js dependencies for the frontend..."
(cd casino_fe && npm install)
echo "Frontend Node.js dependencies installed."

# --- Health Checks ---
echo ""
echo "=== Performing Health Checks ==="

BACKEND_PID=""

cleanup() {
    echo "Cleaning up background processes..."
    if [ -n "$BACKEND_PID" ]; then
        echo "Stopping backend server (PID: $BACKEND_PID)..."
        # Attempt to kill the process group first, then the specific PID
        kill -TERM -$BACKEND_PID 2>/dev/null || kill -TERM $BACKEND_PID 2>/dev/null || echo "Backend server (PID: $BACKEND_PID) already stopped or could not be stopped."
        wait $BACKEND_PID 2>/dev/null # Wait for the process to actually terminate
        echo "Backend server stopped."
    fi
    BACKEND_PID="" # Reset PID after stopping
}

# Trap EXIT, INT, TERM signals to run cleanup
trap cleanup EXIT INT TERM

perform_health_checks() {
    # Backend Health Check
    echo "Starting backend server for health check..."
    (
        cd casino_be
        # Ensure environment variables are available for the health check server
        # Sourcing .env here makes them available for this subshell
        if [ -f ".env" ]; then
            echo "Sourcing .env file for health check backend..."
            set -a # Automatically export all variables
            source .env
            set +a
        else
            echo "Warning: casino_be/.env file not found. Health check backend might not start correctly."
            # Essential vars must be set if .env is not found; assuming they are exported from main script
        fi
        # Start Flask in background, redirect output, and get PID
        # Use setsid to run in a new session, making it easier to kill the process group
        setsid flask run --host=0.0.0.0 --port=5001 &> backend_health_check.log &
        BACKEND_PID=$!
        echo "$BACKEND_PID" > ../backend_pid.txt # Save PID to a file to pass it to the parent shell
    )
    # Read PID from file because subshell variable assignments don't persist
    if [ -f backend_pid.txt ]; then
        BACKEND_PID=$(cat backend_pid.txt)
        rm backend_pid.txt
    else
        echo "Error: Could not retrieve backend PID for health check."
        BACKEND_PID="" # Ensure it's empty
    fi

    if [ -n "$BACKEND_PID" ]; then
        echo "Backend server started for health check (PID: $BACKEND_PID). Log: casino_be/backend_health_check.log"
        echo "Waiting for backend to initialize (approx. 15 seconds)..."
        sleep 15

        echo "Performing backend GET request to /api/slots..."
        if curl --fail --silent -o /dev/null http://localhost:5001/api/slots; then
            echo "Backend health check: PASSED"
        else
            echo "Backend health check: FAILED. Check casino_be/backend_health_check.log for details."
        fi
    else
        echo "Backend health check: SKIPPED (Could not start server)."
    fi

    # Stop the backend server explicitly after the check
    cleanup # This will also reset BACKEND_PID

    # Frontend Health Check (Placeholder)
    echo "Frontend health check: Not automatically implemented. Please manually verify the frontend after script completion."
}

perform_health_checks

# Ensure trap is reset if no longer needed or script is ending normally
trap - EXIT INT TERM


echo ""
echo "========================================"
echo "Application setup script finished!"
echo "========================================"
echo ""
echo "IMPORTANT: Review any error messages above to ensure setup was fully successful."
echo ""
echo "To run the application:"
echo "1. Start the backend server:"
echo "   cd casino_be"
echo "   source .env  # Or ensure DATABASE_URL and JWT_SECRET_KEY are set in your environment"
echo "   flask run --host=0.0.0.0"
echo "   (The backend will typically be available at http://localhost:5000)"
echo ""
echo "2. Start the frontend server (in a new terminal):"
echo "   cd casino_fe"
echo "   npm run serve"
echo "   (The frontend will typically be available at http://localhost:8080)"
echo ""
echo "Admin credentials for login:"
echo "Username: $ADMIN_USERNAME"
echo "Email: $ADMIN_EMAIL"
echo "Password: [the password you entered]"
echo ""
```
