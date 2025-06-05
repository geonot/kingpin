import unittest
from unittest.mock import patch, MagicMock, ANY
from decimal import Decimal

from casino_be.utils.poker_helper import _distribute_pot
from casino_be.models import User, PokerTable, PokerHand, PokerPlayerState, Transaction, db

# Helper to create a mock session (can be shared or defined per test file)
def create_mock_session():
    mock_session = MagicMock(spec=db.session)
    mock_session.query.return_value.filter_by.return_value.first.return_value = None
    mock_session.query.return_value.get.return_value = None
    mock_session.add = MagicMock()
    mock_session.commit = MagicMock()
    mock_session.rollback = MagicMock()
    return mock_session

class TestDistributePot(unittest.TestCase):

    def setUp(self):
        self.mock_db_session = create_mock_session()
        self.db_session_patch = patch('casino_be.utils.poker_helper.db.session', self.mock_db_session)
        self.mock_db_session_instance = self.db_session_patch.start()

        self.table_id = 1
        self.hand_id = 1

        self.mock_poker_table = PokerTable(
            id=self.table_id,
            rake_percentage=Decimal("0.05"), # 5% rake
            max_rake_sats=300 # Max rake of 300 satoshis
        )
        self.mock_db_session.query(PokerTable).get.return_value = self.mock_poker_table

        # Mock users that will be returned by session.query(User).get(id)
        self.mock_users = {}

    def tearDown(self):
        self.db_session_patch.stop()

    def _setup_player(self, user_id, username, stack, total_invested, hole_cards):
        user = User(id=user_id, username=username)
        self.mock_users[user_id] = user # Store for later retrieval by mock_query_user_get

        player_state = PokerPlayerState(
            user_id=user_id,
            table_id=self.table_id,
            stack_sats=stack,
            total_invested_this_hand=total_invested,
            hole_cards=hole_cards,
            is_active_in_hand=True, # Assumed for showdown players
            user=user # Associate user object
        )
        return player_state

    def mock_query_user_get(self, user_id_key):
        return self.mock_users.get(user_id_key)


    @patch('casino_be.utils.poker_helper._determine_winning_hand')
    @patch('casino_be.utils.poker_helper.Transaction')
    def test_single_winner_main_pot_no_rake_cap_hit(self, MockTransaction, mock_determine_winning_hand):
        self.mock_poker_table.rake_percentage = Decimal("0.10") # 10%
        self.mock_poker_table.max_rake_sats = 500

        player1 = self._setup_player(user_id=1, username="Alice", stack=1000, total_invested=200, hole_cards=["AH", "KH"])
        player2 = self._setup_player(user_id=2, username="Bob", stack=1000, total_invested=200, hole_cards=["QC", "JC"])

        showdown_players = [player1, player2]
        poker_hand = PokerHand(
            id=self.hand_id, table_id=self.table_id, pot_size_sats=400, board_cards=["2D", "3D", "4D", "5S", "6S"],
            player_street_investments={}, winners=[] # Ensure winners is empty list initially
        )

        # Mocking User query within _distribute_pot if winner_user_obj is fetched again.
        # It's better if player_state_obj.user is already loaded.
        self.mock_db_session.query(User).get.side_effect = self.mock_query_user_get

        # Player1 wins the only pot
        mock_determine_winning_hand.return_value = [
            {"user_id": 1, "winning_hand": "Straight", "best_five_cards": ["AH", "KH", "2D", "3D", "4D"]}
        ]

        _distribute_pot(poker_hand, showdown_players)

        expected_rake = 400 * 0.10 # 40
        self.assertEqual(poker_hand.rake_sats, expected_rake)
        expected_pot_distributed = 400 - expected_rake # 360

        self.assertEqual(player1.stack_sats, 1000 + expected_pot_distributed)
        self.assertEqual(player2.stack_sats, 1000) # Bob lost

        self.assertEqual(len(poker_hand.winners), 1)
        self.assertEqual(poker_hand.winners[0]['user_id'], 1)
        self.assertEqual(poker_hand.winners[0]['amount_won'], expected_pot_distributed)

        MockTransaction.assert_called_once()
        call_args = MockTransaction.call_args[1]
        self.assertEqual(call_args['user_id'], 1)
        self.assertEqual(call_args['amount'], expected_pot_distributed)
        self.assertEqual(call_args['transaction_type'], 'poker_win')

        self.mock_db_session.commit.assert_called_once()
        self.assertEqual(poker_hand.status, 'completed')

    @patch('casino_be.utils.poker_helper._determine_winning_hand')
    @patch('casino_be.utils.poker_helper.Transaction')
    def test_split_pot_two_winners_main_pot(self, MockTransaction, mock_determine_winning_hand):
        self.mock_poker_table.rake_percentage = Decimal("0.00") # No rake for simplicity

        player1 = self._setup_player(user_id=1, username="Alice", stack=1000, total_invested=200, hole_cards=["AH", "KH"])
        player2 = self._setup_player(user_id=2, username="Bob", stack=1000, total_invested=200, hole_cards=["AD", "KD"])
        showdown_players = [player1, player2]
        poker_hand = PokerHand(id=self.hand_id, table_id=self.table_id, pot_size_sats=400, board_cards=["2S", "3H", "4C", "5S", "6D"], winners=[])

        self.mock_db_session.query(User).get.side_effect = self.mock_query_user_get

        mock_determine_winning_hand.return_value = [
            {"user_id": 1, "winning_hand": "Straight", "best_five_cards": []},
            {"user_id": 2, "winning_hand": "Straight", "best_five_cards": []}
        ] # Split pot

        _distribute_pot(poker_hand, showdown_players)

        self.assertEqual(poker_hand.rake_sats, 0)
        pot_per_winner = 400 // 2 # 200

        self.assertEqual(player1.stack_sats, 1000 + pot_per_winner)
        self.assertEqual(player2.stack_sats, 1000 + pot_per_winner)

        self.assertEqual(len(poker_hand.winners), 2)
        self.assertEqual(MockTransaction.call_count, 2)
        # Could add more assertions for transaction details if needed

        self.mock_db_session.commit.assert_called_once()

    @patch('casino_be.utils.poker_helper._determine_winning_hand')
    @patch('casino_be.utils.poker_helper.Transaction')
    def test_one_main_pot_one_side_pot(self, MockTransaction, mock_determine_winning_hand):
        self.mock_poker_table.rake_percentage = Decimal("0.10") # 10% rake
        self.mock_poker_table.max_rake_sats = 10 # Max rake 10

        # P1 all-in for 100. P2 calls 100 and has more. P3 calls 100 and has more.
        # Total pot = 300. Rake = 10. Distributable = 290.
        # Main pot for P1, P2, P3: P1 puts in 100. P2 matches 100. P3 matches 100. Total 300.
        # This setup is for _distribute_pot. Assume pot_size_sats is already calculated.
        # Let's say:
        # P1 invested 100 (all-in)
        # P2 invested 200
        # P3 invested 200
        # Total pot_size_sats on PokerHand = 100 + 200 + 200 = 500
        # Rake = 10. Distributable = 490.

        player1 = self._setup_player(user_id=1, username="P1_AllIn", stack=0, total_invested=100, hole_cards=["AS", "KS"]) # All-in
        player2 = self._setup_player(user_id=2, username="P2_Cover", stack=1000, total_invested=200, hole_cards=["QS", "JS"])
        player3 = self._setup_player(user_id=3, username="P3_Cover", stack=1000, total_invested=200, hole_cards=["TS", "9S"])
        showdown_players = [player1, player2, player3]

        poker_hand = PokerHand(id=self.hand_id, table_id=self.table_id, pot_size_sats=500, board_cards=["2H", "3H", "4H", "5D", "7D"], winners=[])
        self.mock_db_session.query(User).get.side_effect = self.mock_query_user_get

        # P1 wins main pot. P2 wins side pot against P3.
        def side_effect_determine_winner(*args, **kwargs):
            player_map = args[0]
            if 1 in player_map and 2 in player_map and 3 in player_map: # Main pot
                return [{"user_id": 1, "winning_hand": "Flush", "best_five_cards": []}]
            elif 2 in player_map and 3 in player_map: # Side pot P2 vs P3
                return [{"user_id": 2, "winning_hand": "Pair of 7s", "best_five_cards": []}]
            return []
        mock_determine_winning_hand.side_effect = side_effect_determine_winner

        _distribute_pot(poker_hand, showdown_players)

        self.assertEqual(poker_hand.rake_sats, 10) # Max rake
        distributable_overall = 500 - 10 # 490

        # Expected pots:
        # Main Pot (cap 100): P1, P2, P3 contribute 100 each. Value = 300. Eligible: {1,2,3}. Winner P1.
        # Side Pot 1 (cap 200, layer is 100-200): P2, P3 contribute 100 each. Value = 200. Eligible: {2,3}. Winner P2.
        # Total value from investments = 300 + 200 = 500.
        # This should be scaled/deducted from distributable_overall (490) by the logic.
        # The current logic in _distribute_pot:
        # Layer 1 (cap 100): value_of_this_pot_layer = 100 * 3 = 300. amount_for_this_pot = min(300, 490) = 300. P1 wins 300.
        # Remaining distributable = 490 - 300 = 190.
        # Layer 2 (cap 200, processed_investment_level=100): contribution_this_layer = 100.
        #   P2 adds min(100, 200-100)=100. P3 adds min(100, 200-100)=100.
        #   value_of_this_pot_layer = 100 * 2 = 200. amount_for_this_pot = min(200, 190) = 190. P2 wins 190.

        self.assertEqual(player1.stack_sats, 0 + 300) # P1 was all-in, won main pot
        self.assertEqual(player2.stack_sats, 1000 + 190) # P2 won side pot
        self.assertEqual(player3.stack_sats, 1000) # P3 lost both

        self.assertEqual(len(poker_hand.winners), 2)
        self.assertEqual(MockTransaction.call_count, 2)

        winner_p1 = next(w for w in poker_hand.winners if w['user_id'] == 1)
        winner_p2 = next(w for w in poker_hand.winners if w['user_id'] == 2)
        self.assertEqual(winner_p1['amount_won'], 300)
        self.assertEqual(winner_p2['amount_won'], 190)

        self.mock_db_session.commit.assert_called_once()


if __name__ == '__main__':
    unittest.main()
