-- SQL for creating the roulette_game table
CREATE TABLE roulette_game (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    bet_amount FLOAT NOT NULL,
    bet_type VARCHAR(50) NOT NULL,
    winning_number INTEGER,
    payout FLOAT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES "user"(id) -- Assuming your user table is named "user"
);

-- Note: The exact syntax for SERIAL, FLOAT, TIMESTAMP, and FOREIGN KEY
-- might vary slightly depending on the specific SQL database being used (e.g., PostgreSQL, MySQL, SQLite).
-- This script is based on PostgreSQL syntax.
-- Also, ensure the referenced table "user" and its "id" column exist.
