import unittest
from unittest.mock import MagicMock, patch

from casino_be.utils.poker_helper import _validate_bet, _calculate_pot_limit_raise_sizes
from casino_be.models import PokerPlayerState, PokerTable # Only need these, not full db setup
from casino_be.app import app # Import the app instance

class TestCalculatePotLimitRaiseSizes(unittest.TestCase):
    def setUp(self):
        self.app_context = app.app_context()
        self.app_context.push()

    def tearDown(self):
        self.app_context.pop()

    def test_basic_pot_limit_raise_scenario(self):
        # Player stack: 1000, Player invested this street: 50 (call previous bet)
        # Current pot total (before this player's call): 150
        # Bet to match this street: 50 (player already called this, or it's the blind)
        # Min valid raise increment: 50 (e.g. Big Blind)

        # Player needs to add 0 to call (already invested 50, bet_to_match is 50)
        # Pot size if player calls: 150 (current_pot_total) + 0 (amount_to_call_action) = 150
        # Max raise increment player can make: 150
        # Total chips for pot raise action: 0 (call) + 150 (raise) = 150
        # Max player investment this street: 50 (already_in) + 150 (pot_raise_chips) = 200

        # Min raise target: 50 (bet_to_match) + 50 (min_increment) = 100 (total investment)
        min_target, max_target = _calculate_pot_limit_raise_sizes(
            player_current_stack=1000,
            player_invested_this_street=50,
            current_pot_total=150,
            bet_to_match_this_street=50,
            min_valid_raise_increment=50
        )
        self.assertEqual(min_target, 100) # Min raise makes total street investment 100
        self.assertEqual(max_target, 200) # Max pot raise makes total street investment 200

    def test_pot_limit_raise_opening_bet_scenario(self):
        # Opening bet scenario (no prior bet this street)
        # Player stack: 1000, Player invested this street: 0
        # Current pot total (before this player's action): 75 (e.g. blinds from pre-flop)
        # Bet to match this street: 0
        # Min valid raise increment: 25 (e.g. Big Blind, also min opening bet)

        # Amount to call: 0
        # Pot size if player calls (conceptually, as it's an opening bet): 75 + 0 = 75
        # Max raise increment (max bet size): 75
        # Total chips for pot raise action: 0 (call) + 75 (raise) = 75
        # Max player investment this street: 0 (already_in) + 75 (pot_bet_chips) = 75

        # Min raise target (min opening bet): 0 (bet_to_match) + 25 (min_increment) = 25
        min_target, max_target = _calculate_pot_limit_raise_sizes(
            player_current_stack=1000,
            player_invested_this_street=0,
            current_pot_total=75,
            bet_to_match_this_street=0,
            min_valid_raise_increment=25
        )
        self.assertEqual(min_target, 25) # Min opening bet is 25
        self.assertEqual(max_target, 75) # Max pot opening bet is 75

    def test_pot_limit_raise_player_all_in_for_min_raise(self):
        # Player stack: 70, Player invested this street: 50
        # Current pot total: 200, Bet to match: 100, Min increment: 100
        # Player needs 50 to call. Stack is 70.
        # Min raise target total: 100 (bet_to_match) + 100 (min_increment) = 200
        # Chips for min raise action: 200 (target) - 50 (invested) = 150
        # Chips player can add: min(150, 70 (stack)) = 70
        # Effective min raise total: 50 (invested) + 70 (all_in_chips) = 120

        # Max raise:
        # Amount to call: 100 - 50 = 50
        # Pot if calls: 200 + 50 = 250
        # Max raise increment: 250
        # Chips for pot raise action: 50 (call) + 250 (raise) = 300
        # Chips player can add: min(300, 70 (stack)) = 70
        # Effective max raise total: 50 (invested) + 70 (all_in_chips) = 120
        min_target, max_target = _calculate_pot_limit_raise_sizes(
            player_current_stack=70,
            player_invested_this_street=50,
            current_pot_total=200,
            bet_to_match_this_street=100,
            min_valid_raise_increment=100
        )
        self.assertEqual(min_target, 120) # All-in amount is the only possible "raise"
        self.assertEqual(max_target, 120) # All-in amount becomes both min and max

    def test_pot_limit_cannot_make_min_raise_increment_can_only_call(self):
        # Player stack: 20, Player invested this street: 50
        # Current pot total: 200, Bet to match: 100, Min increment: 100
        # Player needs 50 to call. Stack is 20. Can only call all-in for 20.
        # Min raise target total: 100 + 100 = 200. Player cannot make this.
        # All-in total investment: 50 + 20 = 70. This is less than bet_to_match (100).
        # So, no raise is possible.
        min_target, max_target = _calculate_pot_limit_raise_sizes(
            player_current_stack=20,
            player_invested_this_street=50,
            current_pot_total=200,
            bet_to_match_this_street=100,
            min_valid_raise_increment=100
        )
        # Function returns (bet_to_match_this_street, all_in_total_investment_for_street)
        # if all_in_total_investment_for_street <= bet_to_match_this_street
        self.assertEqual(min_target, 100) # Min target effectively becomes the call amount
        self.assertEqual(max_target, 70)  # Max is their all-in amount (which is a call for less)


class TestValidateBet(unittest.TestCase):
    def setUp(self):
        self.app_context = app.app_context()
        self.app_context.push()
        self.mock_player_state = MagicMock(spec=PokerPlayerState)
        self.mock_poker_table = MagicMock(spec=PokerTable)
        self.mock_poker_table.big_blind = 20
        self.mock_poker_table.small_blind = 10

    def tearDown(self):
        self.app_context.pop()

    # No Limit Tests
    def test_nl_valid_opening_bet(self):
        self.mock_player_state.stack_sats = 1000
        self.mock_poker_table.limit_type = 'no_limit'
        is_valid, msg = _validate_bet(
            player_state=self.mock_player_state, action_amount=50, current_bet_to_match=0,
            min_next_raise_increment=20, limit_type='no_limit', poker_table=self.mock_poker_table,
            player_amount_invested_this_street=0, current_hand_pot_size=0
        )
        self.assertTrue(is_valid)
        self.assertIn("Valid No-Limit opening bet", msg)

    def test_nl_invalid_opening_bet_too_small(self):
        self.mock_player_state.stack_sats = 1000
        self.mock_poker_table.limit_type = 'no_limit'
        is_valid, msg = _validate_bet(
            player_state=self.mock_player_state, action_amount=10, current_bet_to_match=0,
            min_next_raise_increment=20, limit_type='no_limit', poker_table=self.mock_poker_table,
            player_amount_invested_this_street=0, current_hand_pot_size=0
        )
        self.assertFalse(is_valid)
        self.assertIn("less than minimum opening bet size", msg)

    def test_nl_valid_all_in_opening_bet_less_than_bb(self):
        self.mock_player_state.stack_sats = 10
        self.mock_poker_table.limit_type = 'no_limit'
        is_valid, msg = _validate_bet( # action_amount is total investment for street
            player_state=self.mock_player_state, action_amount=10, current_bet_to_match=0,
            min_next_raise_increment=20, limit_type='no_limit', poker_table=self.mock_poker_table,
            player_amount_invested_this_street=0, current_hand_pot_size=0
        )
        self.assertTrue(is_valid, msg)
        self.assertIn("Valid No-Limit all-in opening bet", msg)

    def test_nl_valid_raise(self):
        self.mock_player_state.stack_sats = 1000
        self.mock_poker_table.limit_type = 'no_limit'
        # current bet 50, min_next_raise_increment 50, so min raise TO is 100
        is_valid, msg = _validate_bet(
            player_state=self.mock_player_state, action_amount=100, current_bet_to_match=50,
            min_next_raise_increment=50, limit_type='no_limit', poker_table=self.mock_poker_table,
            player_amount_invested_this_street=0, current_hand_pot_size=100
        )
        self.assertTrue(is_valid, msg)
        self.assertIn("Valid No-Limit raise", msg)

    def test_nl_invalid_raise_too_small(self):
        self.mock_player_state.stack_sats = 1000
        self.mock_poker_table.limit_type = 'no_limit'
        # current bet 50, min_next_raise_increment 50, so min raise TO is 100
        is_valid, msg = _validate_bet(
            player_state=self.mock_player_state, action_amount=70, current_bet_to_match=50, # Trying to raise to 70
            min_next_raise_increment=50, limit_type='no_limit', poker_table=self.mock_poker_table,
            player_amount_invested_this_street=0, current_hand_pot_size=100
        )
        self.assertFalse(is_valid)
        self.assertIn("less than minimum required raise total", msg)

    def test_nl_valid_all_in_raise_less_than_min_increment(self):
        self.mock_player_state.stack_sats = 30
        self.mock_poker_table.limit_type = 'no_limit'
         # Player invested 50 (call). Current bet 50. Wants to raise all-in for 30 more, total 80.
         # Min_next_raise_increment is 50. Min raise TO should be 50+50=100.
         # All-in to 80 is valid.
        is_valid, msg = _validate_bet(
            player_state=self.mock_player_state, action_amount=80, current_bet_to_match=50,
            min_next_raise_increment=50, limit_type='no_limit', poker_table=self.mock_poker_table,
            player_amount_invested_this_street=50, current_hand_pot_size=150
        )
        self.assertTrue(is_valid, msg)
        self.assertIn("Valid No-Limit all-in raise", msg)

    def test_valid_call(self):
        self.mock_player_state.stack_sats = 100
        is_valid, msg = _validate_bet(
            player_state=self.mock_player_state, action_amount=50, current_bet_to_match=50,
            min_next_raise_increment=20, limit_type='no_limit', poker_table=self.mock_poker_table,
            player_amount_invested_this_street=0, current_hand_pot_size=50
        )
        self.assertTrue(is_valid, msg)
        self.assertIn("Valid call", msg)

    def test_valid_check(self):
        self.mock_player_state.stack_sats = 100
        is_valid, msg = _validate_bet(
            player_state=self.mock_player_state, action_amount=50, current_bet_to_match=50,
            min_next_raise_increment=20, limit_type='no_limit', poker_table=self.mock_poker_table,
            player_amount_invested_this_street=50, # Already invested matching amount
            current_hand_pot_size=100
        )
        self.assertTrue(is_valid, msg)
        self.assertIn("Valid check", msg)

    def test_insufficient_stack_for_action(self):
        self.mock_player_state.stack_sats = 30
        # Trying to make total street investment 50 (by adding 50), but only has 30.
        is_valid, msg = _validate_bet(
            player_state=self.mock_player_state, action_amount=50, current_bet_to_match=0,
            min_next_raise_increment=20, limit_type='no_limit', poker_table=self.mock_poker_table,
            player_amount_invested_this_street=0, current_hand_pot_size=0
        )
        self.assertFalse(is_valid)
        self.assertIn("Insufficient stack", msg)

    # Pot Limit Tests (Leveraging _calculate_pot_limit_raise_sizes indirectly via _validate_bet)
    @patch('casino_be.utils.poker_helper._calculate_pot_limit_raise_sizes')
    def test_pl_valid_opening_bet(self, mock_calc_pl):
        self.mock_player_state.stack_sats = 1000
        self.mock_poker_table.limit_type = 'pot_limit'
        # Opening bet of 50. Min opening is 20 (BB). Max pot opening bet (e.g. if pot was 50 before this) is 50.
        mock_calc_pl.return_value = (20, 50) # (min_target, max_target) for opening bet

        is_valid, msg = _validate_bet(
            player_state=self.mock_player_state, action_amount=50, current_bet_to_match=0,
            min_next_raise_increment=20, limit_type='pot_limit', poker_table=self.mock_poker_table,
            player_amount_invested_this_street=0, current_hand_pot_size=50 # pot before this action
        )
        self.assertTrue(is_valid, msg)
        self.assertIn("Valid Pot-Limit opening bet", msg)
        mock_calc_pl.assert_called_once()


    @patch('casino_be.utils.poker_helper._calculate_pot_limit_raise_sizes')
    def test_pl_invalid_opening_bet_exceeds_pot(self, mock_calc_pl):
        self.mock_player_state.stack_sats = 1000
        self.mock_poker_table.limit_type = 'pot_limit'
        # Max pot opening bet is 50, player tries 60.
        mock_calc_pl.return_value = (20, 50)

        is_valid, msg = _validate_bet(
            player_state=self.mock_player_state, action_amount=60, current_bet_to_match=0,
            min_next_raise_increment=20, limit_type='pot_limit', poker_table=self.mock_poker_table,
            player_amount_invested_this_street=0, current_hand_pot_size=50
        )
        self.assertFalse(is_valid)
        self.assertIn("exceeds max pot limit target", msg)

    # Fixed Limit Tests (Simplified: uses BB as fixed amount)
    def test_fl_valid_opening_bet(self):
        self.mock_player_state.stack_sats = 1000
        self.mock_poker_table.limit_type = 'fixed_limit'
        self.mock_poker_table.big_blind = 20 # Fixed bet amount for this test
        is_valid, msg = _validate_bet(
            player_state=self.mock_player_state, action_amount=20, current_bet_to_match=0,
            min_next_raise_increment=20, limit_type='fixed_limit', poker_table=self.mock_poker_table,
            player_amount_invested_this_street=0, current_hand_pot_size=0
        )
        self.assertTrue(is_valid, msg)
        self.assertIn("Valid Fixed-Limit bet", msg)

    def test_fl_invalid_opening_bet_wrong_amount(self):
        self.mock_player_state.stack_sats = 1000
        self.mock_poker_table.limit_type = 'fixed_limit'
        self.mock_poker_table.big_blind = 20
        is_valid, msg = _validate_bet(
            player_state=self.mock_player_state, action_amount=30, current_bet_to_match=0,
            min_next_raise_increment=20, limit_type='fixed_limit', poker_table=self.mock_poker_table,
            player_amount_invested_this_street=0, current_hand_pot_size=0
        )
        self.assertFalse(is_valid)
        self.assertIn("must be exactly 20", msg)

    def test_fl_valid_raise(self):
        self.mock_player_state.stack_sats = 1000
        self.mock_poker_table.limit_type = 'fixed_limit'
        self.mock_poker_table.big_blind = 20 # Fixed raise increment
        # Current bet 20. Raise must be TO 40. Player invested 0, action_amount is 40.
        is_valid, msg = _validate_bet(
            player_state=self.mock_player_state, action_amount=40, current_bet_to_match=20,
            min_next_raise_increment=20, limit_type='fixed_limit', poker_table=self.mock_poker_table,
            player_amount_invested_this_street=0, current_hand_pot_size=40
        )
        self.assertTrue(is_valid, msg)
        self.assertIn("Valid Fixed-Limit raise", msg)

    def test_fl_invalid_raise_wrong_amount(self):
        self.mock_player_state.stack_sats = 1000
        self.mock_poker_table.limit_type = 'fixed_limit'
        self.mock_poker_table.big_blind = 20
        # Current bet 20. Raise must be TO 40. Player tries to raise to 50.
        is_valid, msg = _validate_bet(
            player_state=self.mock_player_state, action_amount=50, current_bet_to_match=20,
            min_next_raise_increment=20, limit_type='fixed_limit', poker_table=self.mock_poker_table,
            player_amount_invested_this_street=0, current_hand_pot_size=40
        )
        self.assertFalse(is_valid)
        self.assertIn("Must make total investment 40", msg)


if __name__ == '__main__':
    unittest.main()
