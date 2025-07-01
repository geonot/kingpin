import os
import unittest
import json
from datetime import datetime, timezone
from unittest.mock import patch # Import patch

# It's crucial that 'app' and 'db' are imported from the main application package.
# Assuming your Flask app instance is named 'app' and SQLAlchemy instance is 'db'
# in 'casino_be.app' and models are in 'casino_be.models'.
from casino_be.app import db # app removed, db is fine as it's initialized globally
from casino_be.models import User, Slot, GameSession, SlotSymbol, SlotBet, TokenBlacklist, Transaction, BonusCode, UserBonus, PlinkoDropLog # Added BonusCode, UserBonus, PlinkoDropLog
#SATOSHI_FACTOR might be needed if amounts are converted
from casino_be.config import Config, TestingConfig # Import TestingConfig
from casino_be.app import create_app # Import create_app factory
from casino_be.error_codes import ErrorCodes # Import ErrorCodes
from datetime import timedelta
from casino_be.utils.plinko_helper import PAYOUT_MULTIPLIERS
# StaticPool is not needed for file-based DB strategy per test
# from sqlalchemy.pool import StaticPool

class BaseTestCase(unittest.TestCase):
    """
    Base test case to set up a fresh app and database for each test method,
    ensuring maximum test isolation.
    """

    def setUp(self):
        """Set up for each test."""
        self.app, _ = create_app(TestingConfig) # Create a new app instance with TestingConfig, ignore socketio

        # Store the database file path from the app's config for cleanup
        self.test_db_file = self.app.config.get('DATABASE_FILE_PATH', 'test_casino_be_isolated.db') # Default if not in config

        self.app_context = self.app.app_context()
        self.app_context.push()

        # db.init_app(self.app) # This is already done in create_app factory
        db.drop_all()         # Ensure any existing tables are dropped
        db.create_all()       # Create tables fresh for each test

        self.client = self.app.test_client() # Create test client for this app instance

    def tearDown(self):
        """Tear down after each test."""
        db.session.remove()   # Remove session first
        db.drop_all()         # Drop all tables
        self.app_context.pop()

        # Clean up the test database file
        if os.path.exists(self.test_db_file):
            try:
                os.remove(self.test_db_file)
            except OSError as e: # Handle potential errors during file removal (e.g., file in use)
                print(f"Error removing test database file {self.test_db_file}: {e}")


    def _create_user(self, username="testuser", email="test@example.com", password="password123", deposit_wallet_address=None):
        """Helper to create a user directly in the DB."""
        hashed_password = User.hash_password(password)
        # Log the hash being created
        print(f"TEST_DEBUG: Creating user {username} with password '{password}', hash: {hashed_password}")
        user = User(
            username=username,
            email=email,
            password=hashed_password,
            # Use provided deposit_wallet_address if available, otherwise generate one
            deposit_wallet_address=deposit_wallet_address if deposit_wallet_address is not None else f"test_wallet_{username}"
        )
        # Operations will use the session from the currently active app context (e.g., from setUp)
        db.session.add(user)
        db.session.commit()
        # Refresh user to get ID etc. and ensure it's attached to the current session
        # If called from a context that's immediately popped, this refresh might not be useful to the caller.
        # However, _login_and_get_token now re-fetches, which is safer.
        db.session.refresh(user)
        return user

    def _create_bonus_code(self, code_id="TESTCODE", type="deposit", subtype="percentage", amount=10.0, amount_sats=None, uses_remaining=100, is_active=True, **kwargs): # Added **kwargs to accept extra params
        # This helper also assumes an app context is active (e.g., from setUp)
        bonus_code = BonusCode(
            code_id=code_id,
            type=type,
            subtype=subtype,
            amount=amount,
            amount_sats=amount_sats,
            uses_remaining=uses_remaining,
            is_active=is_active,
            expires_at=datetime.now(timezone.utc) + timedelta(days=30)
        )
        db.session.add(bonus_code)
        db.session.commit()
        db.session.refresh(bonus_code)
        return bonus_code

    def _login_and_get_token(self, username_prefix="testloginuser", password_suffix="password123"):
        """
        Ensures a user exists (or creates one), logs them in, and returns token and user_id.
        Username is made unique with a suffix to avoid clashes if called multiple times.
        """
        # Make username unique to avoid clashes if called multiple times in complex test setups
        # However, with proper setUp/tearDown for each test, this might not be strictly necessary
        # but adds robustness if tests share state or are not perfectly isolated.
        unique_username = f"{username_prefix}_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
        user_email = f"{unique_username}@example.com"

        # Check if user exists, if not, create one using the helper
        # The query should happen within the current app context
        user = User.query.filter_by(username=unique_username).first()
        if not user:
            # _create_user handles its own session commit and refresh
            user = self._create_user(username=unique_username, password=password_suffix, email=user_email)

        # Ensure user is not None after attempt to create/fetch
        self.assertIsNotNone(user, f"User {unique_username} could not be created or fetched.")
        self.assertIsNotNone(user.id, f"User {unique_username} does not have an ID, creation/fetch failed.")


        login_payload = {"username": user.username, "password": password_suffix}
        response = self.client.post('/api/login', json=login_payload)
        data = json.loads(response.data.decode())

        # Check for successful status code first
        self.assertEqual(response.status_code, 200, f"Login failed. Status Code: {response.status_code}. Response: {data}")
        self.assertTrue(data.get('status'), f"Login response 'status' field is False. Response: {data}")
        # CSRF token should be in response if login is successful and sets cookies
        self.assertIn('csrf_token', data, "CSRF token not in successful login response.")

        # Token is now in HttpOnly cookie, not in JSON response body.
        # The client (self.client) will store and use cookies automatically for subsequent requests.
        return None, user.id # Return None for token string, user_id for reference.


class AuthApiTests(BaseTestCase):
    """Tests for authentication related API endpoints (/register, /login)."""

    def test_register_success(self):
        """Test successful user registration."""
        payload = {
            "username": "testregister", # Changed to not be part of email
            "email": "newuser@example.com",
            "password": "StrongPassword123!"
        }
        response = self.client.post('/api/register', json=payload)
        data = json.loads(response.data.decode())

        self.assertEqual(response.status_code, 201, f"Registration failed: {data}") # Include response data
        self.assertTrue(data['status'])
        # self.assertIn('access_token', data) # Tokens are in HttpOnly cookies
        # self.assertIn('refresh_token', data) # Tokens are in HttpOnly cookies
        self.assertIn('csrf_token', data) # Assuming register returns csrf_token upon success
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
        data = response.get_json()

        self.assertEqual(response.status_code, 422) # ValidationException returns 422
        self.assertFalse(data['status'])
        self.assertEqual(data['error_code'], ErrorCodes.VALIDATION_ERROR) # Expecting default validation error
        self.assertEqual(data['status_message'], 'Username already taken.')
        self.assertIn('username', data['details'])


    def test_register_email_exists(self):
        """Test registration with an existing email."""
        self._create_user(username="another_user", email="existing@example.com")
        payload = {
            "username": "new_username_for_email_test",
            "email": "existing@example.com", # Same email
            "password": "Password123!" # Added special character
        }
        response = self.client.post('/api/register', json=payload)
        data = response.get_json()

        self.assertEqual(response.status_code, 422) # ValidationException returns 422
        self.assertFalse(data['status'])
        self.assertEqual(data['error_code'], ErrorCodes.VALIDATION_ERROR) # Expecting default validation error
        self.assertEqual(data['status_message'], 'Email already registered.')
        self.assertIn('email', data['details'])

    def test_register_missing_fields(self):
        """Test registration with missing fields (handled by Marshmallow)."""
        # Missing password
        payload_no_pass = {"username": "user", "email": "email@example.com"}
        response = self.client.post('/api/register', json=payload_no_pass)
        data = response.get_json() # Marshmallow error handler returns 422
        self.assertEqual(response.status_code, 422) # Changed from 400 to 422 for ValidationError
        self.assertFalse(data['status'])
        self.assertEqual(data['error_code'], ErrorCodes.VALIDATION_ERROR)
        self.assertIn('password', data['details']['errors'])


        # Missing username
        payload_no_user = {"email": "email@example.com", "password": "password"}
        response = self.client.post('/api/register', json=payload_no_user)
        data = response.get_json()
        self.assertEqual(response.status_code, 422)
        self.assertFalse(data['status'])
        self.assertEqual(data['error_code'], ErrorCodes.VALIDATION_ERROR)
        self.assertIn('username', data['details']['errors'])

        # Missing email
        payload_no_email = {"username": "user", "password": "password"}
        response = self.client.post('/api/register', json=payload_no_email)
        data = response.get_json()
        self.assertEqual(response.status_code, 422)
        self.assertFalse(data['status'])
        self.assertEqual(data['error_code'], ErrorCodes.VALIDATION_ERROR)
        self.assertIn('email', data['details']['errors'])

    def test_login_success(self):
        """Test successful user login."""
        username = "loginuser"
        password = "loginpassword123"
        self._create_user(username=username, password=password)

        payload = {"username": username, "password": password}
        response = self.client.post('/api/login', json=payload)
        data = json.loads(response.data.decode())

        self.assertEqual(response.status_code, 200, f"Login failed. Response: {data}")
        self.assertTrue(data.get('status'), f"Login response 'status' is False. Response: {data}")
        self.assertIn('csrf_token', data, "CSRF token not in successful login response.")
        self.assertNotIn('access_token', data) # Explicitly check token is NOT in body
        self.assertNotIn('refresh_token', data) # Explicitly check token is NOT in body
        self.assertEqual(data['user']['username'], username)

    def test_login_invalid_username(self):
        """Test login with a non-existent username."""
        payload = {"username": "nonexistentuser", "password": "password"}
        response = self.client.post('/api/login', json=payload)
        data = response.get_json()

        self.assertEqual(response.status_code, 401) # Unauthorized
        self.assertFalse(data['status'])
        self.assertEqual(data['error_code'], ErrorCodes.UNAUTHENTICATED) # Expecting default from AuthenticationException
        self.assertEqual(data['status_message'], 'Invalid username or password.')

    def test_login_invalid_password(self):
        """Test login with an invalid password."""
        username = "userwithwrongpass"
        self._create_user(username=username, password="correctpassword")

        payload = {"username": username, "password": "wrongpassword"}
        response = self.client.post('/api/login', json=payload)
        data = response.get_json()

        self.assertEqual(response.status_code, 401) # Unauthorized
        self.assertFalse(data['status'])
        self.assertEqual(data['error_code'], ErrorCodes.UNAUTHENTICATED) # Expecting default from AuthenticationException
        self.assertEqual(data['status_message'], 'Invalid username or password.')

    def test_logout_success_and_token_blacklisting(self):
        """Test successful user logout and token blacklisting."""
        # Login to get cookies set
        _, user_id = self._login_and_get_token(username_prefix="logout_user")

        # Make a request to a protected endpoint to confirm login works
        profile_response_before_logout = self.client.get('/api/me')
        self.assertEqual(profile_response_before_logout.status_code, 200, "Protected endpoint should be accessible before logout.")

        # Logout
        logout_response = self.client.post('/api/logout') # No body needed for logout
        data = json.loads(logout_response.data.decode())

        self.assertEqual(logout_response.status_code, 200, f"Logout failed: {data}")
        self.assertTrue(data['status'])
        self.assertEqual(data['status_message'], 'Successfully logged out') # Removed period

        # Verify token is blacklisted by trying to access a protected endpoint again
        profile_response_after_logout = self.client.get('/api/me') # Uses the same client, which had the cookies

        # Depending on how JWT Extended handles blacklisted HttpOnly cookies,
        # it might return 401 (Unauthorized) or 422 (Unprocessable Entity if specific error for revoked token)
        # Flask-JWT-Extended typically returns 401 if the token is revoked and blocklist is enabled.
        self.assertEqual(profile_response_after_logout.status_code, 401, "Accessing protected endpoint after logout should be unauthorized.")
        error_data = json.loads(profile_response_after_logout.data.decode())
        self.assertFalse(error_data['status'])
        # Check for specific error code if JWT Extended provides one for revoked tokens, otherwise generic UNAUTHENTICATED
        # For HttpOnly cookies, if the cookie is simply cleared by /logout, then subsequent requests won't have it, leading to "Missing cookie"
        # If the cookie is still sent but the token is blacklisted, it would be "Token has been revoked"
        # The current /logout route uses unset_jwt_cookies which clears them.
        # So, the error from @jwt_required would be due to missing cookies.
        self.assertEqual(error_data['error_code'], ErrorCodes.UNAUTHENTICATED)
        self.assertIn(error_data['status_message'].lower(), ['missing cookie "access_token_cookie"', 'missing or invalid authorization token.'])


class UserProfileApiTests(BaseTestCase):
    """Tests for user profile and settings API endpoints."""

    def test_get_user_profile_success(self):
        """Test successfully fetching the current user's profile."""
        _, user_id = self._login_and_get_token(username_prefix="profile_user")

        # Fetch the user details from DB to compare
        with self.app.app_context():
            db_user = User.query.get(user_id)
            self.assertIsNotNone(db_user)

        response = self.client.get('/api/me')
        data = json.loads(response.data.decode())

        self.assertEqual(response.status_code, 200, f"Failed to get profile: {data}")
        self.assertTrue(data['status'])
        self.assertEqual(data['user']['id'], user_id)
        self.assertEqual(data['user']['username'], db_user.username)
        self.assertEqual(data['user']['email'], db_user.email)
        self.assertNotIn('password_hash', data['user'], "Password hash should not be in profile response.")
        self.assertIn('balance', data['user']) # Balance should be present

    def test_get_user_profile_unauthenticated(self):
        """Test fetching user profile without authentication."""
        response = self.client.get('/api/me')
        data = response.get_json()

        self.assertEqual(response.status_code, 401) # Unauthorized
        self.assertFalse(data['status'])
        self.assertEqual(data['error_code'], ErrorCodes.UNAUTHENTICATED)

    def test_update_user_settings_change_email_success(self):
        """Test successfully changing the user's email."""
        _, user_id = self._login_and_get_token(username_prefix="email_change_user", password_suffix="password123") # Explicitly show suffix
        new_email = "new_email@example.com"
        correct_current_password = "password123" # This is the actual password set by _login_and_get_token

        payload = {
            "email": new_email,
            "current_password": correct_current_password
        }
        response = self.client.post('/api/settings', json=payload)
        data = json.loads(response.data.decode())

        self.assertEqual(response.status_code, 200, f"Failed to update settings: {data}")
        self.assertTrue(data['status'])
        # self.assertEqual(data['status_message'], "Settings updated successfully.") # Route doesn't return status_message
        self.assertEqual(data['user']['email'], new_email)

        # Verify in DB
        with self.app.app_context():
            updated_user = User.query.get(user_id)
            self.assertEqual(updated_user.email, new_email)

    def test_update_user_settings_change_password_success(self):
        """Test successfully changing the user's password."""
        username = "password_change_user"
        old_password = "oldPassword123!"
        new_password = "newStrongPassword456@"

        self._create_user(username=username, password=old_password, email=f"{username}@example.com")

        # Log in with old password
        login_payload = {"username": username, "password": old_password}
        login_response = self.client.post('/api/login', json=login_payload)
        self.assertEqual(login_response.status_code, 200, "Login with old password failed.")

        payload = {
            "current_password": old_password,
            "new_password": new_password,
            "confirm_new_password": new_password
        }
        response = self.client.post('/api/settings', json=payload)
        data = json.loads(response.data.decode())

        self.assertEqual(response.status_code, 200, f"Failed to update password: {data}")
        self.assertTrue(data['status'])
        # self.assertEqual(data['status_message'], "Settings updated successfully.") # Route doesn't return status_message

        # Verify new password works for login, old one does not
        # Logout first to clear session/cookies from previous login
        self.client.post('/api/logout')

        # Try logging in with old password (should fail)
        login_fail_response = self.client.post('/api/login', json={"username": username, "password": old_password})
        self.assertEqual(login_fail_response.status_code, 401, "Login with old password should fail after change.")

        # Try logging in with new password (should succeed)
        login_success_response = self.client.post('/api/login', json={"username": username, "password": new_password})
        self.assertEqual(login_success_response.status_code, 200, "Login with new password failed.")
        success_data = json.loads(login_success_response.data.decode())
        self.assertTrue(success_data['status'])


    def test_update_user_settings_incorrect_current_password(self):
        """Test changing settings with an incorrect current password."""
        _, user_id = self._login_and_get_token(username_prefix="settings_fail_user")

        payload = {
            "email": "any_new_email@example.com",
            "current_password": "wrong_current_password"
        }
        response = self.client.post('/api/settings', json=payload)
        data = response.get_json()

        self.assertEqual(response.status_code, 401, f"Response: {data}") # Unauthorized or BadRequest
        self.assertFalse(data['status'])
        self.assertEqual(data['error_code'], ErrorCodes.UNAUTHENTICATED) # Changed to UN AUTHENTICATED
        self.assertEqual(data['status_message'], "Incorrect current password.")

    def test_update_user_settings_new_password_mismatch(self):
        """Test changing password when new_password and confirm_new_password don't match."""
        _, user_id = self._login_and_get_token(username_prefix="pw_mismatch_user", password_suffix="password123")

        payload = {
            "current_password": "password123",
            "new_password": "newStrongP@ssword1!", # Strong password
            "confirm_new_password": "differentPasswordValue" # Still different for mismatch test
        }
        response = self.client.post('/api/settings', json=payload)
        data = response.get_json()

        self.assertEqual(response.status_code, 422, f"Response: {data}") # Validation error
        self.assertFalse(data['status'])
        self.assertEqual(data['error_code'], ErrorCodes.VALIDATION_ERROR)
        self.assertIn("New passwords do not match.", data['details']['errors']['_schema'][0]) # Schema-level error


class GameApiTests(BaseTestCase):
    """Tests for game related API endpoints."""

    # GameApiTests will use the _login_and_get_token from BaseTestCase

    def _create_slot(self, name="Test Slot", short_name="test_slot_sn",
                     reels=3, rows=3, scatter_symbol_id=None, bonus_symbol_id=None, is_multiway=False, is_active=True): # Added is_active
        """Helper to create a slot machine directly in the DB."""
        with self.app.app_context():
            # Create the slot first to get its ID
            slot = Slot(
                name=name,
                short_name=short_name,
                num_rows=rows,
                num_columns=reels,
                num_symbols=4, # Default, can be adjusted if tests need more/less
                asset_directory=f"/{short_name}/",
                rtp=96.0,
                volatility="medium",
                scatter_symbol_id=scatter_symbol_id, # Set from parameter
                # bonus_symbol_id=bonus_symbol_id, # Removed as it's not a field in Slot model
                is_multiway=is_multiway,           # Set from parameter
                is_active=is_active,               # Set from parameter
                # Assuming wild_symbol_id might be one of the default symbols created below
                wild_symbol_id=4 # Defaulting wild to symbol_internal_id 4 for now
            )
            db.session.add(slot)
            db.session.commit()
            slot_id_val = slot.id


            # Create symbols for this slot
            # Ensure symbol_internal_ids match any specific IDs used (scatter, bonus, wild)
            symbols_data = [
                {"name": "Cherry", "value_multiplier": 10, "img_link": "cherry.png", "symbol_internal_id": 1, "slot_id": slot_id_val},
                {"name": "Lemon", "value_multiplier": 5, "img_link": "lemon.png", "symbol_internal_id": 2, "slot_id": slot_id_val},
                {"name": "BAR", "value_multiplier": 20, "img_link": "bar.png", "symbol_internal_id": 3, "slot_id": slot_id_val}, # Scatter could be 3
                {"name": "Wild", "value_multiplier": 0, "img_link": "wild.png", "symbol_internal_id": 4, "slot_id": slot_id_val}, # Wild is 4
                # Add a specific bonus symbol if bonus_symbol_id is set and different
            ]
            if bonus_symbol_id and bonus_symbol_id not in [s["symbol_internal_id"] for s in symbols_data]:
                symbols_data.append({"name": "BonusSym", "value_multiplier": 0, "img_link": "bonus.png", "symbol_internal_id": bonus_symbol_id, "slot_id": slot_id_val})


            for s_data in symbols_data:
                # Ensure we don't add duplicate internal_ids for the same slot
                existing_symbol = SlotSymbol.query.filter_by(slot_id=slot_id_val, symbol_internal_id=s_data["symbol_internal_id"]).first()
                if not existing_symbol:
                    symbol = SlotSymbol(**s_data)
                    db.session.add(symbol)
            db.session.flush() # Flush to ensure symbols are in DB before SlotBets that might reference them implicitly

            # Create default SlotBet entries - ensure these are sensible defaults
            slot_bets_data = [
                {"slot_id": slot_id_val, "bet_amount": 100}, # e.g. 100 satoshis
                {"slot_id": slot_id_val, "bet_amount": 200}, # e.g. 200 satoshis
                {"slot_id": slot_id_val, "bet_amount": 500}  # e.g. 500 satoshis
            ]
            # Add specific bet used in test_spin_success if it's different
            if (10 * Config.SATOSHI_FACTOR) not in [sbd["bet_amount"] for sbd in slot_bets_data]:
                 slot_bets_data.append({"slot_id": slot_id_val, "bet_amount": 10 * Config.SATOSHI_FACTOR})


            for sb_data in slot_bets_data:
                existing_slot_bet = SlotBet.query.filter_by(slot_id=sb_data["slot_id"], bet_amount=sb_data["bet_amount"]).first()
                if not existing_slot_bet:
                    slot_bet = SlotBet(**sb_data)
                    db.session.add(slot_bet)

            db.session.commit()
        return slot_id_val

    def test_spin_success(self):
        """Test a successful spin."""
        token, user_id = self._login_and_get_token(username_prefix="spinner", password_suffix="spinpassword") # Capture user_id

        # Get user for balance update
        with self.app.app_context():
            user = User.query.get(user_id) # Use user_id to fetch
            self.assertIsNotNone(user, "User not found after login_and_get_token in spin_success")
            user.balance = 1000 * Config.SATOSHI_FACTOR # Give user 1000 BTC in satoshis
            db.session.commit()
            # Re-fetch user to ensure it's attached to the current session after commit
            user = User.query.get(user_id) # Use user_id
            original_balance = user.balance

        # Create a slot machine
        slot_id = self._create_slot(short_name="slot1") # Use an existing config

        with self.app.app_context():
            # Fetch user and slot within the current session context to avoid DetachedInstanceError
            user_for_session = User.query.get(user_id) # Use user_id
            slot_for_session = Slot.query.get(slot_id)
            self.assertIsNotNone(user_for_session, "User for session not found (user_for_session)")
            self.assertIsNotNone(slot_for_session, "Slot for session not found")

            # original_balance is already set correctly above with the re-fetched user.
            # No need to set it again here from user_for_session unless balance was changed again without commit.

            game_session = GameSession(user_id=user_for_session.id, slot_id=slot_for_session.id, game_type="slot", session_start=datetime.now(timezone.utc))
            db.session.add(game_session)
            db.session.commit()

        bet_amount_sats = 100 # Changed to a valid bet amount (e.g., 100 sats)

        spin_payload = {"bet_amount": bet_amount_sats}
        response = self.client.post('/api/slots/spin', # Corrected URL
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
            user_after_spin = User.query.get(user_id) # Use user_id
            win_amount_sats = data['win_amount']
            # Balance should be original - bet + win
            expected_balance = original_balance - bet_amount_sats + win_amount_sats
            self.assertEqual(user_after_spin.balance, expected_balance)

    def test_spin_insufficient_balance(self):
        """Test spin attempt with insufficient balance."""
        token, user_id = self._login_and_get_token(username_prefix="pooruser", password_suffix="poorpassword") # Capture user_id

        # Set user balance
        with self.app.app_context():
            user = User.query.get(user_id) # Use user_id
            self.assertIsNotNone(user, "User not found after login_and_get_token in spin_insufficient_balance")
            user.balance = 5 # Only 5 satoshis
            db.session.commit()

        slot_id = self._create_slot(name="Another Slot", short_name="slot1") # Use an existing config
        with self.app.app_context():
            # Fetch user and slot within the current session context
            user_for_session = User.query.get(user_id) # Use user_id
            slot_for_session = Slot.query.get(slot_id)
            self.assertIsNotNone(user_for_session, "User for session not found (user_for_session)")
            self.assertIsNotNone(slot_for_session, "Slot for session not found")

            game_session = GameSession(user_id=user_for_session.id, slot_id=slot_for_session.id, game_type="slot", session_start=datetime.now(timezone.utc))
            db.session.add(game_session)
            db.session.commit()

        bet_amount_sats = 100 # Changed to a valid bet amount (e.g. 100 sats)
        # User balance is 5, so this bet (100) should trigger "Insufficient balance"
        spin_payload = {"bet_amount": bet_amount_sats}
        response = self.client.post('/api/slots/spin', # Corrected URL
                                     headers={'Authorization': f'Bearer {token}'},
                                     json=spin_payload)
        data = response.get_json()
        self.assertEqual(response.status_code, 400) # InsufficientFundsException returns 400
        self.assertFalse(data['status'])
        self.assertEqual(data['error_code'], ErrorCodes.INSUFFICIENT_FUNDS)
        self.assertEqual(data['status_message'], 'Insufficient balance to place bet.') # Updated message from slots.py

    @patch('casino_be.utils.spin_handler_new.load_game_config')
    @patch('casino_be.utils.spin_handler_new.generate_spin_grid')
    def test_spin_triggers_bonus(self, mock_generate_grid, mock_load_config):
        """Test that a spin can trigger a bonus feature."""
        token, user_id = self._login_and_get_token(username_prefix="bonus_trigger_user")

        # 1. Setup Slot with a scatter symbol ID
        scatter_sym_id = 3 # Must match a symbol_internal_id in _create_slot symbols
        slot_id = self._create_slot(short_name="bonus_slot", scatter_symbol_id=scatter_sym_id)

        # 2. Configure mock for load_game_config
        # This config will be returned when handle_spin calls load_game_config
        mock_game_config_data = {
            "game": {
                "name": "Bonus Slot",
                "short_name": "bonus_slot",
                "layout": {
                    "rows": 3,
                    "columns": 5,
                    "paylines": [{"id": 0, "coords": [[0,0],[0,1],[0,2]]}] # Minimal payline
                },
                "symbols": [ # Ensure these symbols are consistent with _create_slot or add more if needed
                    {"id": 1, "name": "A", "value_multipliers": {"3": 1}},
                    {"id": 2, "name": "B", "value_multipliers": {"3": 1}},
                    {"id": scatter_sym_id, "name": "Scatter", "is_scatter": True}, # Scatter symbol
                    {"id": 4, "name": "Wild", "is_wild": True}
                ],
                "scatter_symbol_id": scatter_sym_id,
                "wild_symbol_id": 4,
                "bonus_features": {
                    "free_spins": {
                        "trigger_count": 3, # 3 scatters needed
                        "spins_awarded": 10,
                        "multiplier": 2.0
                    }
                }
                # Add any other minimal required fields for game_config structure
            }
        }
        # Ensure the mocked config also has a symbols_map, as spin_handler_new.py creates it internally if not present
        # but tests for spin_handler_new.py showed it's better to have it pre-made.
        mock_game_config_data['game']['symbols_map'] = {s['id']: s for s in mock_game_config_data['game']['symbols']}
        mock_load_config.return_value = mock_game_config_data

        # 3. Configure mock for generate_spin_grid to return 3 scatters
        # Example: [[S, S, S], [X, X, X], [Y, Y, Y]] (assuming 3x3 for simplicity of grid display)
        # For a 3x5 grid:
        mock_generate_grid.return_value = [
            [scatter_sym_id, 1, scatter_sym_id], # Row 0
            [1, scatter_sym_id, 1],             # Row 1
            [2, 2, 2]                           # Row 2
        ] # This grid has 3 scatter symbols (ID `scatter_sym_id`)

        # Give user some balance
        with self.app.app_context():
            user = User.query.get(user_id)
            user.balance = 1000
            db.session.commit()

        # Join the slot game to create a session
        join_payload = {"slot_id": slot_id, "game_type": "slot"}
        join_response = self.client.post('/api/slots/join', headers={'Authorization': f'Bearer {token}'}, json=join_payload)
        self.assertEqual(join_response.status_code, 201, "Failed to join slot game")
        join_data = json.loads(join_response.data.decode())
        game_session_id = join_data['game_session']['id']


        # 4. Call /api/slots/spin endpoint
        bet_amount_sats = 100 # A valid bet amount from _create_slot defaults
        spin_payload = {"bet_amount": bet_amount_sats}
        response = self.client.post('/api/slots/spin',
                                     headers={'Authorization': f'Bearer {token}'},
                                     json=spin_payload)
        spin_data = json.loads(response.data.decode())

        # 5. Assertions
        self.assertEqual(response.status_code, 200, f"Spin API call failed: {spin_data.get('status_message')}")
        self.assertTrue(spin_data['status'])
        self.assertTrue(spin_data['bonus_triggered'], "Bonus was not triggered in API response")
        self.assertTrue(spin_data['bonus_active'], "Bonus is not active in API response")
        self.assertEqual(spin_data['bonus_spins_remaining'], 10)
        self.assertEqual(spin_data['bonus_multiplier'], 2.0)

        # Verify GameSession in DB
        with self.app.app_context():
            game_session_db = GameSession.query.get(game_session_id)
            self.assertIsNotNone(game_session_db)
            self.assertTrue(game_session_db.bonus_active)
            self.assertEqual(game_session_db.bonus_spins_remaining, 10)
            self.assertEqual(game_session_db.bonus_multiplier, 2.0)

        mock_load_config.assert_called_once() # Ensure it was called
        mock_generate_grid.assert_called_once() # Ensure it was called

    @patch('casino_be.utils.spin_handler_new.load_game_config')
    @patch('casino_be.utils.spin_handler_new.generate_spin_grid')
    def test_spin_with_active_bonus(self, mock_generate_grid, mock_load_config):
        """Test a spin when a bonus is already active."""
        token, user_id = self._login_and_get_token(username_prefix="active_bonus_user")

        # 1. Setup Slot
        slot_id = self._create_slot(short_name="active_bonus_slot")
        default_bet_amount = 100 # from _create_slot defaults

        # 2. Mock game config - standard config, no special bonus trigger needed here
        # It just needs to be a valid config for win calculation.
        # Using a simplified version of BASE_GAME_CONFIG from test_spin_handler.py
        standard_game_config = {
            "game": {
                "name": "Active Bonus Slot", "short_name": "active_bonus_slot",
                "layout": {"rows": 3, "columns": 5, "paylines": [{"id": 0, "coords": [[0,0],[0,1],[0,2]]}]},
                "symbols": [
                    {"id": 1, "name": "A", "value_multipliers": {"3": 5.0}}, # 3 'A's pay 5x bet_per_line
                    {"id": 2, "name": "B"}, {"id": 4, "name": "Wild", "is_wild": True}
                ],
                "wild_symbol_id": 4,
                "symbols_map": { # Pre-generate for simplicity
                    1: {"id": 1, "name": "A", "value_multipliers": {"3": 5.0}},
                    2: {"id": 2, "name": "B"},
                    4: {"id": 4, "name": "Wild", "is_wild": True}
                }
            }
        }
        mock_load_config.return_value = standard_game_config

        # 3. Mock generate_spin_grid to return a winning grid (e.g., three 'A's on the payline)
        # Grid: [[1, 1, 1, 2, 2], [2, 2, 2, 2, 2], [2, 2, 2, 2, 2]]
        # Payline: [[0,0],[0,1],[0,2]]
        # This should result in a win with symbol 1, count 3.
        # Base win = bet_per_line * 5.0. If bet_amount_sats is 100, and 1 payline, bet_per_line = 100. Win = 500.
        mock_generate_grid.return_value = [[1, 1, 1, 2, 2]] + [[2]*5]*2 # 3x5 grid

        initial_bonus_spins = 5
        bonus_multiplier = 2.0
        initial_user_balance = 10000

        # 4. Setup GameSession with active bonus
        with self.app.app_context():
            user = User.query.get(user_id)
            user.balance = initial_user_balance

            # End any other active sessions
            GameSession.query.filter_by(user_id=user_id, session_end=None).update({"session_end": datetime.now(timezone.utc)})

            game_session = GameSession(
                user_id=user_id, slot_id=slot_id, game_type="slot",
                session_start=datetime.now(timezone.utc),
                bonus_active=True,
                bonus_spins_remaining=initial_bonus_spins,
                bonus_multiplier=bonus_multiplier
            )
            db.session.add(game_session)
            db.session.commit()
            game_session_id = game_session.id

        # 5. Call /api/slots/spin
        # Bet amount in payload is the "line bet" or "total bet" player would have chosen,
        # but it shouldn't be deducted for a bonus spin.
        spin_payload = {"bet_amount": default_bet_amount}
        response = self.client.post('/api/slots/spin',
                                     headers={'Authorization': f'Bearer {token}'},
                                     json=spin_payload)
        spin_data = json.loads(response.data.decode())

        # 6. Assertions
        self.assertEqual(response.status_code, 200, f"Spin API call failed: {spin_data.get('status_message')}")
        self.assertTrue(spin_data['status'])

        self.assertTrue(spin_data['bonus_active'], "Bonus should still be active if spins remain")
        self.assertEqual(spin_data['bonus_spins_remaining'], initial_bonus_spins - 1)

        # Calculate expected win:
        # mock_load_config has 1 payline. So bet_per_line is default_bet_amount (100).
        # Symbol 1, count 3, pays 5.0x. So, base_win = 100 * 5.0 = 500.
        # Multiplied_win = base_win * bonus_multiplier = 500 * 2.0 = 1000.
        expected_base_win = default_bet_amount * 5.0
        expected_multiplied_win = int(expected_base_win * bonus_multiplier)
        self.assertEqual(spin_data['win_amount'], expected_multiplied_win, "Win amount not correctly multiplied by bonus_multiplier")

        # Verify user balance: only win amount added, no bet deducted
        with self.app.app_context():
            user_after_spin = User.query.get(user_id)
            self.assertEqual(user_after_spin.balance, initial_user_balance + expected_multiplied_win)

            game_session_db = GameSession.query.get(game_session_id)
            self.assertEqual(game_session_db.bonus_spins_remaining, initial_bonus_spins - 1)
            self.assertTrue(game_session_db.bonus_active) # Assuming spins_remaining > 0

    def test_spin_invalid_bet_config(self):
        """Test spin with a bet amount not configured in SlotBet for the slot."""
        token, user_id = self._login_and_get_token(username_prefix="invalid_bet_user")

        # Create a slot. _create_slot adds default bets (e.g., 100, 200, 500).
        slot_id = self._create_slot(short_name="bet_config_slot")

        with self.app.app_context():
            user = User.query.get(user_id)
            user.balance = 5000 # Sufficient balance
            db.session.commit()

        # Join the slot game
        join_payload = {"slot_id": slot_id, "game_type": "slot"}
        join_response = self.client.post('/api/slots/join', headers={'Authorization': f'Bearer {token}'}, json=join_payload)
        self.assertEqual(join_response.status_code, 201, "Failed to join slot game")

        # Attempt spin with a bet amount not in the default SlotBet entries
        invalid_bet_amount = 1000 # Changed to be a multiple of 100 and not a default SlotBet value
        # Default SlotBet amounts are 100, 200, 500, and 10 * Config.SATOSHI_FACTOR.
        # 1000 is chosen as it's a multiple of 100 and distinct from these defaults.

        spin_payload = {"bet_amount": invalid_bet_amount}
        response = self.client.post('/api/slots/spin',
                                     headers={'Authorization': f'Bearer {token}'},
                                     json=spin_payload)
        spin_data = json.loads(response.data.decode())

        self.assertEqual(response.status_code, 422, f"Response: {spin_data}") # Expect ValidationException (422)
        self.assertFalse(spin_data['status'])
        self.assertIn("Invalid bet amount for this slot", spin_data['status_message']) # Check specific part of message

    def test_spin_no_active_session(self):
        """Test spin attempt without an active game session."""
        token, user_id = self._login_and_get_token(username_prefix="no_session_user")

        # Create a slot (so it exists in general) but don't join it.
        self._create_slot(short_name="no_session_slot")

        with self.app.app_context():
            user = User.query.get(user_id)
            user.balance = 5000 # Give some balance
            db.session.commit()

        # Attempt spin without joining the game (no active session)
        bet_amount_sats = 100 # A valid bet amount for default slots
        spin_payload = {"bet_amount": bet_amount_sats}
        response = self.client.post('/api/slots/spin',
                                     headers={'Authorization': f'Bearer {token}'},
                                     json=spin_payload)
        spin_data = json.loads(response.data.decode())

        self.assertEqual(response.status_code, 404) # Now expecting NotFoundException
        self.assertFalse(spin_data['status'])
        self.assertEqual(spin_data['error_code'], ErrorCodes.SESSION_NOT_FOUND)
        self.assertEqual(spin_data['status_message'], 'No active slot game session. Please join a slot game first.')

    def test_get_slots_list_success(self):
        """Test successfully fetching the list of available slots."""
        token, _ = self._login_and_get_token(username_prefix="slot_lister")

        # Create a couple of slots to ensure the list is not empty
        self._create_slot(name="Slot Alpha", short_name="slot_a")
        self._create_slot(name="Slot Beta", short_name="slot_b", is_active=False) # One inactive

        response = self.client.get('/api/slots', headers={'Authorization': f'Bearer {token}'})
        data = json.loads(response.data.decode())

        self.assertEqual(response.status_code, 200, f"Failed to get slots list: {data}")
        self.assertTrue(data['status'])
        self.assertIn('slots', data)

        active_slots_in_response = [s for s in data['slots'] if s['short_name'] == 'slot_a']
        inactive_slots_in_response = [s for s in data['slots'] if s['short_name'] == 'slot_b']

        self.assertEqual(len(active_slots_in_response), 1, "Active slot 'slot_a' not found or duplicated.")
        # Assuming /api/slots only returns active slots by default, or includes an 'is_active' field
        # Based on routes/slots.py, it returns all slots and includes their 'is_active' status.
        self.assertTrue(any(s['short_name'] == 'slot_a' and s['is_active'] for s in data['slots']))
        self.assertTrue(any(s['short_name'] == 'slot_b' and not s['is_active'] for s in data['slots']))


    def test_get_slot_config_success(self):
        """Test successfully fetching the configuration for a specific slot."""
        token, _ = self._login_and_get_token(username_prefix="slot_config_getter")
        slot_short_name = "config_slot"
        slot_id = self._create_slot(name="Config Test Slot", short_name=slot_short_name)

        response = self.client.get(f'/api/slots/{slot_id}/config', headers={'Authorization': f'Bearer {token}'})
        data = json.loads(response.data.decode())

        self.assertEqual(response.status_code, 200, f"Failed to get slot config: {data}")
        self.assertTrue(data['status'])
        self.assertIn('game', data['config']) # Top level key should be 'game'
        game_config = data['config']['game']
        self.assertEqual(game_config['short_name'], slot_short_name)
        self.assertIn('layout', game_config)
        # Symbols are not part of client_config's top level game object, they are built by _build_secure_config and used internally
        # The client_config intentionally strips most symbol details.
        # self.assertIn('symbols', game_config)
        self.assertIn('settings', game_config)
        self.assertIn('betOptions', game_config['settings']) # Bet amounts are under settings.betOptions

    def test_get_slot_config_not_found(self):
        """Test fetching configuration for a non-existent slot."""
        token, _ = self._login_and_get_token(username_prefix="slot_config_fail_user")
        non_existent_slot_id = 99999

        response = self.client.get(f'/api/slots/{non_existent_slot_id}/config', headers={'Authorization': f'Bearer {token}'})
        data = response.get_json()

        self.assertEqual(response.status_code, 404, f"Response: {data}") # NotFoundException
        self.assertFalse(data['status'])
        self.assertEqual(data['error_code'], ErrorCodes.GAME_NOT_FOUND)
        self.assertEqual(data['status_message'], 'Slot not found') # Corrected message

    def test_join_slot_success(self):
        """Test successfully joining a slot game."""
        token, user_id = self._login_and_get_token(username_prefix="slot_joiner")
        slot_id = self._create_slot(name="Joinable Slot", short_name="join_slot")

        payload = {"slot_id": slot_id, "game_type": "slot"} # game_type might be redundant if endpoint is /slots/join
        response = self.client.post('/api/slots/join', headers={'Authorization': f'Bearer {token}'}, json=payload)
        data = json.loads(response.data.decode())

        self.assertEqual(response.status_code, 201, f"Failed to join slot: {data}") # 201 Created for new session
        self.assertTrue(data['status'])
        self.assertIn('game_session', data)
        self.assertEqual(data['game_session']['slot_id'], slot_id)
        self.assertEqual(data['game_session']['user_id'], user_id)
        self.assertIsNone(data['game_session']['session_end']) # Session should be active

        # Verify in DB
        with self.app.app_context():
            game_session_db = GameSession.query.filter_by(user_id=user_id, slot_id=slot_id, session_end=None).first()
            self.assertIsNotNone(game_session_db)
            self.assertEqual(game_session_db.id, data['game_session']['id'])

    def test_join_slot_non_existent(self):
        """Test joining a non-existent slot game."""
        token, _ = self._login_and_get_token(username_prefix="slot_join_fail_user")
        non_existent_slot_id = 99998

        payload = {"slot_id": non_existent_slot_id, "game_type": "slot"}
        response = self.client.post('/api/slots/join', headers={'Authorization': f'Bearer {token}'}, json=payload)
        data = response.get_json()

        self.assertEqual(response.status_code, 404, f"Response: {data}") # NotFoundException for slot
        self.assertFalse(data['status'])
        self.assertEqual(data['error_code'], ErrorCodes.GAME_NOT_FOUND)
        self.assertEqual(data['status_message'], f"Slot with ID {non_existent_slot_id} not found")


# === Billing API Tests ===
class BillingApiTests(BaseTestCase):

    # BillingApiTests will now use the _login_and_get_token from BaseTestCase

    def test_deposit_success_no_bonus(self):
        token, user_id = self._login_and_get_token(username_prefix="deposit_no_bonus_user")

        with self.app.app_context():
            user = User.query.get(user_id)
            user.balance = 1000 # Initial balance in satoshis
            db.session.commit()
            initial_balance = user.balance

        deposit_amount = 500
        payload = {"deposit_amount_sats": deposit_amount}

        response = self.client.post('/api/deposit', headers={'Authorization': f'Bearer {token}'}, json=payload)
        data = json.loads(response.data.decode())

        self.assertEqual(response.status_code, 200, data.get('status_message'))
        self.assertTrue(data['status'])
        self.assertIn("Deposit of 500 sats successful", data['status_message'])

        with self.app.app_context():
            user = User.query.get(user_id)
            self.assertEqual(user.balance, initial_balance + deposit_amount)

            transaction = Transaction.query.filter_by(user_id=user_id, amount=deposit_amount, transaction_type='deposit').first()
            self.assertIsNotNone(transaction)
            self.assertEqual(transaction.status, 'completed')

    def test_deposit_success_with_valid_percentage_bonus(self):
        token, user_id = self._login_and_get_token(username_prefix="deposit_perc_bonus_user")
        bonus_code_obj = self._create_bonus_code(code_id="PERC50", type="deposit", subtype="percentage", amount=50.0, wagering_multiplier=20) # 50% bonus

        with self.app.app_context():
            user = User.query.get(user_id)
            user.balance = 1000 # Initial balance
            db.session.commit()
            initial_balance = user.balance

        deposit_amount = 1000
        expected_bonus_amount = int(deposit_amount * 0.50)
        payload = {"deposit_amount_sats": deposit_amount, "bonus_code": bonus_code_obj.code_id}

        response = self.client.post('/api/deposit', headers={'Authorization': f'Bearer {token}'}, json=payload)
        data = json.loads(response.data.decode())

        self.assertEqual(response.status_code, 200, data.get('status_message'))
        self.assertTrue(data['status'])
        self.assertIn(f"Deposit of {deposit_amount} sats successful.", data['status_message'])
        self.assertIn(f"Bonus of {expected_bonus_amount} sats applied.", data['status_message']) # Corrected expected message part
        self.assertEqual(data.get('bonus_applied_sats'), expected_bonus_amount)

        with self.app.app_context():
            user = User.query.get(user_id)
            self.assertEqual(user.balance, initial_balance + deposit_amount + expected_bonus_amount)

            user_bonus = UserBonus.query.filter_by(user_id=user_id, bonus_code_id=bonus_code_obj.id).first()
            self.assertIsNotNone(user_bonus)
            self.assertEqual(user_bonus.bonus_amount_awarded_sats, expected_bonus_amount)
            self.assertEqual(user_bonus.wagering_requirement_sats, int(expected_bonus_amount * bonus_code_obj.wagering_requirement_multiplier)) # Corrected calculation
            self.assertTrue(user_bonus.is_active)

            deposit_tx = Transaction.query.filter_by(user_id=user_id, amount=deposit_amount, transaction_type='deposit').first()
            self.assertIsNotNone(deposit_tx)
            bonus_tx = Transaction.query.filter_by(user_id=user_id, amount=expected_bonus_amount, transaction_type='bonus').first()
            self.assertIsNotNone(bonus_tx) # Assuming bonus service creates a 'bonus' transaction

    def test_deposit_success_with_valid_fixed_bonus(self):
        token, user_id = self._login_and_get_token(username_prefix="deposit_fixed_bonus_user")
        fixed_bonus_sats = 10000
        bonus_code_obj = self._create_bonus_code(code_id="FIXED10K", type="deposit", subtype="fixed", amount=None, amount_sats=fixed_bonus_sats, wagering_multiplier=25)

        with self.app.app_context():
            user = User.query.get(user_id)
            user.balance = 5000 # Initial balance
            db.session.commit()
            initial_balance = user.balance

        deposit_amount = 20000
        payload = {"deposit_amount_sats": deposit_amount, "bonus_code": bonus_code_obj.code_id}

        response = self.client.post('/api/deposit', headers={'Authorization': f'Bearer {token}'}, json=payload)
        data = json.loads(response.data.decode())

        self.assertEqual(response.status_code, 200, data.get('status_message'))
        self.assertTrue(data['status'])
        self.assertIn(f"Deposit of {deposit_amount} sats successful.", data['status_message'])
        self.assertIn(f"Bonus of {fixed_bonus_sats} sats applied.", data['status_message']) # Corrected expected message part
        self.assertEqual(data.get('bonus_applied_sats'), fixed_bonus_sats)

        with self.app.app_context():
            user = User.query.get(user_id)
            self.assertEqual(user.balance, initial_balance + deposit_amount + fixed_bonus_sats)

            user_bonus = UserBonus.query.filter_by(user_id=user_id, bonus_code_id=bonus_code_obj.id).first()
            self.assertIsNotNone(user_bonus)
            self.assertEqual(user_bonus.bonus_amount_awarded_sats, fixed_bonus_sats)
            self.assertEqual(user_bonus.wagering_requirement_sats, int(fixed_bonus_sats * bonus_code_obj.wagering_requirement_multiplier)) # Corrected calculation
            self.assertTrue(user_bonus.is_active)

    def test_deposit_fail_invalid_bonus_code(self):
        token, user_id = self._login_and_get_token(username_prefix="deposit_invalid_bonus_user")

        with self.app.app_context():
            user = User.query.get(user_id)
            user.balance = 1000
            db.session.commit()
            initial_balance = user.balance

        deposit_amount = 500
        payload = {"deposit_amount_sats": deposit_amount, "bonus_code": "NONEXISTENTCODE"}

        response = self.client.post('/api/deposit', headers={'Authorization': f'Bearer {token}'}, json=payload)
        data = response.get_json()

        self.assertEqual(response.status_code, 200) # Deposit itself is successful
        self.assertTrue(data['status']) # Overall status is true because deposit went through
        self.assertIn(f"Deposit of {deposit_amount} sats successful.", data['status_message'])
        # The bonus failure message is part of the composite status_message
        self.assertIn("Bonus application failed: Invalid or expired bonus code", data['status_message'])
        # Note: The new error handling primarily standardizes HTTP error responses.
        # For 2xx responses with partial failures (like bonus code), the structure might remain custom.
        # If bonus failure were to cause a 4xx error, it would follow the new structure.

        with self.app.app_context():
            user = User.query.get(user_id)
            self.assertEqual(user.balance, initial_balance + deposit_amount) # Balance only reflects deposit
            user_bonus = UserBonus.query.filter(UserBonus.user_id == user_id).first() # Check no bonus applied
            self.assertIsNone(user_bonus)

    def test_withdraw_success(self):
        token, user_id = self._login_and_get_token(username_prefix="withdraw_success_user")
        withdraw_amount = 10000 # Changed to meet min withdrawal of 10000

        with self.app.app_context():
            user = User.query.get(user_id)
            user.balance = 20000 # Ensure sufficient balance
            db.session.commit()
            initial_balance = user.balance

        payload = {"amount_sats": withdraw_amount, "withdraw_wallet_address": "tb1qtestaddressvalidformorethan26chars"}
        response = self.client.post('/api/withdraw', headers={'Authorization': f'Bearer {token}'}, json=payload)
        data = json.loads(response.data.decode())

        self.assertEqual(response.status_code, 201, data.get('status_message'))
        self.assertTrue(data['status'])
        self.assertEqual(data['status_message'], 'Withdrawal request submitted for processing.') # Updated expected message

        with self.app.app_context():
            user = User.query.get(user_id)
            self.assertEqual(user.balance, initial_balance - withdraw_amount)

            transaction = Transaction.query.filter_by(user_id=user_id, amount=withdraw_amount, transaction_type='withdraw').first()
            self.assertIsNotNone(transaction)
            self.assertEqual(transaction.status, 'pending') # Withdrawals are pending

    def test_withdraw_fail_insufficient_funds(self):
        token, user_id = self._login_and_get_token(username_prefix="withdraw_insufficient_user")

        with self.app.app_context():
            user = User.query.get(user_id)
            user.balance = 5000 # User has 5000
            db.session.commit()

        payload = {"amount_sats": 10000, "withdraw_wallet_address": "tb1qtestaddressvalidformorethan26chars"} # Try to withdraw 10000
        response = self.client.post('/api/withdraw', headers={'Authorization': f'Bearer {token}'}, json=payload)
        data = response.get_json()

        self.assertEqual(response.status_code, 400, data.get('status_message')) # InsufficientFundsException returns 400
        self.assertFalse(data['status'])
        self.assertEqual(data['error_code'], ErrorCodes.INSUFFICIENT_FUNDS)
        self.assertEqual(data['status_message'], 'Insufficient funds for withdrawal.') # Corrected message

    def test_withdraw_fail_active_bonus_wagering_incomplete(self):
        token, user_id = self._login_and_get_token(username_prefix="withdraw_wagering_user")
        bonus_code_obj = self._create_bonus_code(code_id="WAGERBONUS", type="deposit", subtype="fixed", amount_sats=500, wagering_multiplier=10)

        with self.app.app_context():
            user = User.query.get(user_id)
            user.balance = 2000 # Sufficient balance for withdrawal itself

            # Create an active UserBonus with incomplete wagering
            user_bonus = UserBonus(
                user_id=user.id,
                bonus_code_id=bonus_code_obj.id,
                bonus_amount_awarded_sats=500,
                wagering_requirement_sats= int(500 * bonus_code_obj.wagering_requirement_multiplier),
                wagering_progress_sats=100,
                is_active=True,
                is_completed=False,
                is_cancelled=False,
                awarded_at=datetime.now(timezone.utc)
            )
            db.session.add(user_bonus)
            db.session.commit()

        payload = {"amount_sats": 10000, "withdraw_wallet_address": "tb1qtestaddressvalidformorethan26chars"} # Changed to valid amount
        response = self.client.post('/api/withdraw', headers={'Authorization': f'Bearer {token}'}, json=payload)
        data = response.get_json()

        self.assertEqual(response.status_code, 403, data.get('status_message')) # ForbiddenException returns 403
        self.assertFalse(data['status'])
        self.assertEqual(data['error_code'], ErrorCodes.FORBIDDEN) # Or a more specific bonus-related code
        self.assertIn("Withdrawal blocked due to unmet wagering requirements.", data['status_message'])


class PlinkoApiTests(BaseTestCase):
    """Tests for the Plinko API endpoint."""

    SATOSHIS_PER_UNIT = 100_000_000 # Should match app.py or be imported from config if centralized

    def _get_auth_headers(self, username_prefix="plinko_user", password_suffix="plinko_password"):
        # Uses the BaseTestCase _login_and_get_token
        access_token, user_id = self._login_and_get_token(username_prefix=username_prefix, password_suffix=password_suffix)
        return {'Authorization': f'Bearer {access_token}'}, user_id

    def test_plinko_play_success(self):
        headers, user_id = self._get_auth_headers()
        
        initial_balance_units = 100.0
        with self.app.app_context():
            user = User.query.get(user_id)
            user.balance = int(initial_balance_units * self.SATOSHIS_PER_UNIT)
            db.session.commit()

        stake_amount_units = 1.0 # e.g. 1 BTC
        chosen_stake_label = 'Low' # Must match STAKE_CONFIG in plinko_helper
        slot_landed_label = '2x'    # Must match PAYOUT_MULTIPLIERS

        payload = {
            "stake_amount": stake_amount_units,
            "chosen_stake_label": chosen_stake_label,
            "slot_landed_label": slot_landed_label
        }
        response = self.client.post('/api/plinko/play', headers=headers, json=payload)
        data = json.loads(response.data.decode())

        self.assertEqual(response.status_code, 200, data.get('error') or data.get('message'))
        self.assertTrue(data['success'])
        
        expected_winnings_units = stake_amount_units * PAYOUT_MULTIPLIERS[slot_landed_label]
        self.assertAlmostEqual(data['winnings'], expected_winnings_units)
        
        expected_new_balance_units = initial_balance_units - stake_amount_units + expected_winnings_units
        self.assertAlmostEqual(data['new_balance'], expected_new_balance_units)

        # Verify database records
        with self.app.app_context():
            user = User.query.get(user_id)
            self.assertEqual(user.balance, int(expected_new_balance_units * self.SATOSHIS_PER_UNIT))

            plinko_log = PlinkoDropLog.query.filter_by(user_id=user_id).first()
            self.assertIsNotNone(plinko_log)
            self.assertEqual(plinko_log.stake_amount, int(stake_amount_units * self.SATOSHIS_PER_UNIT))
            self.assertEqual(plinko_log.chosen_stake_label, chosen_stake_label)
            self.assertEqual(plinko_log.slot_landed_label, slot_landed_label)
            self.assertEqual(plinko_log.multiplier_applied, PAYOUT_MULTIPLIERS[slot_landed_label])
            self.assertEqual(plinko_log.winnings_amount, int(expected_winnings_units * self.SATOSHIS_PER_UNIT))

            transactions = Transaction.query.filter_by(user_id=user_id, plinko_drop_id=plinko_log.id).order_by(Transaction.id).all()
            self.assertEqual(len(transactions), 2 if expected_winnings_units > 0 else 1)
            
            bet_tx = transactions[0]
            self.assertEqual(bet_tx.transaction_type, 'plinko_bet')
            self.assertEqual(bet_tx.amount, -int(stake_amount_units * self.SATOSHIS_PER_UNIT))
            self.assertIsNotNone(bet_tx.details) # Check details if they are set

            if expected_winnings_units > 0:
                win_tx = transactions[1]
                self.assertEqual(win_tx.transaction_type, 'plinko_win')
                self.assertEqual(win_tx.amount, int(expected_winnings_units * self.SATOSHIS_PER_UNIT))
                self.assertIsNotNone(win_tx.details)


    def test_plinko_play_insufficient_funds(self):
        headers, user_id = self._get_auth_headers(username_prefix="plinko_poor_user") # Changed username to username_prefix
        
        with self.app.app_context():
            user = User.query.get(user_id)
            user.balance = int(0.5 * self.SATOSHIS_PER_UNIT) # 0.5 units
            db.session.commit()

        payload = {
            "stake_amount": 1.0, # Trying to bet 1 unit
            "chosen_stake_label": 'Low',
            "slot_landed_label": '0.5x'
        }
        response = self.client.post('/api/plinko/play', headers=headers, json=payload)
        data = response.get_json() # Assuming plinko also uses the new error structure

        self.assertEqual(response.status_code, 400) # InsufficientFundsException
        self.assertFalse(data['status']) # Changed from 'success' for consistency
        self.assertEqual(data['error_code'], ErrorCodes.INSUFFICIENT_FUNDS)
        self.assertEqual(data['status_message'], 'Insufficient funds for Plinko game.') # Corrected message
        # 'new_balance' might not be part of error response, check if it's still relevant
        # self.assertAlmostEqual(data['new_balance'], 0.5)

    def test_plinko_play_validation_errors(self):
        headers, user_id = self._get_auth_headers(username_prefix="plinko_validation_user") # Changed username to username_prefix
        with self.app.app_context(): # Ensure user has some balance
            user = User.query.get(user_id)
            user.balance = int(10 * self.SATOSHIS_PER_UNIT)
            db.session.commit()

        test_cases = [
            # Marshmallow validation errors (missing fields) - will be caught by global ValidationError handler
            ({"chosen_stake_label": "Low", "slot_landed_label": "2x"}, "stake_amount", 422, ErrorCodes.VALIDATION_ERROR, "Missing data for required field."),
            ({"stake_amount": 1.0, "slot_landed_label": "2x"}, "chosen_stake_label", 422, ErrorCodes.VALIDATION_ERROR, "Missing data for required field."),
            ({"stake_amount": 1.0, "chosen_stake_label": "Low"}, "slot_landed_label", 422, ErrorCodes.VALIDATION_ERROR, "Missing data for required field."),
            # Custom validation errors from route logic (now raising ValidationException)
            ({"stake_amount": 1.0, "chosen_stake_label": "InvalidTier", "slot_landed_label": "2x"}, "chosen_stake_label", 422, ErrorCodes.VALIDATION_ERROR, "Must be one of: Low, Medium, High."),
            ({"stake_amount": 0.05, "chosen_stake_label": "Low", "slot_landed_label": "2x"}, None, 422, ErrorCodes.INVALID_AMOUNT, "Stake amount 0.05 out of range for Low tier"),
            ({"stake_amount": 1.0, "chosen_stake_label": "Low", "slot_landed_label": "100x"}, "slot_landed_label", 422, ErrorCodes.VALIDATION_ERROR, "Must be one of: 0.5x, 2x, 5x."),
        ]

        for payload, error_field_in_details, expected_status, expected_error_code, expected_message_part in test_cases:
            with self.subTest(payload=payload):
                response = self.client.post('/api/plinko/play', headers=headers, json=payload)
                data = response.get_json()
                self.assertEqual(response.status_code, expected_status)
                self.assertFalse(data['status'])
                self.assertEqual(data['error_code'], expected_error_code)

                if expected_error_code == ErrorCodes.VALIDATION_ERROR and error_field_in_details:
                     # Marshmallow errors are in details (which is e.messages)
                    self.assertIn(error_field_in_details, data['details'])
                    self.assertIn(expected_message_part, data['details'][error_field_in_details][0])
                else:
                    # Custom ValidationExceptions have message in status_message
                    self.assertIn(expected_message_part, data['status_message'])


    def test_plinko_play_no_auth(self):
        payload = {
            "stake_amount": 1.0,
            "chosen_stake_label": "Low",
            "slot_landed_label": "2x"
        }
        response = self.client.post('/api/plinko/play', json=payload)
        data = response.get_json()
        self.assertEqual(response.status_code, 401) # Unauthorized
        self.assertFalse(data['status'])
        self.assertEqual(data['error_code'], ErrorCodes.UNAUTHENTICATED) # Assuming NoAuthorizationError is caught


if __name__ == '__main__':
    unittest.main()
