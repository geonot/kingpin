# Flask Backend with JWT Authentication and Bitcoin Integration

This project is a Flask-based backend that implements user authentication, session management, Bitcoin address generation, and an admin dashboard. The application uses JWT tokens for secure authentication and manages user sessions for slot games.

## Prerequisites

- Python 3.x
- PostgreSQL (or another SQL database)
- `pip` (Python package manager)

## Installation

1. **Clone the Repository**:

    ```bash
    git clone https://your-repository-url.git
    cd your-repository-directory
    ```

2. **Install Dependencies**:

    ```bash
    pip install -r requirements.txt
    ```

3. **Configure Environment Variables**:

    Set the following environment variables in your shell or in a `.env` file.
    Many of these have default values suitable for development, but **MUST be changed for production environments.**
    The application will fail to start if `DATABASE_URL` (or its components) or `JWT_SECRET_KEY` are not effectively set.

    Key variables to configure (see full list below for more details):
    ```bash
    # Database Configuration (ensure one method is fully set)
    export DATABASE_URL="postgresql://user:password@host:port/dbname" # Recommended for production
    # OR set individual components:
    # export DB_HOST="your_db_host"
    # export DB_PORT="5432"
    # export DB_NAME="your_db_name"
    # export DB_USER="your_db_user"
    # export DB_PASSWORD="your_strong_db_password"

    export JWT_SECRET_KEY="your-very-strong-unique-secret-key" # CRITICAL: MUST be changed for production.
    export FLASK_DEBUG="False" # CRITICAL: MUST be False for production.
    export CORS_ALLOWED_ORIGINS="https://yourfrontend.com" # CRITICAL: MUST be set for production.
    export RATELIMIT_STORAGE_URI="redis://localhost:6379/0" # Recommended for production.
    export SERVICE_API_TOKEN="your-strong-unique-service-token" # MUST be changed for production if used.
    ```
    **Note on Admin Credentials**: The `ADMIN_USERNAME`, `ADMIN_PASSWORD`, and `ADMIN_EMAIL` environment variables set default credentials. While convenient for initial local setup, these **should not be relied upon for production admin accounts.** Always use the `flask create-admin` CLI tool to create and manage admin users with strong, unique credentials, especially in production.

4. **Initialize the Database**:

    Before running database commands, ensure `FLASK_APP` environment variable is set:
    ```bash
    export FLASK_APP=app.py # (or casino_be/app.py if running from project root)
    ```
    Then, initialize the database:
    ```bash
    flask db init
    flask db migrate -m "Initial migration or descriptive message"
    flask db upgrade
    ```

5. **Creating an Admin User**:

    After initializing the database, you can create an administrative user using the following command:

    ```bash
    flask create-admin
    ```
    The command will prompt you to enter a username, email, and password for the admin account.

    Alternatively, you can provide the credentials as command-line arguments:
    ```bash
    flask create-admin --username myadmin --email admin@example.com --password 'yoursecurepassword'
    ```
    Ensure the password is changed from the example if using arguments.

6. **Run the Application**:

    Ensure `FLASK_APP` is set as shown in step 4. For development:
    ```bash
    flask run --host=0.0.0.0 --port=5000
    ```
    The application can also be run directly via `python app.py` if the `if __name__ == '__main__':` block is configured to call `app.run()`.

## Endpoints

- **POST /api/register**: Register a new user.
- **POST /api/login**: Log in a user and obtain a JWT token.
- **POST /api/logout**: Log out a user and invalidate their JWT token.
- **POST /api/join**: Start a new game session.
- **POST /api/spin**: Spin the slot machine for a game session.
- **POST /api/withdraw**: Request a withdrawal of funds.
- **POST /api/settings**: Update user settings.
- **POST /api/deposit**: Deposit funds into a user's account.
- **GET /api/slots**: Get a list of available slots.
- **GET /api/admin/dashboard**: Access the admin dashboard (admin only).

## Database Migrations

Ensure `FLASK_APP` is set (e.g., `export FLASK_APP=app.py`).
To create new migrations after modifying models, run:

```bash
flask db migrate -m "Description of changes"
flask db upgrade
```

## Environment Variables

The following environment variables are used to configure the backend application. Some have default values suitable for development, but it is crucial to set appropriate values for a production environment.

-   `DATABASE_URL`: The complete connection string for the PostgreSQL database (e.g., `postgresql://user:password@host:port/dbname`). If this is set, it overrides the individual `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, and `DB_PASSWORD` variables. **Recommended for production.**
-   `DB_HOST`: Database host. Default: `localhost`.
-   `DB_PORT`: Database port. Default: `5432`.
-   `DB_NAME`: Database name. Default: `kingpin_casino`.
-   `DB_USER`: Database username. Default: `kingpin_user`.
-   `DB_PASSWORD`: Database password. Default: `password123`. **MUST be changed for production if not using `DATABASE_URL`.**
-   `JWT_SECRET_KEY`: Secret key used for signing JWT tokens. Default: `dev-secret-key-change-in-production`.
    **CRITICAL: This is a default development key. You MUST set a strong, unique secret key for production environments.** Using the default key in production is a severe security risk.
-   `FLASK_DEBUG`: Enables or disables Flask's debug mode. Default: `True` (for development).
    **PRODUCTION NOTE: Ensure `FLASK_DEBUG` is set to `False` in production environments. Running Flask in debug mode in production can expose security risks and impact performance.**
-   `RATELIMIT_STORAGE_URI`: Storage URI for the rate limiter. Default: `memory://`.
    **PRODUCTION NOTE: The default 'memory://' is NOT suitable for production as rate limit data will be lost on application restarts and won't be shared across multiple workers. For production, use a persistent store like Redis (e.g., `redis://localhost:6379/0`).**
-   `SERVICE_API_TOKEN`: Token for securing internal service-to-service communication. Default: `default_service_token_please_change`.
    **PRODUCTION NOTE: This is a default development token. You MUST set a strong, unique token for production environments if internal services rely on this.**
-   `CORS_ALLOWED_ORIGINS`: A comma-separated list of HTTP/HTTPS origins that are allowed to make cross-origin requests to the backend (e.g., `https://yourfrontend.com,https://anotherfrontend.com`).
    -   **Default (Development Only)**: If not set, defaults to `http://localhost:8080,http://127.0.0.1:8080,http://localhost:8082,http://127.0.0.1:8082`.
    -   **PRODUCTION NOTE: You MUST set this to the specific origins of your production frontend to prevent unauthorized cross-origin requests.**
-   `ADMIN_USERNAME`: Default username if creating an admin via environment variables (less common now). Default: `admin`.
    For production, use the `create_admin` CLI.
-   `ADMIN_PASSWORD`: Default password if creating an admin via environment variables. Default: `admin123`.
    **CRITICAL: This default password is highly insecure and intended for brief local development tests ONLY. For any persistent admin user, especially in staging or production, use the `create_admin` CLI to set a strong, unique password.**
-   `ADMIN_EMAIL`: Default email if creating an admin via environment variables. Default: `admin@kingpincasino.local`.
    For production, use the `create_admin` CLI.

## Operational Considerations

### Managing `SlotSpin` Table Growth

The `slot_spin` table records details of every spin made by users in slot games. In a high-traffic environment, this table can grow very large over time, potentially impacting database performance and storage costs.

Consider the following strategies for managing its growth:

*   **Regular Archiving:** Periodically archive older `SlotSpin` records to a separate archive database or cold storage (e.g., data warehouse, cloud storage). This keeps the production table leaner while retaining historical data if needed for analysis or compliance.
    *   Define a clear retention policy for how long spin data should remain in the primary operational database.
    *   Archiving can be done via batch jobs that copy and then delete (or mark as archived) records older than the defined retention period.
*   **Periodic Cleanup/Summarization:** If detailed spin-by-spin history is not required indefinitely for all users, consider:
    *   Deleting very old records (e.g., older than 1-2 years) if they are deemed no longer necessary and archiving is not required.
    *   Summarizing older spin data into aggregate tables if only statistical information is needed long-term, and then deleting the detailed records.
*   **Database Partitioning:** For very large tables, database-level partitioning (if supported by your PostgreSQL version and infrastructure) can help manage performance. This is a more advanced database administration task.
*   **Monitoring:** Regularly monitor the size of the `slot_spin` table and query performance related to it to decide when and which strategy to implement.

Choose the strategy that best fits your data retention requirements, regulatory obligations, and technical capabilities.
