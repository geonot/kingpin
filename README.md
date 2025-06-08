# Casino Application

This project contains the backend and frontend for a casino application.

## IMPORTANT: Prerequisites

**Before you begin, ensure you have the following installed AND RUNNING:**
-   **PostgreSQL Server**: The backend requires a running PostgreSQL server. The bootstrap script will check for its availability and will not proceed with backend setup if it's not accessible.
-   **Python 3.x** (and pip)
-   **Node.js** (and npm)
-   **OpenSSL** (for generating JWT secret if needed)
-   **postgresql-client** (provides `pg_isready` utility, often installed separately, e.g., `sudo apt-get install postgresql-client`)

## Setup

This project includes a bootstrap script (`bootstrap.sh`) to automate the initial setup process.

**It is highly recommended to have your PostgreSQL server running and configured before executing the bootstrap script.**

1.  **Clone the repository (if you haven't already):**
    ```bash
    git clone <repository-url>
    cd <repository-directory>
    ```

2.  **Make the bootstrap script executable (if needed):**
    ```bash
    chmod +x bootstrap.sh
    ```

3.  **Run the bootstrap script:**
    ```bash
    ./bootstrap.sh
    ```
    The script will guide you through the setup process, including:
    - Checking for all prerequisites.
    - Installing backend Python dependencies.
    - Installing frontend Node.js dependencies.
    - Prompting for PostgreSQL database credentials (user, password, database name).
    - Prompting for a JWT secret key (or generating one if you don't provide one).
    - Saving backend configurations (like DB connection string, JWT key, Flask settings) to a `.env` file in the `casino_be` directory.
    - Initializing the database schema (running `flask db init`, `flask db migrate`, `flask db upgrade`).
    - Creating an initial admin user for the backend.
    - Performing a basic health check on the backend API.

    Please follow the on-screen prompts carefully. If the script encounters issues (e.g., PostgreSQL not being available), it will provide an error message and may exit.

## Running the Application

After successfully running the bootstrap script:

**Backend:**
1.  Navigate to the backend directory:
    ```bash
    cd casino_be
    ```
2.  Ensure environment variables are set. The bootstrap script creates a `.env` file in this directory. You can load it by running:
    ```bash
    source .env
    ```
    Alternatively, ensure `DATABASE_URL`, `JWT_SECRET_KEY`, `FLASK_APP`, and `FLASK_ENV` are set in your current shell session if you didn't use the `.env` file.
3.  Start the Flask development server:
    ```bash
    flask run --host=0.0.0.0
    ```
    The backend will typically run on `http://127.0.0.1:5000`.

**Frontend:**
1.  Navigate to the frontend directory (from the root or `casino_be`):
    ```bash
    cd ../casino_fe  # If in casino_be
    # OR
    cd casino_fe     # If in root
    ```
2.  Start the Vue.js development server:
    ```bash
    npm run serve
    ```
    The frontend will typically run on `http://localhost:8080` and is configured to proxy API requests to the backend (usually `http://localhost:5000`).

## Project Structure

-   `casino_be/`: Contains the Flask backend application.
-   `casino_fe/`: Contains the Vue.js frontend application.
-   `bootstrap.sh`: Automated setup script.
```
