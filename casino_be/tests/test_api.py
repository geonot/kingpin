import os
import unittest
import json
from datetime import datetime, timezone

# It's crucial that 'app' and 'db' are imported from the main application package.
# Assuming your Flask app instance is named 'app' and SQLAlchemy instance is 'db'
# in 'casino_be.app' and models are in 'casino_be.models'.
from casino_be.app import app, db, limiter # limiter import removed
from casino_be.models import (User, Slot, GameSession, SlotSymbol, SlotBet, # Added PlinkoDropLog
                              TokenBlacklist, Transaction, BonusCode, UserBonus, PlinkoDropLog)
#SATOSHI_FACTOR might be needed if amounts are converted
from casino_be.config import Config
from datetime import timedelta # Added timedelta
from casino_be.utils.plinko_helper import PAYOUT_MULTIPLIERS, STAKE_CONFIG # Added Plinko helpers


class BaseTestCase(unittest.TestCase):
    """Base test case to set up and tear down the test environment."""

    @classmethod
    def setUpClass(cls):
        # Configure the Flask app for testing
        app.config['TESTING'] = True
        app.config['RATELIMIT_ENABLED'] = False # Ensure Flask-Limiter is disabled via app config
        # Use an in-memory SQLite database for tests if TEST_DATABASE_URL is not set
        app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('TEST_DATABASE_URL', 'sqlite:///:memory:')
        app.config['JWT_SECRET_KEY'] = 'test-super-secret-key' # Fixed JWT secret for tests
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        app.config['WTF_CSRF_ENABLED'] = False # If using Flask-WTF

        cls.limiter = limiter
        if hasattr(cls.limiter, 'enabled'): # Check if limiter has 'enabled' attribute
            cls.limiter.enabled = False
        else:
            # Log or handle the case where 'enabled' attribute is not found
            print("Warning: Limiter does not have 'enabled' attribute in setUpClass. Rate limiting might not be disabled.")

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

        if hasattr(cls.limiter, 'enabled'):
            cls.limiter.enabled = True

    def setUp(self):
        """Set up for each test."""
        self.app_context = self.app.app_context()
        self.app_context.push()

        self.limiter = limiter # Assign to instance for consistency
        if hasattr(self.limiter, 'enabled'):
           self.limiter.enabled = False
        else:
            print("Warning: Limiter does not have 'enabled' attribute in setUp. Rate limiting might not be disabled.")

        db.create_all() # Create tables fresh for each test

    def tearDown(self):
        """Tear down after each test."""
        if hasattr(self.limiter, 'enabled'):
           self.limiter.enabled = True

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

    def _create_bonus_code(self, code_id="TESTCODE", type="deposit", subtype="percentage", amount=10.0, amount_sats=None, uses_remaining=100, is_active=True, **kwargs): # Added **kwargs to accept extra params
        with self.app.app_context():
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
        self.assertEqual(data['status_message'], 'Invalid credentials.')

    def test_login_invalid_password(self):
        """Test login with an invalid password."""
        username = "userwithwrongpass"
        self._create_user(username=username, password="correctpassword")

        payload = {"username": username, "password": "wrongpassword"}
        response = self.client.post('/api/login', json=payload)
        data = json.loads(response.data.decode())

        self.assertEqual(response.status_code, 401) # Unauthorized
        self.assertFalse(data['status'])
        self.assertEqual(data['status_message'], 'Invalid credentials.')


class GameApiTests(BaseTestCase):
    """Tests for game related API endpoints."""

    def _login_and_get_token(self, username="gameuser", password="gamepassword", email_suffix="@example.com"):
        """Helper to register, login a user and return their access token."""
        # Ensure email is unique if called multiple times with same username in different test classes
        # or if user is not cleaned up properly between tests (though BaseTestCase should handle this)
        user_email = f"{username}{email_suffix}"
        # Check if user already exists to avoid re-creating, useful if helper is called multiple times in a single test method
        # However, for test isolation, typically we create fresh users or rely on setUp/tearDown.
        # For this helper, let's assume it might be called for a user that needs to be created.
        existing_user = User.query.filter_by(username=username).first()
        if not existing_user:
            self._create_user(username=username, password=password, email=user_email)

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

            created_symbols = []
            for s_data in symbols_data:
                symbol = SlotSymbol(**s_data)
                db.session.add(symbol)
                created_symbols.append(symbol)

            # Add default SlotBet entries
            default_bet_amounts = [10, 10 * Config.SATOSHI_FACTOR] # As used in tests
            for bet_val in default_bet_amounts:
                slot_bet = SlotBet(slot_id=slot_id_val, bet_amount=bet_val)
                db.session.add(slot_bet)

            slot.symbols = created_symbols # Explicitly associate symbols with the slot object
            db.session.add(slot) # Re-add slot to session if needed after modification

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
        response = self.client.post('/api/slots/spin',
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
        response = self.client.post('/api/slots/spin',
                                     headers={'Authorization': f'Bearer {token}'},
                                     json=spin_payload)
        data = json.loads(response.data.decode())

        self.assertEqual(response.status_code, 400) # Bad Request or 402 Payment Required
        self.assertFalse(data['status'])
        self.assertEqual(data['status_message'], 'Insufficient balance')


# === Billing API Tests ===
class BillingApiTests(BaseTestCase):

    def _login_and_get_token(self, username="billinguser", password="billingpassword"):
        """Helper to create, login a user and return their access token for billing tests."""
        user = User.query.filter_by(username=username).first()
        if not user:
            user = self._create_user(username=username, password=password, email=f"{username}@example.com")

        login_payload = {"username": username, "password": password}
        response = self.client.post('/api/login', json=login_payload)
        data = json.loads(response.data.decode())
        self.assertTrue(data.get('status', False), f"Login failed for {username}: {data.get('status_message')}")
        return data['access_token'], user.id # Return user_id as well for convenience

    def test_deposit_success_no_bonus(self):
        token, user_id = self._login_and_get_token(username="deposit_no_bonus_user")

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
        token, user_id = self._login_and_get_token(username="deposit_perc_bonus_user")
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
        self.assertIn(f"Bonus '{bonus_code_obj.code_id}' applied successfully", data['status_message'])
        self.assertEqual(data.get('bonus_applied_sats'), expected_bonus_amount)

        with self.app.app_context():
            user = User.query.get(user_id)
            self.assertEqual(user.balance, initial_balance + deposit_amount + expected_bonus_amount)

            user_bonus = UserBonus.query.filter_by(user_id=user_id, bonus_code_id=bonus_code_obj.id).first()
            self.assertIsNotNone(user_bonus)
            self.assertEqual(user_bonus.bonus_amount_awarded_sats, expected_bonus_amount)
            self.assertEqual(user_bonus.wagering_requirement_sats, (deposit_amount + expected_bonus_amount) * bonus_code_obj.wagering_requirement_multiplier)
            self.assertTrue(user_bonus.is_active)

            deposit_tx = Transaction.query.filter_by(user_id=user_id, amount=deposit_amount, transaction_type='deposit').first()
            self.assertIsNotNone(deposit_tx)
            bonus_tx = Transaction.query.filter_by(user_id=user_id, amount=expected_bonus_amount, transaction_type='bonus').first()
            self.assertIsNotNone(bonus_tx) # Assuming bonus service creates a 'bonus' transaction

    def test_deposit_success_with_valid_fixed_bonus(self):
        token, user_id = self._login_and_get_token(username="deposit_fixed_bonus_user")
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
        self.assertIn(f"Bonus '{bonus_code_obj.code_id}' applied successfully", data['status_message'])
        self.assertEqual(data.get('bonus_applied_sats'), fixed_bonus_sats)

        with self.app.app_context():
            user = User.query.get(user_id)
            self.assertEqual(user.balance, initial_balance + deposit_amount + fixed_bonus_sats)

            user_bonus = UserBonus.query.filter_by(user_id=user_id, bonus_code_id=bonus_code_obj.id).first()
            self.assertIsNotNone(user_bonus)
            self.assertEqual(user_bonus.bonus_amount_awarded_sats, fixed_bonus_sats)
            self.assertEqual(user_bonus.wagering_requirement_sats, (deposit_amount + fixed_bonus_sats) * bonus_code_obj.wagering_requirement_multiplier) # Or just bonus_amount * multiplier, depending on T&C
            self.assertTrue(user_bonus.is_active)

    def test_deposit_fail_invalid_bonus_code(self):
        token, user_id = self._login_and_get_token(username="deposit_invalid_bonus_user")

        with self.app.app_context():
            user = User.query.get(user_id)
            user.balance = 1000
            db.session.commit()
            initial_balance = user.balance

        deposit_amount = 500
        payload = {"deposit_amount_sats": deposit_amount, "bonus_code": "NONEXISTENTCODE"}

        response = self.client.post('/api/deposit', headers={'Authorization': f'Bearer {token}'}, json=payload)
        data = json.loads(response.data.decode())

        self.assertEqual(response.status_code, 200) # Deposit is successful, bonus fails
        self.assertTrue(data['status'])
        self.assertIn(f"Deposit of {deposit_amount} sats successful.", data['status_message'])
        self.assertIn("Bonus application failed: Bonus code 'NONEXISTENTCODE' not found or not active.", data['status_message'])

        with self.app.app_context():
            user = User.query.get(user_id)
            self.assertEqual(user.balance, initial_balance + deposit_amount) # Balance only reflects deposit
            user_bonus = UserBonus.query.filter(UserBonus.user_id == user_id).first() # Check no bonus applied
            self.assertIsNone(user_bonus)

    def test_withdraw_success(self):
        token, user_id = self._login_and_get_token(username="withdraw_success_user")
        withdraw_amount = 100

        with self.app.app_context():
            user = User.query.get(user_id)
            user.balance = 1000 # Initial balance
            db.session.commit()
            initial_balance = user.balance

        payload = {"amount_sats": withdraw_amount, "withdraw_wallet_address": "test_btc_address_valid"}
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
        token, user_id = self._login_and_get_token(username="withdraw_insufficient_user")

        with self.app.app_context():
            user = User.query.get(user_id)
            user.balance = 50 # Initial balance
            db.session.commit()

        payload = {"amount_sats": 100, "withdraw_wallet_address": "test_btc_address"}
        response = self.client.post('/api/withdraw', headers={'Authorization': f'Bearer {token}'}, json=payload)
        data = json.loads(response.data.decode())

        self.assertEqual(response.status_code, 400, data.get('status_message')) # API returns 400 for this
        self.assertFalse(data['status'])
        self.assertEqual(data['status_message'], 'Insufficient funds')

    def test_withdraw_fail_active_bonus_wagering_incomplete(self):
        token, user_id = self._login_and_get_token(username="withdraw_wagering_user")
        bonus_code_obj = self._create_bonus_code(code_id="WAGERBONUS", type="deposit", subtype="fixed", amount_sats=500, wagering_multiplier=10)

        with self.app.app_context():
            user = User.query.get(user_id)
            user.balance = 2000 # Sufficient balance for withdrawal itself

            # Create an active UserBonus with incomplete wagering
            user_bonus = UserBonus(
                user_id=user.id,
                bonus_code_id=bonus_code_obj.id,
                bonus_amount_awarded_sats=500,
                wagering_requirement_multiplier=bonus_code_obj.wagering_requirement_multiplier,
                wagering_requirement_sats= (500 + 500) * bonus_code_obj.wagering_requirement_multiplier, # Example calculation
                wagering_progress_sats=100, 
                is_active=True,
                is_completed=False,
                is_cancelled=False,
                activated_at=datetime.now(timezone.utc)
            )
            db.session.add(user_bonus)
            db.session.commit()

        payload = {"amount_sats": 200, "withdraw_wallet_address": "test_btc_address_wagering"}
        response = self.client.post('/api/withdraw', headers={'Authorization': f'Bearer {token}'}, json=payload)
        data = json.loads(response.data.decode())

        self.assertEqual(response.status_code, 403, data.get('status_message')) 
        self.assertFalse(data['status'])
        self.assertIn("Withdrawal blocked. You have an active bonus with unmet wagering requirements.", data['status_message'])


class PlinkoApiTests(BaseTestCase):
    """Tests for the Plinko API endpoint."""

    SATOSHIS_PER_UNIT = 100_000_000 # Should match app.py or be imported from config if centralized

    def _get_auth_headers(self, username="plinko_user", password="plinko_password"):
        # Create user if not exists, then login
        user = User.query.filter_by(username=username).first()
        if not user:
            user = self._create_user(username=username, password=password, email=f"{username}@example.com")
        
        login_payload = {"username": username, "password": password}
        response = self.client.post('/api/login', json=login_payload)
        data = json.loads(response.data.decode())
        self.assertTrue(data.get('status'))
        access_token = data['access_token']
        return {'Authorization': f'Bearer {access_token}'}, user.id

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
        data = json.loads(response.data.decode())

        self.assertEqual(response.status_code, 400)
        self.assertFalse(data['success'])
        self.assertEqual(data['error'], 'Insufficient funds')
        self.assertAlmostEqual(data['new_balance'], 0.5) # Balance before bet attempt

    def test_plinko_play_validation_errors(self):
        headers, user_id = self._get_auth_headers(username="plinko_validation_user")
        with self.app.app_context(): # Ensure user has some balance
            user = User.query.get(user_id)
            user.balance = int(10 * self.SATOSHIS_PER_UNIT)
            db.session.commit()

        test_cases = [
            ({"chosen_stake_label": "Low", "slot_landed_label": "2x"}, "stake_amount", 400, "Validation failed"), # Missing stake_amount
            ({"stake_amount": 1.0, "slot_landed_label": "2x"}, "chosen_stake_label", 400, "Validation failed"),    # Missing chosen_stake_label
            ({"stake_amount": 1.0, "chosen_stake_label": "Low"}, "slot_landed_label", 400, "Validation failed"), # Missing slot_landed_label
            ({"stake_amount": 1.0, "chosen_stake_label": "InvalidTier", "slot_landed_label": "2x"}, "error", 400, "Invalid stake label"), # Invalid stake tier
            ({"stake_amount": 0.05, "chosen_stake_label": "Low", "slot_landed_label": "2x"}, "error", 400, "out of range for Low tier"), # Stake too low for tier
            ({"stake_amount": 1.0, "chosen_stake_label": "Low", "slot_landed_label": "100x"}, "error", 400, "Invalid slot landed label"), # Invalid slot
        ]

        for payload, error_key, expected_status, expected_message_part in test_cases:
            with self.subTest(payload=payload):
                response = self.client.post('/api/plinko/play', headers=headers, json=payload)
                data = json.loads(response.data.decode())
                self.assertEqual(response.status_code, expected_status)
                if 'success' in data: # Our custom success=False responses
                    self.assertFalse(data['success'])
                    self.assertIn(expected_message_part, data['error'])
                else: # Marshmallow validation errors
                    self.assertIn(expected_message_part, str(data.get('messages', data.get('error'))))


    def test_plinko_play_no_auth(self):
        payload = {
            "stake_amount": 1.0,
            "chosen_stake_label": "Low",
            "slot_landed_label": "2x"
        }
        response = self.client.post('/api/plinko/play', json=payload)
        self.assertEqual(response.status_code, 401) # Unauthorized


if __name__ == '__main__':
    unittest.main()
