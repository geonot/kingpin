import unittest
import os # For BaseTestCase environment variable access
from casino_be.utils.bitcoin import generate_bitcoin_wallet
from casino_be.utils.spin_handler import calculate_win
from casino_be.utils.blackjack_helper import _calculate_hand_value, _determine_winner_for_hand, _create_player_hand_obj, _update_wagering_progress
from casino_be.models import User, UserBonus, BonusCode, db # Added User, UserBonus, BonusCode, db
from casino_be.app import app # Added app for app_context
from datetime import datetime, timezone, timedelta

# Importing BaseTestCase to leverage its setup for DB interactions
from .test_api import BaseTestCase


@unittest.skip("Skipping Bitcoin utils tests due to persistent python-bitcoinlib import issues in this environment.")
class TestBitcoinUtils(unittest.TestCase): # This could potentially inherit from BaseTestCase if it needed DB
    def test_generate_bitcoin_wallet(self):
        """
        Test that generate_bitcoin_wallet returns an address.
        """
        address = generate_bitcoin_wallet()

        self.assertIsInstance(address, str, "Address should be a string.")
        self.assertTrue(len(address) > 25, "Address length seems too short.")

class TestSpinHandlerUtils(unittest.TestCase):
    def test_calculate_win_simple_payline(self):
        """
        Test calculate_win with a simple payline win.
        """
        grid = [[1, 1, 1, 2, 3], [4, 5, 6, 7, 8], [9, 10, 11, 12, 13]]
        config_paylines = [{"id": "line1", "positions": [[0, 0], [0, 1], [0, 2], [0,3], [0,4]]}] # Top row

        config_symbols_map = {
            1: {"id": 1, "name": "Symbol1", "value_multipliers": {"3": 10.0}},
            2: {"id": 2, "name": "Symbol2"},
            3: {"id": 3, "name": "Symbol3"},
        }

        total_bet_sats = 100
        expected_win_per_line = 10.0
        expected_total_win = 100 * expected_win_per_line

        result = calculate_win(
            grid=grid,
            config_paylines=config_paylines,
            config_symbols_map=config_symbols_map,
            total_bet_sats=total_bet_sats,
            wild_symbol_id=None,
            scatter_symbol_id=None
        )

        self.assertEqual(result['total_win_sats'], expected_total_win)
        self.assertEqual(len(result['winning_lines']), 1)
        self.assertEqual(result['winning_lines'][0]['line_id'], "line1")
        self.assertEqual(result['winning_lines'][0]['symbol_id'], 1)
        self.assertEqual(result['winning_lines'][0]['count'], 3)
        self.assertEqual(result['winning_lines'][0]['win_amount_sats'], expected_total_win)

    def test_calculate_win_scatter(self):
        """
        Test calculate_win with a scatter win.
        """
        grid = [[7, 1, 2], [3, 7, 4], [5, 6, 7]]
        config_paylines = []

        scatter_symbol_id = 7
        config_symbols_map = {
            1: {"id": 1, "name": "Symbol1"},
            7: {"id": 7, "name": "Scatter", "payouts": {"3": 5.0}},
        }

        total_bet_sats = 50
        expected_scatter_multiplier = 5.0
        expected_total_win = total_bet_sats * expected_scatter_multiplier

        result = calculate_win(
            grid=grid,
            config_paylines=config_paylines,
            config_symbols_map=config_symbols_map,
            total_bet_sats=total_bet_sats,
            wild_symbol_id=None,
            scatter_symbol_id=scatter_symbol_id
        )

        self.assertEqual(result['total_win_sats'], expected_total_win)
        self.assertEqual(len(result['winning_lines']), 1)
        self.assertEqual(result['winning_lines'][0]['line_id'], "scatter")
        self.assertEqual(result['winning_lines'][0]['symbol_id'], scatter_symbol_id)
        self.assertEqual(result['winning_lines'][0]['count'], 3)
        self.assertEqual(result['winning_lines'][0]['win_amount_sats'], expected_total_win)

class TestBlackjackHelperUtils(unittest.TestCase):
    def test_calculate_hand_value(self):
        """Test calculation of Blackjack hand values."""
        test_cases = [
            (["H2", "D3"], (5, False), "Simple numeric"),
            (["HA", "D5"], (16, True), "Ace as 11 (soft)"),
            (["HA", "DK"], (21, True), "Blackjack (Ace high). Soft 21."),
            (["DJ", "CA"], (21, True), "Blackjack (Ace low on face, but Ace is 11). Soft 21."),
            (["HA", "DA", "C3"], (15, True), "A,A,3 -> 11,1,3 = 15. Soft 15."),
            (["HK", "DQ", "D5"], (25, False), "Bust K,Q,5 -> 10,10,5 = 25. Hard 25."),
            (["HA", "DA", "HK"], (12, False), "A,A,K -> 1,1,10 = 12. Hard 12."),
            (["HA", "DA", "D8", "H2"], (12, False), "A,A,8,2 -> 1,1,8,2 = 12. Hard 12."),
            (["SA", "HA", "DA", "CA"], (14, True), "A,A,A,A -> 11,1,1,1 = 14. Soft 14."),
            (["S5", "H6", "DA"], (12, False), "5,6,A -> 5,6,1 = 12. Hard 12."),
            (["SK", "HQ", "DJ", "HT"], (40, False), "K,Q,J,T -> 10,10,10,10 = 40. Hard 40."),
            (["HA", "H2", "H3", "H4", "H5", "H6"], (21, False), "A,2,3,4,5,6 -> 1,... = 21. Hard 21."),
            (["H7", "H8", "H6"], (21, False), "7,8,6 -> 21. Hard 21."),
        ]

        for hand, expected_value, description in test_cases:
            with self.subTest(description=description, hand=hand):
                self.assertEqual(_calculate_hand_value(hand), expected_value)

    def test_determine_winner_for_hand(self):
        """Test win/loss/push determination for a single player hand vs dealer."""
        table_rules = {'blackjack_payout': 1.5}

        p_hand_20 = _create_player_hand_obj(["HK", "DT"], bet_sats=10)
        p_hand_18 = _create_player_hand_obj(["H8", "DT"], bet_sats=10)
        p_hand_bj = _create_player_hand_obj(["HA", "DK"], bet_sats=10)
        p_hand_bust = _create_player_hand_obj(["H7", "D8", "ST"], bet_sats=10)

        p_hand_doubled_20_cards = ["H5", "H5", "HK"]
        p_hand_doubled_20 = _create_player_hand_obj(p_hand_doubled_20_cards, bet_sats=10)
        p_hand_doubled_20['bet_multiplier'] = 2.0

        d_hand_20 = _create_player_hand_obj(["SK", "CT"])
        d_hand_19 = _create_player_hand_obj(["S9", "CT"])
        d_hand_bj = _create_player_hand_obj(["SA", "CJ"])
        d_hand_bust = _create_player_hand_obj(["S7", "D8", "CT"])

        test_cases = [
            (p_hand_20, d_hand_19, (20, 'win'), "Player 20 vs Dealer 19"),
            (p_hand_18, d_hand_bust, (20, 'win'), "Player 18 vs Dealer Bust"),
            (p_hand_bj, d_hand_20, (25, 'blackjack_win'), "Player BJ vs Dealer 20"),
            (p_hand_doubled_20, d_hand_19, (40, 'win'), "Player Doubled 20 (eff. bet 20) vs Dealer 19"),

            (p_hand_18, d_hand_20, (0, 'lose'), "Player 18 vs Dealer 20"),
            (p_hand_bust, d_hand_19, (0, 'lose'), "Player Bust vs Dealer 19"),
            (p_hand_20, d_hand_bj, (0, 'lose'), "Player 20 vs Dealer BJ"),
            (p_hand_doubled_20, d_hand_bj, (0, 'lose'), "Player Doubled 20 vs Dealer BJ"),

            (p_hand_20, d_hand_20, (10, 'push'), "Player 20 vs Dealer 20 (Push)"),
            (p_hand_bj, d_hand_bj, (10, 'push'), "Player BJ vs Dealer BJ (Push)"),
            (p_hand_doubled_20, d_hand_20, (20, 'push'), "Player Doubled 20 (eff. bet 20) vs Dealer 20 (Push)"),
        ]

        for p_hand, d_hand, expected_result, description in test_cases:
            if 'bet_multiplier' not in p_hand: p_hand['bet_multiplier'] = 1.0
            if 'bet_multiplier' not in d_hand: d_hand['bet_multiplier'] = 1.0

            with self.subTest(description=description, player_hand=p_hand['cards'], dealer_hand=d_hand['cards']):
                amount_returned, result_str = _determine_winner_for_hand(p_hand, d_hand, table_rules)
                self.assertEqual(amount_returned, expected_result[0], f"Amount returned: Expected {expected_result[0]}, got {amount_returned}")
                self.assertEqual(result_str, expected_result[1], f"Result string: Expected '{expected_result[1]}', got '{result_str}'")


class TestBonusLogicUtils(BaseTestCase): # Inherit from BaseTestCase for app_context and db session

    # Re-using _create_user from BaseTestCase, and _create_bonus_code needs to be accessible
    # We can either duplicate it here, or make it part of BaseTestCase in test_api.py (which was done)
    # and ensure test_utils.py can use it. For now, assume BaseTestCase has it.

    def test_update_wagering_progress(self):
        # User created via BaseTestCase's _create_user helper
        user = self._create_user(username="bonuswageruser", email="bwu@example.com", balance=5000)

        # Bonus code created via BaseTestCase's _create_bonus_code helper
        # Ensure this helper is available in BaseTestCase as defined in the previous step for test_api.py
        bonus_code = self._create_bonus_code(code_id="WAGERTEST", wagering_multiplier=10)

        with self.app.app_context(): # Ensure app context for DB operations
            # Create a bonus that requires wagering
            user_bonus = UserBonus(
                user_id=user.id,
                bonus_code_id=bonus_code.id, # Use the ID from the created bonus code
                bonus_amount_awarded_sats=100,
                wagering_requirement_multiplier=bonus_code.wagering_requirement_multiplier, # from bonus code
                wagering_requirement_sats=100 * bonus_code.wagering_requirement_multiplier, # e.g. 100 * 10 = 1000
                wagering_progress_sats=0,
                is_active=True,
                is_completed=False,
                is_cancelled=False,
                activated_at=datetime.now(timezone.utc)
            )
            db.session.add(user_bonus)
            db.session.commit()
            db.session.refresh(user_bonus)

            # Simulate a bet of 50
            # _update_wagering_progress is imported from blackjack_helper
            _update_wagering_progress(user, 50, db.session)
            # _update_wagering_progress itself does not commit the session,
            # so we need to commit here to persist changes for subsequent assertions.
            db.session.commit()
            db.session.refresh(user_bonus) # Refresh to get the latest state from DB

            self.assertEqual(user_bonus.wagering_progress_sats, 50)
            self.assertTrue(user_bonus.is_active)
            self.assertFalse(user_bonus.is_completed)

            # Simulate another bet of (requirement - 50), e.g., 1000 - 50 = 950
            remaining_wagering = user_bonus.wagering_requirement_sats - user_bonus.wagering_progress_sats
            _update_wagering_progress(user, remaining_wagering, db.session)
            db.session.commit()
            db.session.refresh(user_bonus)

            self.assertEqual(user_bonus.wagering_progress_sats, user_bonus.wagering_requirement_sats)
            self.assertFalse(user_bonus.is_active, "Bonus should be inactive after wagering completion")
            self.assertTrue(user_bonus.is_completed, "Bonus should be completed after wagering completion")


if __name__ == '__main__':
    unittest.main()
