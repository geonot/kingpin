import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone
from decimal import Decimal

from flask import Flask

# Assuming models are accessible directly or via casino_be.models
# For this test, we'll mock them, so direct import isn't strictly needed for the models themselves,
# but the service functions will try to import them.
# from casino_be.models import db, User, BonusCode, UserBonus, Transaction # Will be mocked

# Function to test
from casino_be.services.bonus_service import apply_bonus_to_deposit

# --- Mock Model Classes ---
# These classes simulate the SQLAlchemy models and their basic attributes/methods.

class MockUser:
    def __init__(self, id, balance=0):
        self.id = id
        self.balance = Decimal(balance) # Use Decimal for balance consistency

class MockBonusCode:
    def __init__(self, id, code_id, bonus_type, subtype, amount=None, amount_sats=None,
                 wagering_requirement_multiplier=None, uses_remaining=None, is_active=True,
                 description=None):
        self.id = id
        self.code_id = code_id
        self.type = bonus_type # 'deposit', 'free_bet', etc.
        self.subtype = subtype # 'percentage', 'fixed', 'spins'
        self.amount = Decimal(amount) if amount is not None else None # For percentage
        self.amount_sats = int(amount_sats) if amount_sats is not None else None # For fixed
        self.wagering_requirement_multiplier = Decimal(wagering_requirement_multiplier) if wagering_requirement_multiplier is not None else None
        self.uses_remaining = uses_remaining
        self.is_active = is_active
        self.description = description
        self.updated_at = None
        self.created_at = datetime.now(timezone.utc)

class MockUserBonus:
    _next_id = 1
    def __init__(self, user_id, bonus_code_id, bonus_amount_awarded_sats,
                 wagering_requirement_sats, is_active=True, is_completed=False, is_cancelled=False):
        self.id = MockUserBonus._next_id
        MockUserBonus._next_id += 1
        self.user_id = user_id
        self.bonus_code_id = bonus_code_id
        self.bonus_amount_awarded_sats = bonus_amount_awarded_sats
        self.wagering_requirement_sats = wagering_requirement_sats
        self.wagering_progress_sats = 0
        self.is_active = is_active
        self.is_completed = is_completed
        self.is_cancelled = is_cancelled
        self.created_at = datetime.now(timezone.utc)
        self.updated_at = None
        self.completed_at = None
        self.cancelled_at = None

    @classmethod
    def reset_id_counter(cls):
        cls._next_id = 1

class MockTransaction:
    _next_id = 1
    def __init__(self, user_id, amount, transaction_type, status='completed', details=None):
        self.id = MockTransaction._next_id
        MockTransaction._next_id += 1
        self.user_id = user_id
        self.amount = amount # Can be positive (bonus) or negative (wager)
        self.transaction_type = transaction_type # 'deposit', 'bonus', 'wager', 'win'
        self.status = status
        self.details = details if details is not None else {}
        self.created_at = datetime.now(timezone.utc)
        self.updated_at = None

    @classmethod
    def reset_id_counter(cls):
        cls._next_id = 1


class TestBonusService(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        # Configure the app with a dummy SQLAlchemy database URI if your models or db session require it
        # self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        # self.app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        self.app_context = self.app.app_context()
        self.app_context.push()

        # Mock db.session
        self.patcher_db_session = patch('casino_be.services.bonus_service.db.session')
        self.mock_db_session = self.patcher_db_session.start()
        self.mock_db_session.add = MagicMock()
        self.mock_db_session.flush = MagicMock()
        # self.mock_db_session.commit = MagicMock() # Commits are usually handled by the caller route

        # Mock current_app.logger
        self.patcher_logger = patch('casino_be.services.bonus_service.current_app.logger')
        self.mock_logger = self.patcher_logger.start()

        # Mock models used by bonus_service
        # These allow us to control what BonusCode.query.filter_by().first() returns, etc.
        self.patcher_bonus_code_model = patch('casino_be.services.bonus_service.BonusCode')
        self.MockBonusCodeModel = self.patcher_bonus_code_model.start()

        self.patcher_user_bonus_model = patch('casino_be.services.bonus_service.UserBonus')
        self.MockUserBonusModel = self.patcher_user_bonus_model.start()
        # When UserBonus() is called in the service, it should use our MockUserBonus
        self.MockUserBonusModel.side_effect = lambda **kwargs: MockUserBonus(**kwargs)


        self.patcher_transaction_model = patch('casino_be.services.bonus_service.Transaction')
        self.MockTransactionModel = self.patcher_transaction_model.start()
        self.MockTransactionModel.side_effect = lambda **kwargs: MockTransaction(**kwargs)

        MockUserBonus.reset_id_counter()
        MockTransaction.reset_id_counter()


    def tearDown(self):
        self.patcher_db_session.stop()
        self.patcher_logger.stop()
        self.patcher_bonus_code_model.stop()
        self.patcher_user_bonus_model.stop()
        self.patcher_transaction_model.stop()
        self.app_context.pop()

    def test_apply_bonus_invalid_code(self):
        self.MockBonusCodeModel.query.filter_by.return_value.first.return_value = None
        user = MockUser(id=1, balance=10000)
        result = apply_bonus_to_deposit(user, "INVALIDCODE", 5000)

        self.assertFalse(result['success'])
        self.assertEqual(result['bonus_value_sats'], 0)
        self.assertEqual(result['message'], 'Invalid or expired bonus code')
        self.mock_db_session.add.assert_not_called() # No UserBonus or Transaction should be created

    def test_apply_bonus_user_has_active_bonus(self):
        active_bonus_code = MockBonusCode(id=1, code_id="ACTIVEBONUS", bonus_type="deposit", subtype="fixed", amount_sats=1000)
        self.MockBonusCodeModel.query.filter_by.return_value.first.return_value = active_bonus_code

        # Simulate existing active UserBonus
        existing_user_bonus = MockUserBonus(user_id=1, bonus_code_id=99, bonus_amount_awarded_sats=500, wagering_requirement_sats=5000, is_active=True)
        self.MockUserBonusModel.query.filter_by.return_value.first.return_value = existing_user_bonus

        user = MockUser(id=1, balance=10000)
        result = apply_bonus_to_deposit(user, "ACTIVEBONUS", 5000)

        self.assertFalse(result['success'])
        self.assertEqual(result['message'], 'You already have an active bonus. Please complete or cancel it before applying a new one.')

    def test_apply_percentage_bonus_success(self):
        bonus_code = MockBonusCode(id=2, code_id="PERCENT50", bonus_type="deposit", subtype="percentage",
                                   amount=50, wagering_requirement_multiplier=10, uses_remaining=5)
        self.MockBonusCodeModel.query.filter_by.return_value.first.return_value = bonus_code
        self.MockUserBonusModel.query.filter_by.return_value.first.return_value = None # No existing active bonus

        user = MockUser(id=1, balance=0) # Start with 0 balance for clarity
        deposit_amount = 10000 # Sats

        result = apply_bonus_to_deposit(user, "PERCENT50", deposit_amount)

        self.assertTrue(result['success'])
        expected_bonus_sats = 5000 # 50% of 10000
        self.assertEqual(result['bonus_value_sats'], expected_bonus_sats)
        self.assertEqual(user.balance, expected_bonus_sats) # Balance should be updated

        # Check UserBonus creation (mocked)
        # self.MockUserBonusModel constructor is self.MockUserBonusModel.side_effect
        created_user_bonus_args = self.MockUserBonusModel.call_args_list[0][1] # kwargs of first call
        self.assertEqual(created_user_bonus_args['user_id'], user.id)
        self.assertEqual(created_user_bonus_args['bonus_code_id'], bonus_code.id)
        self.assertEqual(created_user_bonus_args['bonus_amount_awarded_sats'], expected_bonus_sats)
        self.assertEqual(created_user_bonus_args['wagering_requirement_sats'], expected_bonus_sats * 10)
        self.assertTrue(created_user_bonus_args['is_active'])

        # Check Transaction creation (mocked)
        created_tx_args = self.MockTransactionModel.call_args_list[0][1]
        self.assertEqual(created_tx_args['user_id'], user.id)
        self.assertEqual(created_tx_args['amount'], expected_bonus_sats)
        self.assertEqual(created_tx_args['transaction_type'], 'bonus')

        # Check db.session.add was called for UserBonus and Transaction
        self.assertEqual(self.mock_db_session.add.call_count, 2)
        self.mock_db_session.flush.assert_called_once() # Should be called to get UserBonus ID

        self.assertEqual(bonus_code.uses_remaining, 4) # Uses remaining decremented

    def test_apply_fixed_bonus_success(self):
        bonus_code = MockBonusCode(id=3, code_id="FIXED1000", bonus_type="deposit", subtype="fixed",
                                   amount_sats=1000, wagering_requirement_multiplier=5, uses_remaining=1)
        self.MockBonusCodeModel.query.filter_by.return_value.first.return_value = bonus_code
        self.MockUserBonusModel.query.filter_by.return_value.first.return_value = None # No existing active bonus

        user = MockUser(id=2, balance=500)

        result = apply_bonus_to_deposit(user, "FIXED1000", 20000) # Deposit amount doesn't affect fixed bonus value

        self.assertTrue(result['success'])
        expected_bonus_sats = 1000
        self.assertEqual(result['bonus_value_sats'], expected_bonus_sats)
        self.assertEqual(user.balance, 500 + expected_bonus_sats)

        created_user_bonus_args = self.MockUserBonusModel.call_args_list[0][1]
        self.assertEqual(created_user_bonus_args['bonus_amount_awarded_sats'], expected_bonus_sats)
        self.assertEqual(created_user_bonus_args['wagering_requirement_sats'], expected_bonus_sats * 5)

        self.assertEqual(bonus_code.uses_remaining, 0)

    def test_apply_percentage_bonus_no_deposit_amount(self):
        bonus_code = MockBonusCode(id=4, code_id="PERCENTNOSATS", bonus_type="deposit", subtype="percentage", amount=20)
        self.MockBonusCodeModel.query.filter_by.return_value.first.return_value = bonus_code
        self.MockUserBonusModel.query.filter_by.return_value.first.return_value = None

        user = MockUser(id=3)
        result = apply_bonus_to_deposit(user, "PERCENTNOSATS", None) # No deposit amount

        self.assertTrue(result['success']) # Still true, but no bonus value
        self.assertEqual(result['bonus_value_sats'], 0)
        self.assertEqual(result['message'], 'Percentage bonus not applied: deposit_amount_sats is required for this bonus.')

    def test_apply_bonus_code_no_uses_remaining(self):
        # Note: The current apply_bonus_to_deposit doesn't explicitly check uses_remaining > 0 before applying,
        # only decrements if uses_remaining is not None. If a code with 0 uses_remaining should be invalid,
        # BonusCode.query should filter it (e.g. uses_remaining > 0 or uses_remaining IS NULL).
        # For this test, we assume the query returns it, and we test the decrement.
        bonus_code = MockBonusCode(id=5, code_id="LIMITED", bonus_type="deposit", subtype="fixed",
                                   amount_sats=500, uses_remaining=0) # Uses already zero
        self.MockBonusCodeModel.query.filter_by.return_value.first.return_value = bonus_code
        self.MockUserBonusModel.query.filter_by.return_value.first.return_value = None

        user = MockUser(id=4)
        result = apply_bonus_to_deposit(user, "LIMITED", 1000)

        self.assertTrue(result['success'])
        self.assertEqual(result['bonus_value_sats'], 500)
        self.assertEqual(bonus_code.uses_remaining, 0) # Max(0, 0-1) = 0

    def test_apply_spins_bonus_type(self):
        bonus_code = MockBonusCode(id=6, code_id="FREESPINS", bonus_type="deposit", subtype="spins")
        self.MockBonusCodeModel.query.filter_by.return_value.first.return_value = bonus_code
        self.MockUserBonusModel.query.filter_by.return_value.first.return_value = None

        user = MockUser(id=5)
        result = apply_bonus_to_deposit(user, "FREESPINS", 1000)

        self.assertTrue(result['success'])
        self.assertEqual(result['bonus_value_sats'], 0)
        self.assertEqual(result['message'], "Spins bonus code does not award direct monetary value here.")
        self.mock_db_session.add.assert_not_called() # No UserBonus or Transaction for monetary value

if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False)
