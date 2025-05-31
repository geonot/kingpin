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

    Set the following environment variables in your shell or in a `.env` file:

    ```bash
    export DATABASE_URL="postgresql://user:password@localhost/dbname"
    export JWT_SECRET_KEY="your-secret-key"
    export BLOCKCYPHER_API_TOKEN="your-blockcypher-api-token"  # Optional
    ```

4. **Initialize the Database**:

    ```bash
    python manage.py db init
    python manage.py db migrate
    python manage.py db upgrade
    ```

5. **Run the Application**:

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
