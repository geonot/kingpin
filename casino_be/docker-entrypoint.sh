#!/bin/bash
set -e

# Function to check if PostgreSQL is ready
wait_for_postgres() {
    echo "Attempting to connect to PostgreSQL..."
    # Extract connection info from DATABASE_URL
    # Format: postgresql://user:password@host:port/dbname
    if [[ -z "$DATABASE_URL" ]]; then
        echo "Error: DATABASE_URL environment variable is not set."
        exit 1
    fi

    # Simple regex to extract host and port. Assumes standard format.
    # This might need to be more robust depending on URL variations.
    DB_HOST=$(echo $DATABASE_URL | sed -n 's/.*@\([^:]*\):.*/\1/p')
    DB_PORT=$(echo $DATABASE_URL | sed -n 's/.*:\([0-9]*\)\/.*/\1/p')
    DB_USER=$(echo $DATABASE_URL | sed -n 's/postgresql:\/\/\([^:]*\):.*/\1/p')

    # Use default values if not extracted (e.g. if port is not in URL)
    if [[ -z "$DB_HOST" ]]; then
       DB_HOST_DEFAULT=$(echo $DATABASE_URL | sed -n 's/.*@\([^/]*\)\/.*/\1/p') # Handles case where port is not specified
       if [[ "$DB_HOST_DEFAULT" == *"@"* || -z "$DB_HOST_DEFAULT" ]]; then # check if it's part of user/pass or empty
         echo "Could not parse DB_HOST from DATABASE_URL. Assuming 'localhost' or relying on pg_isready's default behavior if PGDATABASE is set."
         DB_HOST="localhost" # Default or fallback
       else
         DB_HOST=$DB_HOST_DEFAULT
       fi
    fi
    if [[ -z "$DB_PORT" ]]; then
        DB_PORT="5432" # Default PostgreSQL port
    fi
     if [[ -z "$DB_USER" ]]; then
        echo "Could not parse DB_USER from DATABASE_URL."
        # pg_isready might still work if other PG* env vars are set, or use default
    fi

    echo "Using Host: $DB_HOST, Port: $DB_PORT, User: $DB_USER for pg_isready check."

    max_attempts=30
    attempt_num=1
    until pg_isready -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -q; do
        if [ ${attempt_num} -gt ${max_attempts} ]; then
            echo "PostgreSQL did not become available after ${max_attempts} attempts."
            exit 1
        fi
        echo "PostgreSQL is unavailable - sleeping for 2s (attempt ${attempt_num}/${max_attempts})"
        sleep 2
        attempt_num=$((attempt_num+1))
    done
    echo "PostgreSQL is up and running!"
}

# Wait for PostgreSQL to be ready
wait_for_postgres

# Apply database migrations
echo "Applying database migrations..."
flask db upgrade
echo "Database migrations applied."

# Optional: Create admin user if specified by environment variables
# This is useful for initial setup, especially in automated environments.
if [ "$CREATE_ADMIN_USER" = "true" ] && [ -n "$ADMIN_USERNAME" ] && [ -n "$ADMIN_EMAIL" ] && [ -n "$ADMIN_PASSWORD" ]; then
    echo "Attempting to create admin user..."
    if flask create_admin --username "$ADMIN_USERNAME" --email "$ADMIN_EMAIL" --password "$ADMIN_PASSWORD"; then
        echo "Admin user creation command executed successfully."
    else
        echo "Admin user creation command failed or user might already exist."
    fi
else
    echo "Skipping admin user creation (CREATE_ADMIN_USER not 'true' or required variables not set)."
fi

# Execute the main command (passed as arguments to this script)
echo "Executing command: $@"
exec "$@"
