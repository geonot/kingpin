import os
import unittest
import json
from datetime import datetime, timezone

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
        self.app = create_app(TestingConfig) # Create a new app instance with TestingConfig

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
        user = User(
            username=username,
            email=email,
            password=User.hash_password(password), # Assuming User model has hash_password
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

        self.assertTrue(data.get('status'), f"Login failed for {user.username}: {data.get('status_message', 'No status message')}")
        self.assertIn('access_token', data, "Access token not in login response.")

        return data['access_token'], user.id


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
        data = response.get_json()

        self.assertEqual(response.status_code, 422) # ValidationException returns 422
        self.assertFalse(data['status'])
        self.assertEqual(data['error_code'], ErrorCodes.USERNAME_ALREADY_EXISTS)
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
        self.assertEqual(data['error_code'], ErrorCodes.EMAIL_ALREADY_EXISTS)
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

        self.assertEqual(response.status_code, 200)
        self.assertTrue(data['status'])
        self.assertIn('access_token', data)
        self.assertIn('refresh_token', data)
        self.assertEqual(data['user']['username'], username)

    def test_login_invalid_username(self):
        """Test login with a non-existent username."""
        payload = {"username": "nonexistentuser", "password": "password"}
        response = self.client.post('/api/login', json=payload)
        data = response.get_json()

        self.assertEqual(response.status_code, 401) # Unauthorized
        self.assertFalse(data['status'])
        self.assertEqual(data['error_code'], ErrorCodes.INVALID_CREDENTIALS)
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
        self.assertEqual(data['error_code'], ErrorCodes.INVALID_CREDENTIALS)
        self.assertEqual(data['status_message'], 'Invalid username or password.')


class GameApiTests(BaseTestCase):
    """Tests for game related API endpoints."""

    # GameApiTests will use the _login_and_get_token from BaseTestCase

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
                    asset_directory="/test_assets/", # Added asset_directory
                    rtp=95.0, # Added rtp
                    volatility="medium", # Added volatility as it's also likely required
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

            # Create default SlotBet entries
            slot_bets_data = [
                {"slot_id": slot_id_val, "bet_amount": 10},
                {"slot_id": slot_id_val, "bet_amount": 10 * Config.SATOSHI_FACTOR} # Used in test_spin_success
            ]
            for sb_data in slot_bets_data:
                # Ensure no duplicate bet amounts if this helper is called multiple times for the same slot_id
                # (though setUp/tearDown should prevent this state across test methods)
                existing_slot_bet = SlotBet.query.filter_by(slot_id=sb_data["slot_id"], bet_amount=sb_data["bet_amount"]).first()
                if not existing_slot_bet:
                    slot_bet = SlotBet(**sb_data)
                    db.session.add(slot_bet)

            db.session.commit()
        return slot_id_val # Return the stored ID

    def test_spin_success(self):
        """Test a successful spin."""
        token, _ = self._login_and_get_token(username_prefix="spinner", password_suffix="spinpassword")

        # Get user for balance update
        with self.app.app_context():
            user = User.query.filter_by(username="spinner").first()
            self.assertIsNotNone(user)
            user.balance = 1000 * Config.SATOSHI_FACTOR # Give user 1000 BTC in satoshis
            db.session.commit()
            # Re-fetch user to ensure it's attached to the current session after commit
            user = User.query.filter_by(username="spinner").first()
            original_balance = user.balance

        # Create a slot machine
        slot_id = self._create_slot(short_name="slot1") # Use an existing config

        with self.app.app_context():
            # Fetch user and slot within the current session context to avoid DetachedInstanceError
            # User object might have been created/modified in a different session/context from _login_and_get_token
            user_for_session = User.query.filter_by(username="spinner").first()
            slot_for_session = Slot.query.get(slot_id)
            self.assertIsNotNone(user_for_session, "User for session not found")
            self.assertIsNotNone(slot_for_session, "Slot for session not found")

            # original_balance is already set correctly above with the re-fetched user.
            # No need to set it again here from user_for_session unless balance was changed again without commit.

            game_session = GameSession(user_id=user_for_session.id, slot_id=slot_for_session.id, game_type="slot", session_start=datetime.now(timezone.utc))
            db.session.add(game_session)
            db.session.commit()

        bet_amount_sats = 10 * Config.SATOSHI_FACTOR # Bet 10 BTC in satoshis

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
            user_after_spin = User.query.filter_by(username="spinner").first() # Re-fetch for current session
            win_amount_sats = data['win_amount']
            # Balance should be original - bet + win
            expected_balance = original_balance - bet_amount_sats + win_amount_sats
            self.assertEqual(user_after_spin.balance, expected_balance)

    def test_spin_insufficient_balance(self):
        """Test spin attempt with insufficient balance."""
        token, _ = self._login_and_get_token(username_prefix="pooruser", password_suffix="poorpassword")

        # Set user balance
        with self.app.app_context():
            user = User.query.filter_by(username="pooruser").first()
            self.assertIsNotNone(user)
            user.balance = 5 # Only 5 satoshis
            db.session.commit()

        slot_id = self._create_slot(name="Another Slot", short_name="slot1") # Use an existing config
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
        response = self.client.post('/api/slots/spin', # Corrected URL
                                     headers={'Authorization': f'Bearer {token}'},
                                     json=spin_payload)
        data = response.get_json()

        self.assertEqual(response.status_code, 400) # InsufficientFundsException returns 400
        self.assertFalse(data['status'])
        self.assertEqual(data['error_code'], ErrorCodes.INSUFFICIENT_FUNDS)
        self.assertEqual(data['status_message'], 'Insufficient balance to place bet.') # Updated message from slots.py


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
        withdraw_amount = 1000 # Adjusted to meet min withdrawal

        with self.app.app_context():
            user = User.query.get(user_id)
            user.balance = 2000 # Ensure sufficient balance for withdrawal
            db.session.commit()
            initial_balance = user.balance

        payload = {"amount_sats": withdraw_amount, "withdraw_wallet_address": "tb1qtestaddressvalidformorethan26chars"} # Adjusted payload
        response = self.client.post('/api/withdraw', headers={'Authorization': f'Bearer {token}'}, json=payload)
        data = json.loads(response.data.decode())

        self.assertEqual(response.status_code, 201, data.get('status_message'))
        self.assertTrue(data['status'])
        self.assertEqual(data['status_message'], 'Withdrawal request submitted.')

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
            user.balance = 500 # Initial balance, less than 1000 for test
            db.session.commit()

        payload = {"amount_sats": 1000, "withdraw_wallet_address": "tb1qtestaddressvalidformorethan26chars"} # Adjusted payload
        response = self.client.post('/api/withdraw', headers={'Authorization': f'Bearer {token}'}, json=payload)
        data = response.get_json()

        self.assertEqual(response.status_code, 400, data.get('status_message')) # InsufficientFundsException returns 400
        self.assertFalse(data['status'])
        self.assertEqual(data['error_code'], ErrorCodes.INSUFFICIENT_FUNDS)
        self.assertEqual(data['status_message'], 'Insufficient funds for withdrawal.')


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

        payload = {"amount_sats": 1000, "withdraw_wallet_address": "tb1qtestaddressvalidformorethan26chars"} # Adjusted amount_sats and address
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
        headers, user_id = self._get_auth_headers(username="plinko_poor_user")
        
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
        self.assertEqual(data['status_message'], 'Insufficient funds.')
        # 'new_balance' might not be part of error response, check if it's still relevant
        # self.assertAlmostEqual(data['new_balance'], 0.5)

    def test_plinko_play_validation_errors(self):
        headers, user_id = self._get_auth_headers(username="plinko_validation_user")
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
                     # Marshmallow errors are in details.errors
                    self.assertIn(error_field_in_details, data['details']['errors'])
                    self.assertIn(expected_message_part, data['details']['errors'][error_field_in_details][0])
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
