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
    The application will fail to start if `DATABASE_URL` or `JWT_SECRET_KEY` are not set.

    ```bash
    export DATABASE_URL="postgresql://user:password@localhost/dbname"  # Critical: Must be set for the application to run.
    export JWT_SECRET_KEY="your-very-secret-key" # Critical: Must be set for the application to run.
    # Note: ADMIN_USERNAME, ADMIN_PASSWORD, and ADMIN_EMAIL are no longer used for initial admin creation.
    # Please use the 'create_admin' command described below.
    ```

4. **Initialize the Database**:

    ```bash
    python manage.py db init
    python manage.py db migrate
    python manage.py db upgrade
    ```

5. **Creating an Admin User**:

    After initializing the database, you can create an administrative user using the following command:

    ```bash
    python manage.py create_admin
    ```
    The command will prompt you to enter a username, email, and password for the admin account.

    Alternatively, you can provide the credentials as command-line arguments:
    ```bash
    python manage.py create_admin --username myadmin --email admin@example.com --password 'yoursecurepassword'
    ```
    Ensure the password is changed from the example if using arguments.

6. **Run the Application**:

    ```bash
    python app.py
    ```

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

To create new migrations after modifying models, run:

```bash
python manage.py db migrate
python manage.py db upgrade
```

## Environment Variables

The following environment variables are used to configure the backend application. Some have default values suitable for development, but it is crucial to set appropriate values for a production environment.

-   `DATABASE_URL`: The complete connection string for the PostgreSQL database (e.g., `postgresql://user:password@host:port/dbname`). If this is set, it overrides the individual `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, and `DB_PASSWORD` variables. **Recommended for production.**
-   `DB_HOST`: Database host. Default: `localhost`.
-   `DB_PORT`: Database port. Default: `5432`.
-   `DB_NAME`: Database name. Default: `kingpin_casino`.
-   `DB_USER`: Database username. Default: `kingpin_user`.
-   `DB_PASSWORD`: Database password. Default: `password123`. **Change for production.**
-   `JWT_SECRET_KEY`: Secret key used for signing JWT tokens. Default: `dev-secret-key-change-in-production`. **CRITICAL: Set a strong, unique key for production.**
-   `RATELIMIT_STORAGE_URI`: Storage URI for the rate limiter. Default: `memory://` (not suitable for production). For production, use a persistent store like Redis (e.g., `redis://localhost:6379/0`). **Change for production.**
-   `FLASK_DEBUG`: Enables or disables Flask's debug mode. Default: `True` (for development). Set to `False` for production. **Change for production.**
-   `ADMIN_USERNAME`: Username for the initial admin account. Default: `admin`. **Recommended to change for production.**
-   `ADMIN_PASSWORD`: Password for the initial admin account. Default: `admin123`. **CRITICAL: Change to a strong password for production.**
-   `ADMIN_EMAIL`: Email address for the initial admin account. Default: `admin@kingpincasino.local`. **Recommended to change for production.**
