import os
import unittest
import json
from datetime import datetime, timezone

# It's crucial that 'app' and 'db' are imported from the main application package.
# Assuming your Flask app instance is named 'app' and SQLAlchemy instance is 'db'
# in 'casino_be.app' and models are in 'casino_be.models'.
from casino_be.app import app, db
from casino_be.models import User, Slot, GameSession, SlotSymbol, SlotBet, TokenBlacklist, Transaction
#SATOSHI_FACTOR might be needed if amounts are converted
from casino_be.config import Config


class BaseTestCase(unittest.TestCase):
    """Base test case to set up and tear down the test environment."""

    @classmethod
    def setUpClass(cls):
        # Configure the Flask app for testing
        app.config['TESTING'] = True
        # Use an in-memory SQLite database for tests if TEST_DATABASE_URL is not set
        app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('TEST_DATABASE_URL', 'sqlite:///:memory:')
        app.config['JWT_SECRET_KEY'] = 'test-super-secret-key' # Fixed JWT secret for tests
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        app.config['WTF_CSRF_ENABLED'] = False # If using Flask-WTF

        cls.app = app
        cls.client = cls.app.test_client()

        # Create all database tables
        with cls.app.app_context():
            db.create_all()

    @classmethod
    def tearDownClass(cls):
        # Drop all database tables
        with cls.app.app_context():
            db.drop_all()

    def setUp(self):
        """Set up for each test."""
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all() # Create tables fresh for each test

    def tearDown(self):
        """Tear down after each test."""
        db.session.remove()
        db.drop_all() # Drop tables after each test
        self.app_context.pop()

    def _create_user(self, username="testuser", email="test@example.com", password="password123"):
        """Helper to create a user directly in the DB."""
        user = User(
            username=username,
            email=email,
            password=User.hash_password(password), # Assuming User model has hash_password
            deposit_wallet_address="test_wallet_address" # Assuming this is a required field
        )
        with self.app.app_context():
            db.session.add(user)
            db.session.commit()
            # Refresh user to get ID etc.
            db.session.refresh(user)
        return user


class AuthApiTests(BaseTestCase):
    """Tests for authentication related API endpoints (/register, /login)."""

    def test_register_success(self):
        """Test successful user registration."""
        payload = {
            "username": "newuser",
            "email": "newuser@example.com",
            "password": "StrongPassword123!" # Added special character
        }
        response = self.client.post('/api/register', json=payload)
        data = json.loads(response.data.decode())

        self.assertEqual(response.status_code, 201)
        self.assertTrue(data['status'])
        self.assertIn('access_token', data)
        self.assertIn('refresh_token', data)
        self.assertEqual(data['user']['username'], payload['username'])
        self.assertEqual(data['user']['email'], payload['email'])

        # Verify user in database
        with self.app.app_context():
            user = User.query.filter_by(username=payload['username']).first()
            self.assertIsNotNone(user)
            self.assertEqual(user.email, payload['email'])

    def test_register_username_exists(self):
        """Test registration with an existing username."""
        self._create_user(username="existinguser", email="unique_email@example.com")
        payload = {
            "username": "existinguser", # Same username
            "email": "another_email@example.com",
            "password": "Password123!" # Added special character
        }
        response = self.client.post('/api/register', json=payload)
        data = json.loads(response.data.decode())

        self.assertEqual(response.status_code, 409) # Conflict
        self.assertFalse(data['status'])
        self.assertIn('Username already exists', data['status_message'])

    def test_register_email_exists(self):
        """Test registration with an existing email."""
        self._create_user(username="another_user", email="existing@example.com")
        payload = {
            "username": "new_username_for_email_test",
            "email": "existing@example.com", # Same email
            "password": "Password123!" # Added special character
        }
        response = self.client.post('/api/register', json=payload)
        data = json.loads(response.data.decode())

        self.assertEqual(response.status_code, 409) # Conflict
        self.assertFalse(data['status'])
        self.assertIn('Email already exists', data['status_message'])

    def test_register_missing_fields(self):
        """Test registration with missing fields."""
        # Missing password
        payload_no_pass = {"username": "user", "email": "email@example.com"}
        response = self.client.post('/api/register', json=payload_no_pass)
        data = json.loads(response.data.decode())
        self.assertEqual(response.status_code, 400)
        self.assertFalse(data['status'])
        self.assertIn('password', data['status_message']) # Schema validation should catch this

        # Missing username
        payload_no_user = {"email": "email@example.com", "password": "password"}
        response = self.client.post('/api/register', json=payload_no_user)
        data = json.loads(response.data.decode())
        self.assertEqual(response.status_code, 400)
        self.assertFalse(data['status'])
        self.assertIn('username', data['status_message'])

        # Missing email
        payload_no_email = {"username": "user", "password": "password"}
        response = self.client.post('/api/register', json=payload_no_email)
        data = json.loads(response.data.decode())
        self.assertEqual(response.status_code, 400)
        self.assertFalse(data['status'])
        self.assertIn('email', data['status_message'])

    def test_login_success(self):
        """Test successful user login."""
        username = "loginuser"
        password = "loginpassword123"
        self._create_user(username=username, password=password)

        payload = {"username": username, "password": password}
        response = self.client.post('/api/login', json=payload)
        data = json.loads(response.data.decode())

        self.assertEqual(response.status_code, 200)
        self.assertTrue(data['status'])
        self.assertIn('access_token', data)
        self.assertIn('refresh_token', data)
        self.assertEqual(data['user']['username'], username)

    def test_login_invalid_username(self):
        """Test login with a non-existent username."""
        payload = {"username": "nonexistentuser", "password": "password"}
        response = self.client.post('/api/login', json=payload)
        data = json.loads(response.data.decode())

        self.assertEqual(response.status_code, 401) # Unauthorized
        self.assertFalse(data['status'])
        self.assertEqual(data['status_message'], 'Invalid username or password')

    def test_login_invalid_password(self):
        """Test login with an invalid password."""
        username = "userwithwrongpass"
        self._create_user(username=username, password="correctpassword")

        payload = {"username": username, "password": "wrongpassword"}
        response = self.client.post('/api/login', json=payload)
        data = json.loads(response.data.decode())

        self.assertEqual(response.status_code, 401) # Unauthorized
        self.assertFalse(data['status'])
        self.assertEqual(data['status_message'], 'Invalid username or password')


class GameApiTests(BaseTestCase):
    """Tests for game related API endpoints."""

    def _login_and_get_token(self, username="gameuser", password="gamepassword"):
        """Helper to register, login a user and return their access token."""
        self._create_user(username=username, password=password, email=f"{username}@example.com")
        login_payload = {"username": username, "password": password}
        response = self.client.post('/api/login', json=login_payload)
        data = json.loads(response.data.decode())
        return data['access_token']

    def _create_slot(self, name="Test Slot", short_name="test_slot_sn", reels=3, rows=3, paylines=5): # Added short_name param
        """Helper to create a slot machine directly in the DB."""
        with self.app.app_context():
            # Create the slot first to get its ID
            slot = Slot(
                name=name,
                short_name=short_name, # Use parameter
                num_rows=rows,
                num_columns=reels,
                num_symbols=4, # Example, adjust if needed
                # wild_symbol_id, scatter_symbol_id can be set later if needed
            )
            db.session.add(slot)
            db.session.commit()
            # slot.id is definitely available here
            slot_id_val = slot.id # Store the ID while session is active


            # Create symbols for this slot
            symbols_data = [
                {"name": "Cherry", "value_multiplier": 10, "img_link": "cherry.png", "symbol_internal_id": 1, "slot_id": slot_id_val},
                {"name": "Lemon", "value_multiplier": 5, "img_link": "lemon.png", "symbol_internal_id": 2, "slot_id": slot_id_val},
                {"name": "BAR", "value_multiplier": 20, "img_link": "bar.png", "symbol_internal_id": 3, "slot_id": slot_id_val},
                {"name": "Wild", "value_multiplier": 0, "img_link": "wild.png", "symbol_internal_id": 4, "slot_id": slot_id_val},
            ]

            for s_data in symbols_data:
                symbol = SlotSymbol(**s_data)
                db.session.add(symbol)
            db.session.commit()

            # Optionally, refresh symbols or query them back if needed for association with slot.symbols
            # If Slot.symbols relationship is configured with backref, adding symbols with slot_id
            # might be enough. Or append to slot.symbols collection.
            # For now, direct creation with slot_id is done.
        return slot_id_val # Return the stored ID

    def test_spin_success(self):
        """Test a successful spin."""
        token = self._login_and_get_token(username="spinner", password="spinpassword")

        # Get user for balance update
        with self.app.app_context():
            user = User.query.filter_by(username="spinner").first()
            self.assertIsNotNone(user)
            user.balance = 1000 * Config.SATOSHI_FACTOR # Give user 1000 BTC in satoshis
            db.session.commit()
            db.session.refresh(user)
            original_balance = user.balance

        # Create a slot machine
        slot_id = self._create_slot(short_name="spin_succ_slot") # Get slot_id with unique short_name

        with self.app.app_context():
            # Fetch user and slot within the current session context to avoid DetachedInstanceError
            user_for_session = User.query.filter_by(username="spinner").first() # User from _login_and_get_token
            slot_for_session = Slot.query.get(slot_id)
            self.assertIsNotNone(user_for_session, "User for session not found")
            self.assertIsNotNone(slot_for_session, "Slot for session not found")

            # Ensure user has balance (already done in _login_and_get_token's user creation, but good to be explicit if needed)
            # For this test, user's balance is set after _login_and_get_token call.
            original_balance = user_for_session.balance


            game_session = GameSession(user_id=user_for_session.id, slot_id=slot_for_session.id, game_type="slot", session_start=datetime.now(timezone.utc))
            db.session.add(game_session)
            db.session.commit()

        bet_amount_sats = 10 * Config.SATOSHI_FACTOR # Bet 10 BTC in satoshis

        spin_payload = {"bet_amount": bet_amount_sats}
        response = self.client.post('/api/spin',
                                     headers={'Authorization': f'Bearer {token}'},
                                     json=spin_payload)
        data = json.loads(response.data.decode())

        self.assertEqual(response.status_code, 200, f"Spin failed: {data.get('status_message')}")
        self.assertTrue(data['status'])
        self.assertIn('win_amount', data) # win_amount is in satoshis
        self.assertIn('user', data)
        self.assertIn('balance', data['user'])

        # Verify balance update in DB
        with self.app.app_context():
            user_after_spin = User.query.filter_by(username="spinner").first() # Re-fetch for current session
            win_amount_sats = data['win_amount']
            # Balance should be original - bet + win
            expected_balance = original_balance - bet_amount_sats + win_amount_sats
            self.assertEqual(user_after_spin.balance, expected_balance)

    def test_spin_insufficient_balance(self):
        """Test spin attempt with insufficient balance."""
        token = self._login_and_get_token(username="pooruser", password="poorpassword")

        # Set user balance
        with self.app.app_context():
            user = User.query.filter_by(username="pooruser").first()
            self.assertIsNotNone(user)
            user.balance = 5 # Only 5 satoshis
            db.session.commit()

        slot_id = self._create_slot(name="Another Slot", short_name="spin_insuf_slot") # Get slot_id with unique short_name
        with self.app.app_context():
            # Fetch user and slot within the current session context
            user_for_session = User.query.filter_by(username="pooruser").first()
            slot_for_session = Slot.query.get(slot_id)
            self.assertIsNotNone(user_for_session, "User for session not found")
            self.assertIsNotNone(slot_for_session, "Slot for session not found")

            game_session = GameSession(user_id=user_for_session.id, slot_id=slot_for_session.id, game_type="slot", session_start=datetime.now(timezone.utc))
            db.session.add(game_session)
            db.session.commit()

        bet_amount_sats = 10 # Bet 10 satoshis
        spin_payload = {"bet_amount": bet_amount_sats}
        response = self.client.post('/api/spin',
                                     headers={'Authorization': f'Bearer {token}'},
                                     json=spin_payload)
        data = json.loads(response.data.decode())

        self.assertEqual(response.status_code, 400) # Bad Request or 402 Payment Required
        self.assertFalse(data['status'])
        self.assertEqual(data['status_message'], 'Insufficient balance')


if __name__ == '__main__':
    unittest.main()
