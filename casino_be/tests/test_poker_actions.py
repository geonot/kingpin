import unittest
from unittest.mock import patch, MagicMock, ANY
from datetime import datetime, timezone

# Assuming casino_be.utils.poker_helper and casino_be.models are accessible
# Adjust imports based on actual project structure if using relative imports from test location
from casino_be.utils.poker_helper import handle_fold, handle_check, handle_call, handle_bet, handle_raise
from casino_be.models import User, PokerTable, PokerHand, PokerPlayerState, Transaction, db

# Helper to create a mock session
def create_mock_session():
    mock_session = MagicMock(spec=db.session)
    mock_session.query.return_value.filter_by.return_value.first.return_value = None
    mock_session.query.return_value.get.return_value = None
    mock_session.add = MagicMock()
    mock_session.commit = MagicMock()
    mock_session.rollback = MagicMock()
    return mock_session

class TestHandleFold(unittest.TestCase):

    def setUp(self):
        self.mock_db_session = create_mock_session()
        # Patch db.session for all tests in this class that use poker_helper functions
        self.db_session_patch = patch('casino_be.utils.poker_helper.db.session', self.mock_db_session)
        self.mock_db_session_instance = self.db_session_patch.start()

        self.user_id = 1
        self.table_id = 101
        self.hand_id = 201
        self.seat_id = 1

        self.mock_player_state = PokerPlayerState(
            user_id=self.user_id,
            table_id=self.table_id,
            seat_id=self.seat_id,
            stack_sats=10000,
            is_active_in_hand=True,
            time_to_act_ends=datetime.now(timezone.utc)
        )
        self.mock_poker_hand = PokerHand(
            id=self.hand_id,
            table_id=self.table_id,
            current_turn_user_id=self.user_id,
            pot_size_sats=500,
            hand_history=[],
            player_street_investments={},
            current_bet_to_match=0
        )

    def tearDown(self):
        self.db_session_patch.stop()

    @patch('casino_be.utils.poker_helper._check_betting_round_completion')
    def test_handle_fold_success(self, mock_check_betting_completion):
        # Setup mocks for this specific test
        self.mock_db_session.query(PokerPlayerState).filter_by(user_id=self.user_id, table_id=self.table_id).first.return_value = self.mock_player_state
        self.mock_db_session.query(PokerHand).get(self.hand_id).first.return_value = self.mock_poker_hand # Corrected from .get(id) to .get(hand_id)
        # If PokerHand is fetched by primary key, .get() is more direct
        self.mock_db_session.query(PokerHand).get.return_value = self.mock_poker_hand


        mock_check_betting_completion.return_value = {"status": "betting_continues", "next_to_act_user_id": 2}

        result = handle_fold(user_id=self.user_id, table_id=self.table_id, hand_id=self.hand_id)

        self.assertFalse(self.mock_player_state.is_active_in_hand)
        self.assertEqual(self.mock_player_state.last_action, "fold")
        self.assertIsNone(self.mock_player_state.time_to_act_ends)

        self.assertTrue(self.mock_db_session.add.called)
        self.mock_db_session.add.assert_any_call(self.mock_player_state)
        self.mock_db_session.add.assert_any_call(self.mock_poker_hand)

        self.assertEqual(len(self.mock_poker_hand.hand_history), 1)
        self.assertEqual(self.mock_poker_hand.hand_history[0]['action'], "fold")
        self.assertEqual(self.mock_poker_hand.hand_history[0]['user_id'], self.user_id)

        mock_check_betting_completion.assert_called_once_with(self.hand_id, self.user_id, self.mock_db_session_instance)
        self.mock_db_session.commit.assert_called_once()

        self.assertIn("folded successfully", result["message"])
        self.assertEqual(result["game_flow"], {"status": "betting_continues", "next_to_act_user_id": 2})

    def test_handle_fold_player_state_not_found(self):
        self.mock_db_session.query(PokerPlayerState).filter_by(user_id=self.user_id, table_id=self.table_id).first.return_value = None
        self.mock_db_session.query(PokerHand).get.return_value = self.mock_poker_hand # Hand exists

        result = handle_fold(user_id=self.user_id, table_id=self.table_id, hand_id=self.hand_id)

        self.assertIn("error", result)
        self.assertIn(f"Player state for user {self.user_id} not found", result["error"])
        self.mock_db_session.commit.assert_not_called()

    def test_handle_fold_hand_not_found(self):
        self.mock_db_session.query(PokerPlayerState).filter_by(user_id=self.user_id, table_id=self.table_id).first.return_value = self.mock_player_state
        self.mock_db_session.query(PokerHand).get.return_value = None # Hand does not exist

        result = handle_fold(user_id=self.user_id, table_id=self.table_id, hand_id=self.hand_id)

        self.assertIn("error", result)
        self.assertIn(f"Poker hand {self.hand_id} not found", result["error"])
        self.mock_db_session.commit.assert_not_called()

    @patch('casino_be.utils.poker_helper._check_betting_round_completion')
    def test_handle_fold_player_not_active_in_hand(self, mock_check_betting_completion):
        self.mock_player_state.is_active_in_hand = False # Player already folded or not in hand
        self.mock_db_session.query(PokerPlayerState).filter_by(user_id=self.user_id, table_id=self.table_id).first.return_value = self.mock_player_state
        self.mock_db_session.query(PokerHand).get.return_value = self.mock_poker_hand

        result = handle_fold(user_id=self.user_id, table_id=self.table_id, hand_id=self.hand_id)

        self.assertIn("error", result)
        self.assertIn(f"Player {self.user_id} is not active in hand", result["error"])
        # time_to_act_ends should still be cleared and committed
        self.assertIsNone(self.mock_player_state.time_to_act_ends)
        self.mock_db_session.add.assert_called_once_with(self.mock_player_state)
        self.mock_db_session.commit.assert_called_once() # Commit for clearing timer
        mock_check_betting_completion.assert_not_called() # Game flow check shouldn't happen


class TestHandleCheck(unittest.TestCase):
    def setUp(self):
        self.mock_db_session = create_mock_session()
        self.db_session_patch = patch('casino_be.utils.poker_helper.db.session', self.mock_db_session)
        self.mock_db_session_instance = self.db_session_patch.start()

        self.user_id = 1
        self.table_id = 101
        self.hand_id = 201
        self.seat_id = 1

        self.mock_player_state = PokerPlayerState(
            user_id=self.user_id,
            table_id=self.table_id,
            seat_id=self.seat_id,
            stack_sats=10000,
            is_active_in_hand=True,
            time_to_act_ends=datetime.now(timezone.utc)
        )
        self.mock_poker_hand = PokerHand(
            id=self.hand_id,
            table_id=self.table_id,
            current_turn_user_id=self.user_id,
            pot_size_sats=500,
            hand_history=[],
            player_street_investments={}, # Player has 0 invested this street
            current_bet_to_match=0 # No bet to match, check is legal
        )

    def tearDown(self):
        self.db_session_patch.stop()

    @patch('casino_be.utils.poker_helper._check_betting_round_completion')
    def test_handle_check_success_no_bet_to_match(self, mock_check_betting_completion):
        self.mock_db_session.query(PokerPlayerState).filter_by(user_id=self.user_id, table_id=self.table_id).first.return_value = self.mock_player_state
        self.mock_db_session.query(PokerHand).get.return_value = self.mock_poker_hand

        mock_check_betting_completion.return_value = {"status": "betting_continues", "next_to_act_user_id": 2}

        result = handle_check(user_id=self.user_id, table_id=self.table_id, hand_id=self.hand_id)

        self.assertEqual(self.mock_player_state.last_action, "check")
        self.assertIsNone(self.mock_player_state.time_to_act_ends)
        self.assertEqual(len(self.mock_poker_hand.hand_history), 1)
        self.assertEqual(self.mock_poker_hand.hand_history[0]['action'], "check")

        self.mock_db_session.add.assert_any_call(self.mock_player_state)
        self.mock_db_session.add.assert_any_call(self.mock_poker_hand)
        mock_check_betting_completion.assert_called_once_with(self.hand_id, self.user_id, self.mock_db_session_instance)
        self.mock_db_session.commit.assert_called_once()

        self.assertIn("checked successfully", result["message"])
        self.assertEqual(result["game_flow"], {"status": "betting_continues", "next_to_act_user_id": 2})

    @patch('casino_be.utils.poker_helper._check_betting_round_completion')
    def test_handle_check_success_player_matched_bet(self, mock_check_betting_completion):
        self.mock_poker_hand.current_bet_to_match = 100
        self.mock_poker_hand.player_street_investments = {str(self.user_id): 100} # Player already matched

        self.mock_db_session.query(PokerPlayerState).filter_by(user_id=self.user_id, table_id=self.table_id).first.return_value = self.mock_player_state
        self.mock_db_session.query(PokerHand).get.return_value = self.mock_poker_hand
        mock_check_betting_completion.return_value = {"status": "round_completed_advancing_street"}

        result = handle_check(user_id=self.user_id, table_id=self.table_id, hand_id=self.hand_id)

        self.assertEqual(self.mock_player_state.last_action, "check")
        self.assertIn("checked successfully", result["message"])
        self.mock_db_session.commit.assert_called_once()

    def test_handle_check_fail_bet_to_match(self):
        self.mock_poker_hand.current_bet_to_match = 100 # There's a bet
        self.mock_poker_hand.player_street_investments = {str(self.user_id): 50} # Player has not matched it

        self.mock_db_session.query(PokerPlayerState).filter_by(user_id=self.user_id, table_id=self.table_id).first.return_value = self.mock_player_state
        self.mock_db_session.query(PokerHand).get.return_value = self.mock_poker_hand

        result = handle_check(user_id=self.user_id, table_id=self.table_id, hand_id=self.hand_id)

        self.assertIn("error", result)
        self.assertIn("Cannot check. Player", result["error"])
        self.assertIsNone(self.mock_player_state.time_to_act_ends) # Timer should still be cleared
        self.mock_db_session.add.assert_any_call(self.mock_player_state) # For timer clear
        self.mock_db_session.add.assert_any_call(self.mock_poker_hand) # For player_street_investments init
        self.mock_db_session.commit.assert_called_once() # Commit for timer clear and investment init

    def test_handle_check_fail_player_not_active(self):
        self.mock_player_state.is_active_in_hand = False
        self.mock_db_session.query(PokerPlayerState).filter_by(user_id=self.user_id, table_id=self.table_id).first.return_value = self.mock_player_state
        self.mock_db_session.query(PokerHand).get.return_value = self.mock_poker_hand

        result = handle_check(user_id=self.user_id, table_id=self.table_id, hand_id=self.hand_id)
        self.assertIn("error", result)
        self.assertIn(f"Player {self.user_id} is not active", result["error"])
        self.mock_db_session.commit.assert_called_once() # For timer clear

    def test_handle_check_hand_not_found(self):
        self.mock_db_session.query(PokerPlayerState).filter_by(user_id=self.user_id, table_id=self.table_id).first.return_value = self.mock_player_state
        self.mock_db_session.query(PokerHand).get.return_value = None

        result = handle_check(user_id=self.user_id, table_id=self.table_id, hand_id=self.hand_id)
        self.assertIn("error", result)
        self.assertIn(f"Poker hand {self.hand_id} not found", result["error"])


class TestHandleCall(unittest.TestCase):
    def setUp(self):
        self.mock_db_session = create_mock_session()
        self.db_session_patch = patch('casino_be.utils.poker_helper.db.session', self.mock_db_session)
        self.mock_db_session_instance = self.db_session_patch.start()

        self.user_id = 1
        self.table_id = 101
        self.hand_id = 201
        self.seat_id = 1

        self.mock_user = User(id=self.user_id, username="testuser") # For Transaction details
        self.mock_player_state = PokerPlayerState(
            user_id=self.user_id,
            table_id=self.table_id,
            seat_id=self.seat_id,
            stack_sats=10000,
            is_active_in_hand=True,
            time_to_act_ends=datetime.now(timezone.utc),
            user=self.mock_user, # Associate user
            total_invested_this_hand=0
        )
        self.mock_poker_hand = PokerHand(
            id=self.hand_id,
            table_id=self.table_id,
            current_turn_user_id=self.user_id,
            pot_size_sats=500,
            hand_history=[],
            player_street_investments={},
            current_bet_to_match=100, # Bet of 100 to call
            min_next_raise_amount=100
        )
        # Mock joinedload for player_state.user
        self.mock_db_session.query(PokerPlayerState).options.return_value.filter_by.return_value.first.return_value = self.mock_player_state


    def tearDown(self):
        self.db_session_patch.stop()

    @patch('casino_be.utils.poker_helper._check_betting_round_completion')
    @patch('casino_be.utils.poker_helper.Transaction') # Mock the Transaction class
    def test_handle_call_success_full_call(self, MockTransaction, mock_check_betting_completion):
        self.mock_db_session.query(PokerPlayerState).filter_by(user_id=self.user_id, table_id=self.table_id).first.return_value = self.mock_player_state
        self.mock_db_session.query(PokerHand).get.return_value = self.mock_poker_hand

        mock_check_betting_completion.return_value = {"status": "betting_continues", "next_to_act_user_id": 2}
        initial_stack = self.mock_player_state.stack_sats
        initial_pot_size = self.mock_poker_hand.pot_size_sats
        amount_to_call = self.mock_poker_hand.current_bet_to_match # 100

        result = handle_call(user_id=self.user_id, table_id=self.table_id, hand_id=self.hand_id)

        self.assertEqual(self.mock_player_state.stack_sats, initial_stack - amount_to_call)
        self.assertEqual(self.mock_player_state.total_invested_this_hand, amount_to_call)
        self.assertEqual(self.mock_poker_hand.pot_size_sats, initial_pot_size + amount_to_call)
        self.assertEqual(self.mock_poker_hand.player_street_investments[str(self.user_id)], amount_to_call)
        self.assertEqual(self.mock_player_state.last_action, f"call_{amount_to_call}")
        self.assertIsNone(self.mock_player_state.time_to_act_ends)

        MockTransaction.assert_called_once_with(
            user_id=self.user_id,
            amount=-amount_to_call,
            transaction_type='poker_action_call',
            status='completed',
            details=ANY, # Details can be complex, check specific parts if needed
            poker_hand_id=self.hand_id
        )
        self.mock_db_session.add.assert_any_call(MockTransaction())

        self.assertEqual(len(self.mock_poker_hand.hand_history), 1)
        self.assertEqual(self.mock_poker_hand.hand_history[0]['action'], "call")
        self.assertEqual(self.mock_poker_hand.hand_history[0]['amount'], amount_to_call)

        mock_check_betting_completion.assert_called_once_with(self.hand_id, self.user_id, self.mock_db_session_instance)
        self.mock_db_session.commit.assert_called_once()
        self.assertIn(f"User {self.user_id} calls {amount_to_call}", result["message"])

    @patch('casino_be.utils.poker_helper._check_betting_round_completion')
    @patch('casino_be.utils.poker_helper.Transaction')
    def test_handle_call_all_in_for_less(self, MockTransaction, mock_check_betting_completion):
        self.mock_player_state.stack_sats = 50 # Player has less than current_bet_to_match
        self.mock_poker_hand.current_bet_to_match = 100

        self.mock_db_session.query(PokerPlayerState).filter_by(user_id=self.user_id, table_id=self.table_id).first.return_value = self.mock_player_state
        self.mock_db_session.query(PokerHand).get.return_value = self.mock_poker_hand
        mock_check_betting_completion.return_value = {"status": "all_in_showdown"}

        actual_call_amount = 50 # Player goes all-in
        initial_pot_size = self.mock_poker_hand.pot_size_sats

        result = handle_call(user_id=self.user_id, table_id=self.table_id, hand_id=self.hand_id)

        self.assertEqual(self.mock_player_state.stack_sats, 0)
        self.assertEqual(self.mock_player_state.total_invested_this_hand, actual_call_amount)
        self.assertEqual(self.mock_poker_hand.pot_size_sats, initial_pot_size + actual_call_amount)
        self.assertEqual(self.mock_poker_hand.player_street_investments[str(self.user_id)], actual_call_amount)
        self.assertEqual(self.mock_player_state.last_action, f"call_all_in_{actual_call_amount}")

        MockTransaction.assert_called_once()
        self.assertEqual(MockTransaction.call_args[1]['amount'], -actual_call_amount)
        self.assertIn("call_all_in", result["message"])
        self.mock_db_session.commit.assert_called_once()

    def test_handle_call_fail_no_pending_bet(self):
        self.mock_poker_hand.current_bet_to_match = 0 # No bet to call
        self.mock_db_session.query(PokerPlayerState).filter_by(user_id=self.user_id, table_id=self.table_id).first.return_value = self.mock_player_state
        self.mock_db_session.query(PokerHand).get.return_value = self.mock_poker_hand

        result = handle_call(user_id=self.user_id, table_id=self.table_id, hand_id=self.hand_id)

        self.assertIn("error", result)
        self.assertIn("No pending bet to call", result["error"])
        self.mock_db_session.commit.assert_called_once() # For timer clear etc.

    def test_handle_call_fail_already_called_max(self):
        self.mock_poker_hand.current_bet_to_match = 100
        self.mock_poker_hand.player_street_investments = {str(self.user_id): 100} # Player already put in 100
        self.mock_db_session.query(PokerPlayerState).filter_by(user_id=self.user_id, table_id=self.table_id).first.return_value = self.mock_player_state
        self.mock_db_session.query(PokerHand).get.return_value = self.mock_poker_hand

        result = handle_call(user_id=self.user_id, table_id=self.table_id, hand_id=self.hand_id)
        self.assertIn("error", result)
        self.assertIn("No pending bet to call", result["error"])
        self.assertIn("Amount due is 0", result["error"])
        self.mock_db_session.commit.assert_called_once()


class TestHandleBet(unittest.TestCase):
    def setUp(self):
        self.mock_db_session = create_mock_session()
        self.db_session_patch = patch('casino_be.utils.poker_helper.db.session', self.mock_db_session)
        self.mock_db_session_instance = self.db_session_patch.start()

        self.user_id = 1
        self.table_id = 101
        self.hand_id = 201
        self.seat_id = 1

        self.mock_player_state = PokerPlayerState(
            user_id=self.user_id, table_id=self.table_id, seat_id=self.seat_id,
            stack_sats=10000, is_active_in_hand=True, time_to_act_ends=datetime.now(timezone.utc),
            total_invested_this_hand=0
        )
        self.mock_poker_hand = PokerHand(
            id=self.hand_id, table_id=self.table_id, current_turn_user_id=self.user_id,
            pot_size_sats=150, hand_history=[], player_street_investments={},
            current_bet_to_match=0, # No bet yet, so betting is allowed
            min_next_raise_amount=20 # Default BB for min_next_raise_amount often
        )
        self.mock_poker_table = PokerTable(id=self.table_id, big_blind=20, limit_type='no_limit')

        self.mock_db_session.query(PokerPlayerState).filter_by(user_id=self.user_id, table_id=self.table_id).first.return_value = self.mock_player_state
        self.mock_db_session.query(PokerHand).get.return_value = self.mock_poker_hand
        self.mock_db_session.query(PokerTable).get.return_value = self.mock_poker_table


    def tearDown(self):
        self.db_session_patch.stop()

    @patch('casino_be.utils.poker_helper._check_betting_round_completion')
    @patch('casino_be.utils.poker_helper._validate_bet') # Mock _validate_bet
    @patch('casino_be.utils.poker_helper.Transaction')
    def test_handle_bet_success(self, MockTransaction, mock_validate_bet, mock_check_betting_completion):
        bet_amount = 100
        mock_validate_bet.return_value = (True, "Valid No-Limit opening bet.")
        mock_check_betting_completion.return_value = {"status": "betting_continues", "next_to_act_user_id": 2}

        initial_stack = self.mock_player_state.stack_sats
        initial_pot_size = self.mock_poker_hand.pot_size_sats
        player_initial_street_investment = self.mock_poker_hand.player_street_investments.get(str(self.user_id), 0)


        result = handle_bet(user_id=self.user_id, table_id=self.table_id, hand_id=self.hand_id, amount=bet_amount)

        expected_total_street_investment = player_initial_street_investment + bet_amount

        mock_validate_bet.assert_called_once_with(
            player_state=self.mock_player_state,
            action_amount=expected_total_street_investment,
            current_bet_to_match=self.mock_poker_hand.current_bet_to_match, # Before action, it's 0
            min_next_raise_increment=self.mock_poker_hand.min_next_raise_amount or self.mock_poker_table.big_blind,
            limit_type=self.mock_poker_table.limit_type,
            poker_table=self.mock_poker_table,
            player_amount_invested_this_street=player_initial_street_investment,
            current_hand_pot_size=initial_pot_size
        )

        self.assertEqual(self.mock_player_state.stack_sats, initial_stack - bet_amount)
        self.assertEqual(self.mock_player_state.total_invested_this_hand, bet_amount)
        self.assertEqual(self.mock_poker_hand.pot_size_sats, initial_pot_size + bet_amount)
        self.assertEqual(self.mock_poker_hand.player_street_investments[str(self.user_id)], expected_total_street_investment)
        self.assertEqual(self.mock_poker_hand.current_bet_to_match, expected_total_street_investment)
        self.assertEqual(self.mock_poker_hand.last_raiser_user_id, self.user_id)
        self.assertEqual(self.mock_poker_hand.min_next_raise_amount, bet_amount) # Bet size becomes next min raise increment
        self.assertEqual(self.mock_player_state.last_action, f"bet_{bet_amount}")

        MockTransaction.assert_called_once()
        self.assertEqual(MockTransaction.call_args[1]['amount'], -bet_amount)

        self.assertIn(f"User {self.user_id} bets {bet_amount}", result["message"])
        self.mock_db_session.commit.assert_called_once()

    @patch('casino_be.utils.poker_helper._validate_bet')
    def test_handle_bet_fail_validation(self, mock_validate_bet):
        bet_amount = 10 # Too small
        mock_validate_bet.return_value = (False, "Bet amount too small.")

        result = handle_bet(user_id=self.user_id, table_id=self.table_id, hand_id=self.hand_id, amount=bet_amount)

        self.assertIn("error", result)
        self.assertIn("Invalid bet: Bet amount too small.", result["error"])
        self.mock_db_session.commit.assert_not_called() # Should fail before commit typically, unless only timer was saved

    def test_handle_bet_fail_outstanding_bet(self):
        self.mock_poker_hand.current_bet_to_match = 100 # There is an outstanding bet
        self.mock_poker_hand.player_street_investments = {str(self.user_id): 0} # Player hasn't called it

        result = handle_bet(user_id=self.user_id, table_id=self.table_id, hand_id=self.hand_id, amount=50)

        self.assertIn("error", result)
        self.assertIn("Cannot bet. Must call or raise existing bet", result["error"])
        # self.mock_db_session.commit.assert_called_once() # For timer clear.

    @patch('casino_be.utils.poker_helper._check_betting_round_completion')
    @patch('casino_be.utils.poker_helper._validate_bet')
    @patch('casino_be.utils.poker_helper.Transaction')
    def test_handle_bet_all_in(self, MockTransaction, mock_validate_bet, mock_check_betting_completion):
        bet_amount = 10000 # Player intends to bet their whole stack
        self.mock_player_state.stack_sats = 10000
        mock_validate_bet.return_value = (True, "Valid No-Limit all-in opening bet.")
        mock_check_betting_completion.return_value = {"status": "all_in_showdown"}

        result = handle_bet(user_id=self.user_id, table_id=self.table_id, hand_id=self.hand_id, amount=bet_amount)

        self.assertEqual(self.mock_player_state.stack_sats, 0)
        self.assertEqual(self.mock_player_state.last_action, f"bet_all_in_{bet_amount}")
        self.assertIn(f"User {self.user_id} bet_all_in_s {bet_amount}", result["message"])
        self.mock_db_session.commit.assert_called_once()


class TestHandleRaise(unittest.TestCase):
    def setUp(self):
        self.mock_db_session = create_mock_session()
        self.db_session_patch = patch('casino_be.utils.poker_helper.db.session', self.mock_db_session)
        self.mock_db_session_instance = self.db_session_patch.start()

        self.user_id = 1
        self.table_id = 101
        self.hand_id = 201
        self.seat_id = 1

        self.mock_player_state = PokerPlayerState(
            user_id=self.user_id, table_id=self.table_id, seat_id=self.seat_id,
            stack_sats=10000, is_active_in_hand=True, time_to_act_ends=datetime.now(timezone.utc),
            total_invested_this_hand=50 # Player already invested 50 (e.g. call or part of blind)
        )
        self.mock_poker_hand = PokerHand(
            id=self.hand_id, table_id=self.table_id, current_turn_user_id=self.user_id,
            pot_size_sats=200, hand_history=[],
            player_street_investments={str(self.user_id): 50}, # Player's current investment this street
            current_bet_to_match=100, # Current bet to match is 100
            min_next_raise_amount=100 # Min increment for a raise
        )
        self.mock_poker_table = PokerTable(id=self.table_id, big_blind=50, limit_type='no_limit')

        self.mock_db_session.query(PokerPlayerState).filter_by(user_id=self.user_id, table_id=self.table_id).first.return_value = self.mock_player_state
        self.mock_db_session.query(PokerHand).get.return_value = self.mock_poker_hand
        self.mock_db_session.query(PokerTable).get.return_value = self.mock_poker_table

    def tearDown(self):
        self.db_session_patch.stop()

    @patch('casino_be.utils.poker_helper._check_betting_round_completion')
    @patch('casino_be.utils.poker_helper._validate_bet') # Mock _validate_bet
    @patch('casino_be.utils.poker_helper.Transaction')
    def test_handle_raise_success(self, MockTransaction, mock_validate_bet, mock_check_betting_completion):
        # Player has 50 in, current bet is 100. Min increment is 100. So min raise TO is 100 (call) + 100 (raise) = 200.
        # Player wants to raise TO 250. Needs to add 200 more chips.
        raise_to_amount_total = 250

        mock_validate_bet.return_value = (True, "Valid No-Limit raise.")
        mock_check_betting_completion.return_value = {"status": "betting_continues", "next_to_act_user_id": 2}

        initial_stack = self.mock_player_state.stack_sats # 10000
        initial_pot_size = self.mock_poker_hand.pot_size_sats # 200
        player_initial_street_investment = self.mock_poker_hand.player_street_investments[str(self.user_id)] # 50
        previous_bet_to_match = self.mock_poker_hand.current_bet_to_match # 100

        amount_player_needs_to_add = raise_to_amount_total - player_initial_street_investment # 250 - 50 = 200

        result = handle_raise(user_id=self.user_id, table_id=self.table_id, hand_id=self.hand_id, amount=raise_to_amount_total)

        mock_validate_bet.assert_called_once_with(
            player_state=self.mock_player_state,
            action_amount=raise_to_amount_total,
            current_bet_to_match=previous_bet_to_match,
            min_next_raise_increment=self.mock_poker_hand.min_next_raise_amount or self.mock_poker_table.big_blind,
            limit_type=self.mock_poker_table.limit_type,
            poker_table=self.mock_poker_table,
            player_amount_invested_this_street=player_initial_street_investment,
            current_hand_pot_size=initial_pot_size
        )

        self.assertEqual(self.mock_player_state.stack_sats, initial_stack - amount_player_needs_to_add)
        self.assertEqual(self.mock_player_state.total_invested_this_hand, player_initial_street_investment + amount_player_needs_to_add) # total_invested_this_hand already had 50
        self.assertEqual(self.mock_poker_hand.pot_size_sats, initial_pot_size + amount_player_needs_to_add)
        self.assertEqual(self.mock_poker_hand.player_street_investments[str(self.user_id)], raise_to_amount_total)
        self.assertEqual(self.mock_poker_hand.current_bet_to_match, raise_to_amount_total)
        self.assertEqual(self.mock_poker_hand.last_raiser_user_id, self.user_id)
        self.assertEqual(self.mock_poker_hand.min_next_raise_amount, raise_to_amount_total - previous_bet_to_match) # Raise amount itself
        self.assertEqual(self.mock_player_state.last_action, f"raise_to_{raise_to_amount_total}")

        MockTransaction.assert_called_once()
        self.assertEqual(MockTransaction.call_args[1]['amount'], -amount_player_needs_to_add)

        self.assertIn(f"User {self.user_id} raises to {raise_to_amount_total}", result["message"])
        self.mock_db_session.commit.assert_called_once()

    @patch('casino_be.utils.poker_helper._validate_bet')
    def test_handle_raise_fail_validation(self, mock_validate_bet):
        raise_to_amount = 150 # Too small (less than current bet + min increment)
        mock_validate_bet.return_value = (False, "Raise amount too small.")

        result = handle_raise(user_id=self.user_id, table_id=self.table_id, hand_id=self.hand_id, amount=raise_to_amount)

        self.assertIn("error", result)
        self.assertIn("Invalid raise: Raise amount too small.", result["error"])
        self.mock_db_session.commit.assert_not_called()

    def test_handle_raise_fail_no_prior_bet(self):
        self.mock_poker_hand.current_bet_to_match = 0 # No prior bet

        result = handle_raise(user_id=self.user_id, table_id=self.table_id, hand_id=self.hand_id, amount=100)

        self.assertIn("error", result)
        self.assertIn("Cannot raise, no prior bet.", result["error"])
        # self.mock_db_session.commit.assert_called_once() # For timer clear

    @patch('casino_be.utils.poker_helper._check_betting_round_completion')
    @patch('casino_be.utils.poker_helper._validate_bet')
    @patch('casino_be.utils.poker_helper.Transaction')
    def test_handle_raise_all_in_incomplete_raise(self, MockTransaction, mock_validate_bet, mock_check_betting_completion):
        # Current bet 100, player has 50 invested. Player stack is 70.
        # Player wants to raise TO 120 (50 call + 20 raise), which is their all-in.
        # Min raise would be to 200. This is an incomplete all-in raise.
        self.mock_player_state.stack_sats = 70
        self.mock_player_state.total_invested_this_hand = 50
        self.mock_poker_hand.player_street_investments = {str(self.user_id): 50}
        self.mock_poker_hand.current_bet_to_match = 100

        raise_to_amount_total = 120 # Player goes all-in for 70 more, total investment 120
        actual_added_to_pot = 70

        mock_validate_bet.return_value = (True, "Valid No-Limit all-in raise.") # _validate_bet should confirm this is valid all-in
        mock_check_betting_completion.return_value = {"status": "all_in_showdown"}

        result = handle_raise(user_id=self.user_id, table_id=self.table_id, hand_id=self.hand_id, amount=raise_to_amount_total)

        self.assertEqual(self.mock_player_state.stack_sats, 0)
        self.assertEqual(self.mock_player_state.total_invested_this_hand, 50 + actual_added_to_pot)
        self.assertEqual(self.mock_poker_hand.player_street_investments[str(self.user_id)], raise_to_amount_total)
        self.assertEqual(self.mock_poker_hand.current_bet_to_match, raise_to_amount_total) # Current bet becomes the all-in amount
        self.assertEqual(self.mock_poker_hand.last_raiser_user_id, self.user_id)
        self.assertEqual(self.mock_poker_hand.min_next_raise_amount, raise_to_amount_total - 100) # The raise part: 120 - 100 = 20
        self.assertEqual(self.mock_player_state.last_action, f"raise_all_in_to_{raise_to_amount_total}")

        self.assertIn(f"User {self.user_id} raise_all_in_s to {raise_to_amount_total}", result["message"])
        self.mock_db_session.commit.assert_called_once()


if __name__ == '__main__':
    unittest.main()
