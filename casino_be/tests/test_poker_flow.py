import unittest
from unittest.mock import patch, MagicMock, ANY
from datetime import datetime, timezone, timedelta

from casino_be.utils.poker_helper import _check_betting_round_completion, _advance_to_next_street, POKER_ACTION_TIMEOUT_SECONDS
from casino_be.models import User, PokerTable, PokerHand, PokerPlayerState, Transaction, db # Import db for session spec

# Helper to create a mock session
def create_mock_session():
    mock_session = MagicMock(spec=db.session) # Use db.session for spec
    mock_session.query.return_value.filter_by.return_value.first.return_value = None
    mock_session.query.return_value.get.return_value = None
    mock_session.add = MagicMock()
    mock_session.commit = MagicMock() # Action handlers commit, these helpers might not directly
    mock_session.rollback = MagicMock()
    return mock_session

class TestAdvanceToNextStreet(unittest.TestCase):
    def setUp(self):
        self.mock_db_session = create_mock_session()
        # Patch db.session for all tests in this class that use poker_helper functions
        self.db_session_patch = patch('casino_be.utils.poker_helper.db.session', self.mock_db_session)
        self.mock_db_session_instance = self.db_session_patch.start()

        self.hand_id = 1
        self.table_id = 1
        self.user_id_1 = 10
        self.user_id_2 = 11
        self.user_id_3 = 12 # Dealer

        self.mock_poker_table = PokerTable(id=self.table_id, big_blind=20, current_dealer_seat_id=3)
        self.player_state1 = PokerPlayerState(user_id=self.user_id_1, seat_id=1, stack_sats=1000, is_active_in_hand=True, table_id=self.table_id)
        self.player_state2 = PokerPlayerState(user_id=self.user_id_2, seat_id=2, stack_sats=1000, is_active_in_hand=True, table_id=self.table_id)
        self.player_state3_dealer = PokerPlayerState(user_id=self.user_id_3, seat_id=3, stack_sats=1000, is_active_in_hand=True, table_id=self.table_id) # Dealer

        self.mock_poker_table.player_states = [self.player_state1, self.player_state2, self.player_state3_dealer]


    def tearDown(self):
        self.db_session_patch.stop()

    @patch('casino_be.utils.poker_helper.deal_community_cards')
    def test_advance_from_preflop_to_flop(self, mock_deal_community_cards):
        poker_hand = PokerHand(
            id=self.hand_id, table_id=self.table_id, board_cards=[], deck_state=["AS", "KS", "QS", "JS", "TS"],
            status='preflop', hand_history=[], player_street_investments={'some_val': 1}, # Should be cleared
            current_bet_to_match=100, last_raiser_user_id=self.user_id_1, min_next_raise_amount=100 # Should be reset
        )
        poker_hand.table = self.mock_poker_table # Associate table
        self.mock_db_session.query(PokerHand).options.return_value.get.return_value = poker_hand

        mock_deal_community_cards.return_value = ["AH", "KH", "QH"] # Flop cards

        result = _advance_to_next_street(self.hand_id, self.mock_db_session_instance)

        self.assertEqual(result['status'], 'advanced_to_flop')
        self.assertEqual(poker_hand.status, 'flop')
        mock_deal_community_cards.assert_called_once_with(poker_hand, 'flop')
        self.assertEqual(len(poker_hand.board_cards), 3)
        self.assertEqual(poker_hand.current_bet_to_match, 0)
        self.assertEqual(poker_hand.min_next_raise_amount, self.mock_poker_table.big_blind)
        self.assertIsNone(poker_hand.last_raiser_user_id)
        self.assertEqual(poker_hand.player_street_investments, {})
        self.assertIsNotNone(poker_hand.current_turn_user_id) # Should be player left of dealer
        # Player 1 is seat 1, Player 2 is seat 2, Player 3 (dealer) is seat 3. Player 1 is first to act.
        self.assertEqual(poker_hand.current_turn_user_id, self.player_state1.user_id)
        self.assertIsNotNone(self.player_state1.time_to_act_ends)


    def test_advance_from_river_to_showdown(self):
        poker_hand = PokerHand(
            id=self.hand_id, table_id=self.table_id,
            board_cards=["AH", "KH", "QH", "JH", "TH"], # Full board
            status='river', hand_history=[]
        )
        poker_hand.table = self.mock_poker_table
        self.mock_db_session.query(PokerHand).options.return_value.get.return_value = poker_hand

        result = _advance_to_next_street(self.hand_id, self.mock_db_session_instance)

        self.assertEqual(result['status'], 'showdown_reached')
        self.assertEqual(poker_hand.status, 'showdown')
        self.assertIsNone(poker_hand.current_turn_user_id)


class TestCheckBettingRoundCompletion(unittest.TestCase):
    def setUp(self):
        self.mock_db_session = create_mock_session()
        self.db_session_patch = patch('casino_be.utils.poker_helper.db.session', self.mock_db_session)
        self.mock_db_session_instance = self.db_session_patch.start()

        self.hand_id = 1
        self.table_id = 1
        self.user_id_1, self.user_id_2, self.user_id_3 = 10, 11, 12

        self.mock_poker_table = PokerTable(id=self.table_id, big_blind=20, current_dealer_seat_id=3)
        self.p1_state = PokerPlayerState(user_id=self.user_id_1, seat_id=1, stack_sats=1000, is_active_in_hand=True, table_id=self.table_id, user=User(id=self.user_id_1, username="P1"))
        self.p2_state = PokerPlayerState(user_id=self.user_id_2, seat_id=2, stack_sats=1000, is_active_in_hand=True, table_id=self.table_id, user=User(id=self.user_id_2, username="P2"))
        self.p3_state = PokerPlayerState(user_id=self.user_id_3, seat_id=3, stack_sats=1000, is_active_in_hand=True, table_id=self.table_id, user=User(id=self.user_id_3, username="P3")) # Dealer
        self.mock_poker_table.player_states = [self.p1_state, self.p2_state, self.p3_state]

        self.mock_poker_hand = PokerHand(
            id=self.hand_id, table_id=self.table_id, status='flop', pot_size_sats=300,
            current_bet_to_match=100, player_street_investments={}, hand_history=[],
            last_raiser_user_id=None, current_turn_user_id=self.user_id_1
        )
        self.mock_poker_hand.table = self.mock_poker_table
        self.mock_db_session.query(PokerHand).options.return_value.get.return_value = self.mock_poker_hand
        self.mock_db_session.query(PokerPlayerState).filter_by.side_effect = self.get_player_state_mock

    def get_player_state_mock(self, user_id, table_id): # Simplified mock for specific test needs
        if user_id == self.user_id_1: return MagicMock(first=MagicMock(return_value=self.p1_state))
        if user_id == self.user_id_2: return MagicMock(first=MagicMock(return_value=self.p2_state))
        if user_id == self.user_id_3: return MagicMock(first=MagicMock(return_value=self.p3_state))
        return MagicMock(first=MagicMock(return_value=None))

    def tearDown(self):
        self.db_session_patch.stop()

    def test_hand_ends_by_folds(self):
        self.p2_state.is_active_in_hand = False # P2 folded
        self.p3_state.is_active_in_hand = False # P3 folded
        # P1 is the only one left active

        with patch('casino_be.utils.poker_helper.Transaction') as MockTransaction: # Ensure Transaction is properly mocked
            result = _check_betting_round_completion(self.hand_id, self.user_id_2, self.mock_db_session_instance) # P2 was last actor (e.g. folded)

        self.assertEqual(result['status'], 'hand_completed_by_folds')
        self.assertEqual(result['winner_user_id'], self.user_id_1)
        self.assertEqual(self.mock_poker_hand.status, 'completed')
        self.assertIsNotNone(self.mock_poker_hand.end_time)
        self.assertEqual(self.mock_poker_hand.winners[0]['user_id'], self.user_id_1)
        self.assertEqual(self.p1_state.stack_sats, 1000 + self.mock_poker_hand.pot_size_sats) # Pot awarded
        MockTransaction.assert_called_once()


    @patch('casino_be.utils.poker_helper._advance_to_next_street')
    def test_betting_round_complete_advance_street(self, mock_advance):
        # All active players have matched the current bet
        self.mock_poker_hand.player_street_investments = {
            str(self.user_id_1): 100, str(self.user_id_2): 100, str(self.user_id_3): 100
        }
        self.mock_poker_hand.current_bet_to_match = 100
        self.mock_poker_hand.last_raiser_user_id = self.user_id_1 # P1 made the bet

        # Last actor is P3 (dealer), who called. Action is now complete for this round.
        mock_advance.return_value = {"status": "advanced_to_turn", "next_to_act_user_id": self.user_id_1, "board_cards": ["AS","KS","QS","JS"]}

        result = _check_betting_round_completion(self.hand_id, self.user_id_3, self.mock_db_session_instance)

        mock_advance.assert_called_once_with(self.hand_id, self.mock_db_session_instance)
        self.assertEqual(result['status'], 'round_completed_advancing_street')

    def test_betting_continues_next_player(self):
        # P1 (current turn) just acted (e.g. checked or bet). P2 is next.
        self.mock_poker_hand.player_street_investments = {str(self.user_id_1): 0} # P1 checked
        self.mock_poker_hand.current_bet_to_match = 0
        self.mock_poker_hand.current_turn_user_id = self.user_id_1 # P1 was current turn

        # Last actor was P1. Next should be P2.
        result = _check_betting_round_completion(self.hand_id, self.user_id_1, self.mock_db_session_instance)

        self.assertEqual(result['status'], 'betting_continues')
        self.assertEqual(result['next_to_act_user_id'], self.user_id_2)
        self.assertEqual(self.mock_poker_hand.current_turn_user_id, self.user_id_2)
        self.assertIsNotNone(self.p2_state.time_to_act_ends)
        self.assertIsNone(self.p1_state.time_to_act_ends) # P1's timer should be cleared

    @patch('casino_be.utils.poker_helper._advance_to_next_street')
    def test_all_in_showdown_two_players_one_all_in(self, mock_advance):
        self.p1_state.stack_sats = 0 # P1 is all-in
        self.p1_state.total_invested_this_hand = 200 # P1's total investment
        self.mock_poker_hand.player_street_investments = {
            str(self.user_id_1): 100, # P1 all-in for 100 this street
            str(self.user_id_2): 100  # P2 called P1's all-in
        }
        self.mock_poker_hand.current_bet_to_match = 100
        self.p3_state.is_active_in_hand = False # P3 folded
        self.mock_poker_table.player_states = [self.p1_state, self.p2_state, self.p3_state] # Update table state

        # P2 was the last actor (called P1's all-in). Round is complete.
        # Since P1 is all-in and P2 called, and only two players active, it's time for showdown (after running cards).
        mock_advance.side_effect = [ # Simulate advancing through streets
            {"status": "advanced_to_turn", "hand_id": self.hand_id, "board_cards": ["AS","KS","QS","JS"], "next_to_act_user_id": None}, # no one to act
            {"status": "advanced_to_river", "hand_id": self.hand_id, "board_cards": ["AS","KS","QS","JS", "TS"], "next_to_act_user_id": None},
            {"status": "showdown_reached", "hand_id": self.hand_id, "board_cards": ["AS","KS","QS","JS", "TS"]}
        ]

        # When _advance_to_next_street is called, it will find no one to act if players are all-in
        # and poker_hand.status will eventually become 'showdown'.
        # Here, we simulate that the betting round is complete because P2 called P1's all-in.
        # The logic non_all_in_bettable_players should be <= 1.
        # P1 is all-in (stack 0). P2 has stack but has matched. So non_all_in_bettable_players (who still need to act on current bet) might be 0.

        result = _check_betting_round_completion(self.hand_id, self.user_id_2, self.mock_db_session_instance)

        self.assertEqual(result['status'], 'all_in_showdown')
        self.assertEqual(self.mock_poker_hand.status, 'showdown')
        self.assertIsNone(self.mock_poker_hand.current_turn_user_id)
        self.assertTrue(mock_advance.call_count >= 1) # Should try to advance until showdown


if __name__ == '__main__':
    unittest.main()
