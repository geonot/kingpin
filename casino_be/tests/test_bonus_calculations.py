import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

from casino_be.app import app, db
from casino_be.models import User, GameSession, UserBonus, BonusCode
from casino_be.utils.spin_handler import check_bonus_trigger
from casino_be.services.bonus_service import calculate_bonus_payout, validate_bonus_eligibility


class TestBonusCalculations(unittest.TestCase):
    """Comprehensive tests for bonus calculation logic and edge cases."""
    
    def setUp(self):
        self.app = app
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        
        self.user = User(
            username='bonus_user',
            email='bonus@test.com',
            password='password',
            balance=100000
        )
        db.session.add(self.user)
        db.session.commit()
        
    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()
        
    def test_bonus_trigger_exact_scatter_count(self):
        """Test bonus triggers with exact minimum scatter requirements."""
        grid = [
            [4, 1, 2, 3, 1],
            [1, 4, 3, 2, 4],
            [2, 3, 1, 4, 2]
        ]
        scatter_symbol_id = 4
        bonus_features = {
            'free_spins': {
                'trigger_symbol_id': 4,
                'trigger_count': 3,
                'spins_awarded': 10,
                'multiplier': 2.0
            }
        }
        
        result = check_bonus_trigger(grid, scatter_symbol_id, bonus_features)
        
        self.assertTrue(result['triggered'])
        self.assertEqual(result['spins_awarded'], 10)
        self.assertEqual(result['multiplier'], 2.0)
        self.assertEqual(result['trigger_symbol_count'], 4)
        
    def test_bonus_trigger_insufficient_scatters(self):
        """Test that bonus doesn't trigger with insufficient scatters."""
        grid = [
            [4, 1, 2, 3, 1],
            [1, 3, 3, 2, 1],
            [2, 3, 1, 1, 2]
        ]
        scatter_symbol_id = 4
        bonus_features = {
            'free_spins': {
                'trigger_symbol_id': 4,
                'trigger_count': 3,
                'spins_awarded': 10,
                'multiplier': 2.0
            }
        }
        
        result = check_bonus_trigger(grid, scatter_symbol_id, bonus_features)
        
        self.assertFalse(result['triggered'])
        
    def test_bonus_trigger_excess_scatters(self):
        """Test bonus trigger with more scatters than minimum."""
        grid = [
            [4, 4, 4, 4, 4],
            [1, 3, 3, 2, 1],
            [2, 3, 1, 1, 2]
        ]
        scatter_symbol_id = 4
        bonus_features = {
            'free_spins': {
                'trigger_symbol_id': 4,
                'trigger_count': 3,
                'spins_awarded': 10,
                'multiplier': 2.0
            }
        }
        
        result = check_bonus_trigger(grid, scatter_symbol_id, bonus_features)
        
        self.assertTrue(result['triggered'])
        self.assertEqual(result['trigger_symbol_count'], 5)
        
    def test_bonus_trigger_no_config(self):
        """Test bonus trigger with missing configuration."""
        grid = [[4, 4, 4], [1, 2, 3], [2, 3, 1]]
        scatter_symbol_id = 4
        bonus_features = {}
        
        result = check_bonus_trigger(grid, scatter_symbol_id, bonus_features)
        
        self.assertFalse(result['triggered'])
        
    def test_bonus_payout_calculation_basic(self):
        """Test basic bonus payout calculation."""
        base_win = 1000
        bonus_multiplier = 2.5
        
        expected_payout = int(base_win * bonus_multiplier)
        actual_payout = calculate_bonus_payout(base_win, bonus_multiplier)
        
        self.assertEqual(actual_payout, expected_payout)
        
    def test_bonus_payout_calculation_zero_win(self):
        """Test bonus payout with zero base win."""
        base_win = 0
        bonus_multiplier = 2.5
        
        expected_payout = 0
        actual_payout = calculate_bonus_payout(base_win, bonus_multiplier)
        
        self.assertEqual(actual_payout, expected_payout)
        
    def test_bonus_payout_calculation_fractional_result(self):
        """Test bonus payout with fractional results (should be rounded)."""
        base_win = 333
        bonus_multiplier = 1.5
        
        expected_payout = int(333 * 1.5)  # 499.5 -> 499
        actual_payout = calculate_bonus_payout(base_win, bonus_multiplier)
        
        self.assertEqual(actual_payout, expected_payout)
        
    def test_bonus_eligibility_active_user(self):
        """Test bonus eligibility for active user."""
        bonus_code = BonusCode(
            code_id='TEST_BONUS',
            name='Test Bonus',
            bonus_amount_sats=100000,
            wagering_requirement_multiplier=10,
            expiry_date=datetime.now(timezone.utc).replace(year=2025),
            is_active=True
        )
        db.session.add(bonus_code)
        db.session.commit()
        
        is_eligible, error_msg = validate_bonus_eligibility(self.user.id, bonus_code.id)
        
        self.assertTrue(is_eligible)
        self.assertIsNone(error_msg)
        
    def test_bonus_eligibility_expired_bonus(self):
        """Test bonus eligibility for expired bonus."""
        bonus_code = BonusCode(
            code_id='EXPIRED_BONUS',
            name='Expired Bonus',
            bonus_amount_sats=100000,
            wagering_requirement_multiplier=10,
            expiry_date=datetime.now(timezone.utc).replace(year=2020),
            is_active=True
        )
        db.session.add(bonus_code)
        db.session.commit()
        
        is_eligible, error_msg = validate_bonus_eligibility(self.user.id, bonus_code.id)
        
        self.assertFalse(is_eligible)
        self.assertIn('expired', error_msg.lower())
        
    def test_bonus_eligibility_already_claimed(self):
        """Test bonus eligibility for already claimed bonus."""
        bonus_code = BonusCode(
            code_id='CLAIMED_BONUS',
            name='Claimed Bonus',
            bonus_amount_sats=100000,
            wagering_requirement_multiplier=10,
            expiry_date=datetime.now(timezone.utc).replace(year=2025),
            is_active=True
        )
        db.session.add(bonus_code)
        db.session.commit()
        
        # Create existing user bonus
        user_bonus = UserBonus(
            user_id=self.user.id,
            bonus_code_id=bonus_code.id,
            bonus_amount_awarded_sats=100000,
            wagering_requirement_sats=1000000,
            is_active=False,
            is_completed=True,
            awarded_at=datetime.now(timezone.utc)
        )
        db.session.add(user_bonus)
        db.session.commit()
        
        is_eligible, error_msg = validate_bonus_eligibility(self.user.id, bonus_code.id)
        
        self.assertFalse(is_eligible)
        self.assertIn('already', error_msg.lower())


if __name__ == '__main__':
    unittest.main()
