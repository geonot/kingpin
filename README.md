# Casino Application

This project contains the backend and frontend for a casino application.

## Prerequisites

Before you begin, ensure you have the following installed:
- Python 3.x
- pip (Python package manager)
- Node.js
- npm (Node package manager)
- PostgreSQL (must be running)
- OpenSSL

## Setup

This project includes a bootstrap script to automate the setup process.

1.  **Clone the repository (if you haven't already):**
    ```bash
    git clone <repository-url>
    cd <repository-directory>
    ```

2.  **Run the bootstrap script:**
    ```bash
    ./bootstrap.sh
    ```
    The script will guide you through the setup process, including:
    - Installing backend Python dependencies.
    - Installing frontend Node.js dependencies.
    - Prompting for PostgreSQL database credentials.
    - Prompting for a JWT secret key (or generating one).
    - Initializing the database and running migrations.
    - Creating an initial admin user.

    Please follow the on-screen prompts carefully.

3.  **Environment Variables:**
    The `bootstrap.sh` script will help you set the necessary environment variables (`DATABASE_URL` and `JWT_SECRET_KEY`). These are crucial for the backend to run. The script will save these to a `.env` file in the `casino_be` directory if you choose to, or you can set them manually in your shell environment before running the backend.

## Running the Application

After successfully running the bootstrap script:

**Backend:**
1.  Navigate to the backend directory:
    ```bash
    cd casino_be
    ```
2.  If you did not save environment variables to a `.env` file during bootstrap, ensure `DATABASE_URL` and `JWT_SECRET_KEY` are set in your current shell session.
3.  Start the Flask development server:
    ```bash
    python app.py
    ```
    The backend will typically run on `http://127.0.0.1:5000`.

**Frontend:**
1.  Navigate to the frontend directory:
    ```bash
    cd casino_fe
    ```
2.  Start the Vue.js development server:
    ```bash
    npm run serve
    ```
    The frontend will typically run on `http://localhost:8080` and will proxy API requests to the backend.

## Project Structure

-   `casino_be/`: Contains the Flask backend application.
-   `casino_fe/`: Contains the Vue.js frontend application.
-   `bootstrap.sh`: Automated setup script.
```
