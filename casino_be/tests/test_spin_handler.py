import unittest
from unittest.mock import patch, MagicMock, call
import secrets # To mock choices if needed

from casino_be.app import create_app, db
from casino_be.models import User, Slot, GameSession, SlotSpin, Transaction
from casino_be.utils.spin_handler import handle_spin # Target function
from casino_be.utils.slot_builder import SLOT_CONFIG_BASE_PATH # To see where load_game_config looks

# Default configuration values that can be overridden by specific tests
BASE_GAME_CONFIG = {
    "game": {
        "slot_id": 1,
        "name": "Test Slot",
        "short_name": "test_slot1",
        "layout": {"rows": 3, "columns": 5},
        "symbols": [
            {"id": 1, "name": "SymbolA", "asset": "symA.png", "value_multipliers": {"3": 10, "4": 20, "5": 50}, "weight": 10},
            {"id": 2, "name": "SymbolB", "asset": "symB.png", "value_multipliers": {"3": 5, "4": 10, "5": 20}, "weight": 20},
            {"id": 3, "name": "SymbolC", "asset": "symC.png", "value_multipliers": {"3": 2, "4": 4, "5": 8}, "weight": 30},
            {"id": 4, "name": "Scatter", "asset": "scatter.png", "payouts": {"3": 5, "4": 10, "5": 20}, "weight": 5}, # Scatter
            {"id": 5, "name": "Wild", "asset": "wild.png", "weight": 3} # Wild
        ],
        "paylines": [
            {"id": "line_1", "positions": [[1,0],[1,1],[1,2],[1,3],[1,4]]} # Middle row
        ],
        "payouts": [], # General payouts, might be used for cluster later
        "wild_symbol_id": 5,
        "scatter_symbol_id": 4,
        "bonus_features": {},
        "is_cascading": False,
        "cascade_type": None,
        "win_multipliers": [],
        "min_symbols_to_match": None,
        "reel": {"symbolSize": { "width": 100, "height": 100 }} # Added for handle_cascade_fill
    }
}

class TestSpinHandler(unittest.TestCase):
    def setUp(self):
        self.app = create_app(config_name='testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        self.user = User(username='testuser', email='test@example.com', password='password')
        self.user.balance = 100000 # Sats
        db.session.add(self.user)

        self.slot = Slot(
            id=1,
            name="Test Slot",
            short_name="test_slot1", # Must match what load_game_config expects
            num_rows=3,
            num_columns=5,
            is_active=True,
            rtp=95.0,
            volatility="Medium",
            # Cascading fields will be set by mock_game_config typically
            is_cascading=False,
            win_multipliers=None
        )
        # Add some default symbols to slot.symbols relationship if generate_spin_grid relies on it
        # For now, assume config_symbols_map is primary source for symbol properties in spin_handler
        db.session.add(self.slot)
        db.session.commit()

        self.game_session = GameSession(user_id=self.user.id, slot_id=self.slot.id, game_type='slot')
        db.session.add(self.game_session)
        db.session.commit()

        # Patch load_game_config used by spin_handler
        self.mock_load_config = patch('casino_be.utils.spin_handler.load_game_config').start()
        self.mock_load_config.return_value = BASE_GAME_CONFIG # Default config

        # Patch random symbol generation for deterministic tests
        # This targets 'secrets.SystemRandom().choices' as used in generate_spin_grid and handle_cascade_fill
        self.mock_choices = patch('secrets.SystemRandom.choices').start()

        # Patch generate_spin_grid to control initial grid
        self.mock_generate_grid = patch('casino_be.utils.spin_handler.generate_spin_grid').start()


    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()
        patch.stopall() # Stops all active patches

    def test_no_win_scenario(self):
        # Configure a non-winning grid
        no_win_grid = [
            [1, 2, 3, 1, 2],
            [2, 3, 1, 2, 3],
            [3, 1, 2, 3, 1]
        ]
        self.mock_generate_grid.return_value = no_win_grid

        bet_amount = 100
        initial_balance = self.user.balance

        result = handle_spin(self.user, self.slot, self.game_session, bet_amount)

        self.assertEqual(result['win_amount_sats'], 0)
        self.assertEqual(self.user.balance, initial_balance - bet_amount)

        slot_spin_record = SlotSpin.query.filter_by(game_session_id=self.game_session.id).first()
        self.assertIsNotNone(slot_spin_record)
        self.assertEqual(slot_spin_record.win_amount, 0)
        self.assertEqual(slot_spin_record.bet_amount, bet_amount)
        self.assertEqual(slot_spin_record.current_multiplier_level, 0) # No cascade, no multiplier
        self.assertEqual(slot_spin_record.spin_result, no_win_grid)

        transactions = Transaction.query.filter_by(user_id=self.user.id).order_by(Transaction.id.asc()).all()
        self.assertEqual(len(transactions), 1)
        self.assertEqual(transactions[0].amount, -bet_amount)
        self.assertEqual(transactions[0].transaction_type, 'wager')

    def test_win_on_non_cascading_slot(self):
        # Configure a winning grid
        winning_grid = [
            [1, 1, 1, 2, 3], # Symbol 1 (value 10 for 3) on payline
            [2, 3, 1, 2, 3],
            [3, 1, 2, 3, 1]
        ]
        self.mock_generate_grid.return_value = winning_grid
        self.slot.is_cascading = False # Ensure slot model reflects this

        # Ensure BASE_GAME_CONFIG reflects non-cascading for this test
        current_config = {**BASE_GAME_CONFIG,
            "game": {**BASE_GAME_CONFIG["game"], "is_cascading": False}
        }
        self.mock_load_config.return_value = current_config

        bet_amount = 100 # Assume 1 payline, so bet_per_line is 100
        initial_balance = self.user.balance

        # Symbol 1 pays 10x for 3 matches.
        # Expected win = bet_per_line * multiplier = 100 * 10 = 1000
        expected_win = 1000

        result = handle_spin(self.user, self.slot, self.game_session, bet_amount)

        self.assertEqual(result['win_amount_sats'], expected_win)
        self.assertEqual(self.user.balance, initial_balance - bet_amount + expected_win)

        slot_spin_record = SlotSpin.query.filter_by(game_session_id=self.game_session.id).first()
        self.assertIsNotNone(slot_spin_record)
        self.assertEqual(slot_spin_record.win_amount, expected_win)
        self.assertEqual(slot_spin_record.current_multiplier_level, 0) # Not cascading
        self.assertEqual(slot_spin_record.spin_result, winning_grid)

        transactions = Transaction.query.filter_by(user_id=self.user.id).order_by(Transaction.id.asc()).all()
        self.assertEqual(len(transactions), 2) # Wager and Win
        self.assertEqual(transactions[0].amount, -bet_amount)
        self.assertEqual(transactions[1].amount, expected_win)

    def test_basic_cascade_fall_from_top(self):
        # 1. Configure for "fall_from_top" cascading
        self.slot.is_cascading = True
        self.slot.cascade_type = "fall_from_top"
        # Tiered multipliers: 1st cascade x2, 2nd cascade x3
        self.slot.win_multipliers = "[2, 3]" # Stored as JSON string in model

        test_config = {
            "game": {
                **BASE_GAME_CONFIG["game"],
                "is_cascading": True,
                "cascade_type": "fall_from_top",
                "win_multipliers": [2, 3], # e.g. 1st cascade win x2, 2nd x3
                "symbols": [ # Ensure symbols have weights for cascade fill if not mocking fill directly
                    {"id": 1, "name": "SymbolA", "asset": "symA.png", "value_multipliers": {"3": 10}, "weight": 10},
                    {"id": 2, "name": "SymbolB", "asset": "symB.png", "value_multipliers": {"3": 5}, "weight": 20},
                    {"id": 3, "name": "SymbolC", "asset": "symC.png", "value_multipliers": {"3": 2}, "weight": 30},
                    {"id": 5, "name": "Wild", "asset": "wild.png", "weight": 3}
                ],
                 "paylines": [{"id": "line_1", "positions": [[1,0],[1,1],[1,2]]}] # Simplified 3-symbol payline
            }
        }
        self.mock_load_config.return_value = test_config

        # 2. Control symbol generation
        initial_grid_cascade = [
            [1, 1, 1, 2, 3], # This line will fall and win again (SymbolA, id=1)
            [2, 2, 2, 3, 1], # Initial Win here: 3xB (id=2) on payline [[1,0],[1,1],[1,2]]
            [3, 3, 3, 1, 2]
        ]
        self.mock_generate_grid.return_value = initial_grid_cascade

        # When the 3 '2's (SymbolB) are removed from row 1 (index 1),
        # the 3 '1's (SymbolA) from row 0 (index 0) will fall into place on row 1.
        # Then, row 0 becomes empty and needs new symbols.
        # Let these new symbols for row 0, cols 0,1,2 be [3,3,3] (SymbolC, no win on the payline).
        # self.mock_choices is used by handle_cascade_fill. It's called for each new symbol.
        # Since 3 symbols are needed to fill the top row (cols 0, 1, 2 after fall).
        self.mock_choices.side_effect = [
            [[3]], # New symbol for grid[0][0]
            [[3]], # New symbol for grid[0][1]
            [[3]], # New symbol for grid[0][2]
        ]

        bet_amount = 100
        initial_balance = self.user.balance

        # Calculations:
        # Initial win: 3x SymbolB (id=2) on payline. SymbolB pays 5x for 3. Win = 100 * 5 = 500.
        # Cascade 1: Symbols [1,1,1] (SymbolA) fall into the payline. SymbolA (id=1) pays 10x for 3.
        #            Raw win from this cascade = 100 * 10 = 1000.
        #            Multiplier for 1st cascade (level_counter=1) is win_multipliers[0] = 2.
        #            Actual win from 1st cascade = 1000 * 2 = 2000.
        # Total after Cascade 1 = 500 (initial) + 2000 = 2500.
        # Cascade 2: Symbols [3,3,3] (SymbolC) fill the top row. They don't form a win on the defined payline. Cascade stops.
        # Expected total win = 2500.
        expected_total_win = 2500
        expected_multiplier_level = 1 # Max cascade_level_counter that resulted in a win was 1.

        result = handle_spin(self.user, self.slot, self.game_session, bet_amount)

        self.assertEqual(result['win_amount_sats'], expected_total_win)
        self.assertEqual(self.user.balance, initial_balance - bet_amount + expected_total_win)

        slot_spin_record = SlotSpin.query.filter_by(game_session_id=self.game_session.id).first()
        self.assertIsNotNone(slot_spin_record)
        self.assertEqual(slot_spin_record.win_amount, expected_total_win)
        self.assertEqual(slot_spin_record.current_multiplier_level, expected_multiplier_level)
        self.assertEqual(slot_spin_record.spin_result, initial_grid_cascade)

        transactions = Transaction.query.order_by(Transaction.id.asc()).all()
        self.assertEqual(len(transactions), 2)
        self.assertEqual(transactions[0].user_id, self.user.id)
        self.assertEqual(transactions[0].amount, -bet_amount)
        self.assertEqual(transactions[1].user_id, self.user.id)
        self.assertEqual(transactions[1].amount, expected_total_win)

    def test_basic_cascade_replace_in_place(self):
        self.slot.is_cascading = True
        self.slot.cascade_type = "replace_in_place"
        self.slot.win_multipliers = "[2, 3]"

        test_config_replace = {
            "game": {
                **BASE_GAME_CONFIG["game"],
                "is_cascading": True,
                "cascade_type": "replace_in_place",
                "win_multipliers": [2, 3],
                "symbols": [
                    {"id": 1, "name": "SymbolA", "asset": "symA.png", "value_multipliers": {"3": 10}, "weight": 10}, # Wins
                    {"id": 2, "name": "SymbolB", "asset": "symB.png", "value_multipliers": {"3": 5}, "weight": 20},  # Initial win
                    {"id": 3, "name": "SymbolC", "asset": "symC.png", "value_multipliers": {"3": 2}, "weight": 30},  # No win
                ],
                "paylines": [{"id": "line_1", "positions": [[1,0],[1,1],[1,2]]}]
            }
        }
        self.mock_load_config.return_value = test_config_replace

        initial_grid_cascade_replace = [
            [3, 3, 3, 2, 3],
            [2, 2, 2, 3, 1], # Initial Win here: 3xB (id=2) on payline [[1,0],[1,1],[1,2]]
            [1, 1, 3, 1, 2]
        ]
        self.mock_generate_grid.return_value = initial_grid_cascade_replace

        # Symbols for "replace_in_place":
        # The winning symbols [2,2,2] at positions (1,0), (1,1), (1,2) will be replaced.
        # Let the new symbols be [1,1,1] (SymbolA) to cause a cascade win.
        # Then, for the next cascade, let the new symbols be [3,3,3] (SymbolC) to stop.
        self.mock_choices.side_effect = [
            [[1]], # New symbol for grid[1][0] (replaces a '2')
            [[1]], # New symbol for grid[1][1] (replaces a '2')
            [[1]], # New symbol for grid[1][2] (replaces a '2')
            # Second cascade fill (after [1,1,1] win)
            [[3]], # New symbol for grid[1][0]
            [[3]], # New symbol for grid[1][1]
            [[3]], # New symbol for grid[1][2]
        ]

        bet_amount = 100
        initial_balance = self.user.balance

        # Calculations:
        # Initial win: 3x SymbolB (id=2). Pays 5x. Win = 100 * 5 = 500.
        # Cascade 1: [1,1,1] (SymbolA) replace [2,2,2]. SymbolA pays 10x for 3.
        #            Raw win = 100 * 10 = 1000.
        #            Multiplier for 1st cascade is 2. Actual win = 1000 * 2 = 2000.
        # Total after Cascade 1 = 500 + 2000 = 2500.
        # Cascade 2: [3,3,3] (SymbolC) replace [1,1,1]. SymbolC is not on payline or doesn't make a line. No win.
        expected_total_win = 2500
        expected_multiplier_level = 1 # Max cascade_level_counter resulting in a win.

        result = handle_spin(self.user, self.slot, self.game_session, bet_amount)

        self.assertEqual(result['win_amount_sats'], expected_total_win)
        self.assertEqual(self.user.balance, initial_balance - bet_amount + expected_total_win)

        slot_spin_record = SlotSpin.query.filter_by(game_session_id=self.game_session.id).first()
        self.assertIsNotNone(slot_spin_record)
        self.assertEqual(slot_spin_record.win_amount, expected_total_win)
        self.assertEqual(slot_spin_record.current_multiplier_level, expected_multiplier_level)
        self.assertEqual(slot_spin_record.spin_result, initial_grid_cascade_replace)

        transactions = Transaction.query.order_by(Transaction.id.asc()).all()
        self.assertEqual(len(transactions), 2)
        self.assertEqual(transactions[0].amount, -bet_amount)
        self.assertEqual(transactions[1].amount, expected_total_win)

    def test_match_n_cluster_wins_with_cascading(self):
        self.slot.is_cascading = True
        self.slot.cascade_type = "fall_from_top" # Or replace_in_place, choice affects fill mock
        self.slot.min_symbols_to_match = 4 # Example: needs 4 matching symbols for a cluster win
        self.slot.win_multipliers = "[2]" # Single cascade multiplier for simplicity

        test_config_cluster = {
            "game": {
                **BASE_GAME_CONFIG["game"],
                "is_cascading": True,
                "cascade_type": "fall_from_top",
                "win_multipliers": [2],
                "min_symbols_to_match": 4,
                "symbols": [
                    {"id": 1, "name": "ClusterSymA", "asset": "cA.png",
                     "cluster_payouts": {"4": 10, "5": 20}, "weight": 10}, # Pays 10x for 4 matches
                    {"id": 2, "name": "ClusterSymB", "asset": "cB.png",
                     "cluster_payouts": {"4": 5}, "weight": 20},
                    {"id": 3, "name": "OtherSym", "asset": "other.png", "weight": 30},
                ],
                "paylines": [] # Explicitly no paylines for this test, focus on cluster
            }
        }
        self.mock_load_config.return_value = test_config_cluster

        # Initial grid: 4x Symbol 1 (ClusterSymA)
        initial_grid_cluster = [
            [1, 2, 3, 2],
            [1, 1, 2, 3],
            [3, 3, 1, 1]  # Four 1s, scattered. calculate_win counts all.
        ]
        # This grid has five 1s. Let's adjust to exactly four for simpler first test.
        initial_grid_cluster = [
            [1, 2, 3, 2], # Row 0
            [1, 3, 2, 3], # Row 1
            [3, 1, 1, 3]  # Row 2. Total four 1s at (0,0), (1,0), (2,1), (2,2)
        ]
        self.mock_generate_grid.return_value = initial_grid_cluster

        # Symbols for cascade (fall_from_top):
        # The four '1's are removed. Their positions: (0,0), (1,0), (2,1), (2,2)
        # Column 0: grid[0,0] removed. Nothing above to fall. Needs 1 new symbol. Let it be 2.
        # Column 1: grid[2,1] removed. grid[1,1](3) falls to (2,1). grid[0,1](2) falls to (1,1). Needs 1 new at (0,1). Let it be 3.
        # Column 2: grid[2,2] removed. grid[1,2](2) falls to (2,2). grid[0,2](3) falls to (1,2). Needs 1 new at (0,2). Let it be 3.
        # This fill logic is complex to mock precisely without visualizing.
        # Let's simplify: assume 4 new symbols are needed and make them non-winning.
        self.mock_choices.side_effect = [
            [[2]], [[3]], [[3]], [[2]] # Fill the 4 emptied spots (or top spots) with non-winning sequence
        ]

        bet_amount = 100
        initial_balance = self.user.balance

        # Calculations:
        # Initial win: 4x Symbol 1 (ClusterSymA). Pays 10x for 4 matches (from cluster_payouts).
        #            Win = total_bet_sats * cluster_multiplier = 100 * 10 = 1000.
        # Cascade 1: Assume the fill [2,3,3,2] does not create a new cluster of >=4 identical symbols.
        #            No further wins.
        # Expected total win = 1000.
        expected_total_win = 1000
        expected_multiplier_level = 0 # No successful cascades that themselves won.

        result = handle_spin(self.user, self.slot, self.game_session, bet_amount)

        self.assertEqual(result['win_amount_sats'], expected_total_win)
        self.assertEqual(self.user.balance, initial_balance - bet_amount + expected_total_win)

        slot_spin_record = SlotSpin.query.filter_by(game_session_id=self.game_session.id).first()
        self.assertIsNotNone(slot_spin_record)
        self.assertEqual(slot_spin_record.win_amount, expected_total_win)
        self.assertEqual(slot_spin_record.current_multiplier_level, expected_multiplier_level)
        self.assertEqual(slot_spin_record.spin_result, initial_grid_cluster)

        # Verify that winning_lines_data includes the cluster win
        self.assertTrue(any(wl['type'] == 'cluster' for wl in result['winning_lines']))
        self.assertTrue(any(wl['symbol_id'] == 1 and wl['count'] == 4 for wl in result['winning_lines']))

    def test_multiplier_progression_and_cap(self):
        self.slot.is_cascading = True
        self.slot.cascade_type = "replace_in_place"
        self.slot.win_multipliers = "[2, 3]" # Multipliers for 1st, 2nd+ cascade wins

        test_config_multi = {
            "game": {
                **BASE_GAME_CONFIG["game"],
                "is_cascading": True,
                "cascade_type": "replace_in_place",
                "win_multipliers": [2, 3], # Cap at 3x for 2nd cascade onwards
                "symbols": [
                    {"id": 1, "name": "SymbolA", "asset": "symA.png", "value_multipliers": {"3": 10}, "weight": 10},
                    {"id": 2, "name": "SymbolB", "asset": "symB.png", "value_multipliers": {"3": 5}, "weight": 20},
                    {"id": 3, "name": "SymbolC", "asset": "symC.png", "value_multipliers": {"3": 2}, "weight": 30}, # Non-winning
                ],
                "paylines": [{"id": "line_1", "positions": [[0,0],[0,1],[0,2]]}] # Top row payline
            }
        }
        self.mock_load_config.return_value = test_config_multi

        # Initial grid: 3xA (id=1) for a win
        initial_grid_multi = [
            [1, 1, 1, 2, 3], # Win: 3xA (id=1)
            [2, 3, 2, 3, 1],
            [3, 1, 3, 1, 2]
        ]
        self.mock_generate_grid.return_value = initial_grid_multi

        # Mock choices for cascades (replace_in_place at [0,0],[0,1],[0,2])
        self.mock_choices.side_effect = [
            # Cascade 1: Replace [1,1,1] with [2,2,2] (SymbolB) -> Wins
            [[2]], [[2]], [[2]],
            # Cascade 2: Replace [2,2,2] with [1,1,1] (SymbolA) -> Wins again
            [[1]], [[1]], [[1]],
            # Cascade 3: Replace [1,1,1] with [3,3,3] (SymbolC) -> No Win
            [[3]], [[3]], [[3]],
        ]

        bet_amount = 100
        initial_balance = self.user.balance

        # Calculations:
        # Initial win: 3x SymbolA (id=1). Pays 10x. Raw win = 100 * 10 = 1000.
        # Total = 1000.

        # Cascade 1: [2,2,2] (SymbolB) replaces initial [1,1,1]. SymbolB pays 5x.
        #            Raw win = 100 * 5 = 500.
        #            Multiplier for 1st cascade (level_counter=1) is win_multipliers[0]=2.
        #            Actual win from 1st cascade = 500 * 2 = 1000.
        # Total = 1000 + 1000 = 2000.
        # max_multiplier_level_achieved = 1 (as cascade_level_counter = 1)

        # Cascade 2: [1,1,1] (SymbolA) replaces [2,2,2]. SymbolA pays 10x.
        #            Raw win = 100 * 10 = 1000.
        #            Multiplier for 2nd cascade (level_counter=2) is win_multipliers[1]=3.
        #            Actual win from 2nd cascade = 1000 * 3 = 3000.
        # Total = 2000 + 3000 = 5000.
        # max_multiplier_level_achieved = 2 (as cascade_level_counter = 2)

        # Cascade 3: [3,3,3] (SymbolC) replaces [1,1,1]. No win. Loop terminates.
        #            cascade_level_counter would have been 3, but this cascade does not win.

        expected_total_win = 5000
        expected_multiplier_level = 2 # Highest cascade_level_counter that resulted in a win.

        result = handle_spin(self.user, self.slot, self.game_session, bet_amount)

        self.assertEqual(result['win_amount_sats'], expected_total_win)
        self.assertEqual(self.user.balance, initial_balance - bet_amount + expected_total_win)

        slot_spin_record = SlotSpin.query.filter_by(game_session_id=self.game_session.id).first()
        self.assertIsNotNone(slot_spin_record)
        self.assertEqual(slot_spin_record.win_amount, expected_total_win)
        self.assertEqual(slot_spin_record.current_multiplier_level, expected_multiplier_level)
        self.assertEqual(slot_spin_record.spin_result, initial_grid_multi)


if __name__ == '__main__':
    unittest.main()
