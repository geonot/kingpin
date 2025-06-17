import unittest
from unittest.mock import patch, MagicMock, call
import secrets # To mock choices if needed
import json # Added for json.dumps in helper

from casino_be.models import db # Import db directly from models
# Import ALL models to ensure db.create_all() knows about them
from casino_be.models import (
    User, Slot, GameSession, SlotSpin, Transaction, SlotSymbol,
    BonusCode, UserBonus, BlackjackTable, BlackjackHand, BlackjackAction,
    SpacecrashGame, SpacecrashBet, PokerTable, PokerHand, PokerPlayerState,
    PlinkoDropLog, RouletteGame, TokenBlacklist,
    BaccaratTable, BaccaratHand, BaccaratAction,
    CrystalSeed, PlayerGarden, CrystalFlower, CrystalCodexEntry
)
from casino_be.utils.spin_handler import handle_spin # Target function
# from casino_be.utils.slot_builder import SLOT_CONFIG_BASE_PATH # To see where load_game_config looks - Removed as it does not exist

# Default configuration values that can be overridden by specific tests
BASE_GAME_CONFIG = {
    "game": {
        "slot_id": 1,
        "name": "Test Slot",
        "short_name": "test_slot1",
        "layout": {
            "rows": 3,
            "columns": 5,
            "paylines": [
                {"id": "line_1", "coords": [[1,0],[1,1],[1,2],[1,3],[1,4]]} # Middle row
            ]
        },
        "symbols": [
            {"id": 1, "name": "SymbolA", "asset": "symA.png", "value_multipliers": {"3": 10, "4": 20, "5": 50}, "weight": 10},
            {"id": 2, "name": "SymbolB", "asset": "symB.png", "value_multipliers": {"3": 5, "4": 10, "5": 20}, "weight": 20},
            {"id": 3, "name": "SymbolC", "asset": "symC.png", "value_multipliers": {"3": 2, "4": 4, "5": 8}, "weight": 30},
            {"id": 4, "name": "Scatter", "asset": "scatter.png", "payouts": {"3": 5, "4": 10, "5": 20}, "weight": 5}, # Scatter
            {"id": 5, "name": "Wild", "asset": "wild.png", "weight": 3} # Wild
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

from casino_be.tests.test_api import BaseTestCase # Import BaseTestCase

from casino_be.app import create_app # Ensure create_app is imported
from casino_be.config import TestingConfig # Ensure TestingConfig is imported

class TestSpinHandler(BaseTestCase): # Inherit from BaseTestCase
    def setUp(self):
        # Overriding BaseTestCase.setUp for specialized in-memory DB handling for this test suite
        self.app = create_app(TestingConfig)
        self.app_context = self.app.app_context()
        self.app_context.push()
        # Assuming db is initialized within create_app or globally and associated with self.app
        with self.app.app_context(): # Ensure create_all is within context
            db.create_all()
        self.client = self.app.test_client()

        # Original TestSpinHandler specific setup continues below
        # User, Slot, GameSession creation will now use self.app and its db session
        self.user = User(username='testuser', email='test@example.com', password='password')
        self.user.balance = 100000 # Sats
        db.session.add(self.user)

        self.slot = Slot(
            id=1, # Explicitly setting ID
            name="Test Slot",
            short_name="test_slot1",
            num_rows=3,
            num_columns=5,
            num_symbols=5,
            asset_directory="/test_assets/",
            is_active=True,
            rtp=95.0,
            volatility="Medium",
            is_cascading=False,
            win_multipliers=None
        )
        db.session.add(self.slot)
        db.session.flush() # Flush to get self.slot.id before creating SlotSymbol

        base_symbols_config = BASE_GAME_CONFIG.get("game", {}).get("symbols", [])
        for symbol_conf in base_symbols_config:
            slot_symbol = SlotSymbol(
                slot_id=self.slot.id, # Use the flushed ID
                symbol_internal_id=symbol_conf["id"],
                name=symbol_conf["name"],
                img_link=symbol_conf.get("asset", f"default_asset_{symbol_conf['id']}.png"),
                value_multiplier=0.0,
            )
            db.session.add(slot_symbol)
            # self.slot.symbols.append(slot_symbol) # SQLAlchemy handles this via backref if configured

        self.game_session = GameSession(user_id=self.user.id, slot_id=self.slot.id, game_type='slot')
        db.session.add(self.game_session)
        db.session.commit() # Commit all setup data

        # Re-fetch self.slot to ensure relationships like 'symbols' are properly loaded for the test session.
        self.slot = db.session.query(Slot).get(self.slot.id)
        # Explicitly load the symbols to ensure the collection is populated
        # _ = self.slot.symbols # Accessing it should trigger the load
        # A more robust way if the above doesn't work in all scenarios with mocks/sessions:
        self.slot.symbols = db.session.query(SlotSymbol).filter_by(slot_id=self.slot.id).all()


        # Patch load_game_config used by spin_handler
        self.mock_load_config = patch('casino_be.utils.spin_handler.load_game_config').start()
        self.mock_load_config.return_value = BASE_GAME_CONFIG # Default config

        self.mock_choices = patch('secrets.SystemRandom.choices').start()

        # Store the patcher for generate_spin_grid to manage it in specific tests
        self.patcher_generate_grid = patch('casino_be.utils.spin_handler.generate_spin_grid')
        self.mock_generate_grid = self.patcher_generate_grid.start()

    def tearDown(self):
        # Overriding BaseTestCase.tearDown for specialized in-memory DB handling
        # patch.stopall() will be called by the BaseTestCase.tearDown if we call super()
        # or if we explicitly call it here. It's important it runs after each test.
        patch.stopall() # Stop patches first
        with self.app.app_context(): # Ensure session operations and drop_all are within context
            db.session.remove()
            db.drop_all()
        self.app_context.pop()
        # No os.remove needed for in-memory DB

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
        # BASE_GAME_CONFIG payline is middle row: [[1,0],[1,1],[1,2],[1,3],[1,4]]
        # Symbol 1 (SymA) pays 10x for 3.
        winning_grid = [
            [2, 3, 1, 2, 3],  # Non-winning row
            [1, 1, 1, 2, 3],  # WINNING: SymA, SymA, SymA on middle row (payline)
            [3, 1, 2, 3, 1]   # Non-winning row
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
                "layout": { # Overriding layout to change paylines
                    **BASE_GAME_CONFIG["game"]["layout"],
                    "paylines": [{"id": "line_1", "coords": [[1,0],[1,1],[1,2]]}]
                }
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
        # choices(k=1) returns a list like [symbol_id].
        # Provide enough for two fills. First fill uses symbol 6 (expected to be non-winning).
        # _generate_weighted_random_symbols calls choices(..., k=num_to_replace) once per cascade fill.
        # For "fall_from_top", it's called per column needing symbols.
        # Initial win removes 3 symbols at (1,0), (1,1), (1,2).
        # Col 0: (0,0) falls to (1,0). grid[0,0] needs 1 symbol.
        # Col 1: (0,1) falls to (1,1). grid[0,1] needs 1 symbol.
        # Col 2: (0,2) falls to (1,2). grid[0,2] needs 1 symbol.
        # So, 3 calls to choices, each k=1, for the first cascade fill.
        # Second cascade fill (if it happens) would also be 3 calls, k=1.
        # Third cascade fill (if it happens due to min_win logic) would also be 3 calls, k=1.
        self.mock_choices.side_effect = [
            [6], [6], [6], # 1st cascade fill: col 0 gets 6, col 1 gets 6, col 2 gets 6. These should not form a win.
            [3], [3], [3], # 2nd cascade fill: col 0 gets 3, col 1 gets 3, col 2 gets 3. These should not form a win.
            [3], [3], [3]  # 3rd cascade fill (extra, just in case of unexpected win from ID 3)
        ]

        bet_amount = 100
        initial_balance = self.user.balance

        # Calculations:
        # Initial win: 3x SymbolB (id=2) on payline. SymbolB pays 5x for 3. Win = 100 * 5 = 500.
        # Cascade 1: Symbols [1,1,1] (SymbolA) fall into the payline. SymbolA (id=1) pays 10x for 3.
        #            Raw win from this cascade = 100 * 10 = 1000.
        #            Multiplier for 1st cascade (level_counter=1) is win_multipliers[0] = 2.
        #            Actual win from 1st cascade = 1000 * 2 = 2000.
        # Total after Cascade 1 = 5 (initial) + (10 * 2) = 25.
        # Cascade 2: Symbols [3,3,3] (SymbolC) fill the top row. They don't form a win on the defined payline. Cascade stops.
        # Expected total win = 25.
        # UPDATED EXPECTATION based on base_bet_unit = total_bet_sats (100)
        # Initial win (SymB, 5x): 100 * 5 = 500.
        # Cascade 1 (SymA, 10x, mult 2): 100 * 10 * 2 = 2000.
        # Total: 500 + 2000 = 2500.
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
                    {"id": 1, "name": "SymbolA", "asset": "symA.png", "value_multipliers": {"3": 10}, "weight": 10},
                    {"id": 2, "name": "SymbolB", "asset": "symB.png", "value_multipliers": {"3": 5}, "weight": 20},
                    {"id": 3, "name": "SymbolC", "asset": "symC.png", "value_multipliers": {"3": 2}, "weight": 30},
                    {"id": 6, "name": "SymbolDud", "asset": "symDud.png", "weight": 30} # Non-winning symbol
                ],
                "layout": { # Overriding layout to change paylines
                    **BASE_GAME_CONFIG["game"]["layout"],
                    "paylines": [{"id": "line_1", "coords": [[1,0],[1,1],[1,2]]}]
                }
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
        # _generate_weighted_random_symbols calls choices(..., k=num_to_replace) once per cascade fill.
        # num_to_replace is 3 for the first cascade.
        # num_to_replace is 3 for the second cascade.
        # The mock should provide a list of symbols for each call to _generate_weighted_random_symbols
        self.mock_choices.side_effect = [
            [1, 1, 1], # Call 1 to choices(k=3) returns this list for 1st cascade.
            [6, 6, 6], # Call 2 to choices(k=3) returns this list for 2nd cascade.
            [6, 6, 6]  # Call 3 to choices(k=3) returns this list for 3rd cascade (if it happens).
        ]

        bet_amount = 100
        initial_balance = self.user.balance

        # Calculations:
        # Initial win: 3x SymbolB (id=2). Pays 5x. Win = 100 * 5 = 500.
        # Cascade 1: [1,1,1] (SymbolA) replace [2,2,2]. SymbolA pays 10x for 3.
        #            Raw win = 100 * 10 = 1000.
        #            Multiplier for 1st cascade is 2. Actual win = 1000 * 2 = 2000.
        # Total after Cascade 1 = 5 (initial) + (10 * 2) = 25.
        # Cascade 2: [6,6,6] (SymbolDud) replace [1,1,1]. No win.
        # UPDATED EXPECTATION based on base_bet_unit = total_bet_sats (100)
        # Initial win (SymB, 5x): 100 * 5 = 500.
        # Cascade 1 (SymA, 10x, mult 2): 100 * 10 * 2 = 2000.
        # Total: 500 + 2000 = 2500.
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
        # Provide enough for a potential second fill if logic attempts it.
        # _generate_weighted_random_symbols calls choices(..., k=num_to_replace) once per cascade fill.
        # Assuming 4 symbols are removed and replaced in the first cascade.
        # Col 0 needs 2 symbols, Col 1 needs 2, Col 2 needs 2 (if fall_from_top and specific removals)
        # Based on analysis: (0,0), (1,0) removed from Col 0 -> k=2
        # (2,1) removed from Col 1. (0,1) and (1,1) fall. grid[0,1] needs 1, grid[2,1] needs 1. This is complex.
        # Let's assume the previous analysis was: Col 0 needs 2, Col 1 needs 1, Col 2 needs 1 for a total of 4.
        # If (0,0), (1,0), (2,1), (2,2) are removed.
        # Col 0: (0,0), (1,0) are empty. k=2.
        # Col 1: (2,1) is empty. (0,1) falls to (1,1). (1,1) falls to (2,1). grid[0,1] needs 1. k=1.
        # Col 2: (2,2) is empty. (0,2) falls to (1,2). (1,2) falls to (2,2). grid[0,2] needs 1. k=1.
        # Total calls: one for k=2, one for k=1, one for k=1.
        # Making them all non-winning (e.g. symbol 3)
        self.mock_choices.side_effect = [
            [3, 3],    # For Col 0 (k=2)
            [3],       # For Col 1 (k=1, filling new grid[0,1])
            [3],       # For Col 2 (k=1, filling new grid[0,2])
            # Add more if further cascades are expected by the test logic.
            [3, 3], [3], [3] # Just in case of a second cascade round.
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
                    {"id": 3, "name": "SymbolC", "asset": "symC.png", "value_multipliers": {"3": 2}, "weight": 30},
                    {"id": 6, "name": "SymbolDud", "asset": "symDud.png", "weight": 30} # Non-winning symbol
                ],
                "layout": { # Overriding layout to change paylines
                    **BASE_GAME_CONFIG["game"]["layout"],
                    "paylines": [{"id": "line_1", "coords": [[0,0],[0,1],[0,2]]}]
                }
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
        # _generate_weighted_random_symbols calls choices(..., k=num_to_replace) once per cascade fill.
        # Each cascade replaces 3 symbols.
        self.mock_choices.side_effect = [
            # Cascade 1: Replace [1,1,1] with [2,2,2] (SymbolB) -> Wins
            [2, 2, 2],
            # Cascade 2: Replace [2,2,2] with [1,1,1] (SymbolA) -> Wins again
            [1, 1, 1],
            # Cascade 3: Replace [1,1,1] with [6,6,6] (SymbolDud) -> No Win
            [6, 6, 6],
            [6, 6, 6] # Extra, just in case
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


    # ---- New Cluster Pays with Wilds Tests ----

    def helper_configure_cluster_game(self, min_match, cluster_payouts_sym1, cluster_payouts_sym2=None,
                                      is_cascading=False, cascade_type=None, win_multipliers=None):
        """Helper to configure game for cluster tests."""
        symbols = [
            {"id": 1, "name": "SymbolA", "asset": "symA.png", "cluster_payouts": cluster_payouts_sym1, "weight": 10.0},
            {"id": 2, "name": "SymbolB", "asset": "symB.png", "cluster_payouts": cluster_payouts_sym2 if cluster_payouts_sym2 else {}, "weight": 20.0},
            {"id": 3, "name": "SymbolC", "asset": "symC.png", "weight": 30.0}, # Non-cluster symbol for variety
            {"id": 4, "name": "Scatter", "asset": "scatter.png", "scatter_payouts": {"3": 5}, "weight": 5.0}, # SCATTER_SYMBOL_ID
            {"id": 5, "name": "Wild", "asset": "wild.png", "weight": 3.0} # WILD_SYMBOL_ID
        ]

        current_config = {
            "game": {
                "slot_id": self.slot.id,
                "name": "Cluster Test Slot",
                "short_name": self.slot.short_name,
                "layout": {"rows": 3, "columns": 5}, # Adjust if tests need different grid sizes
                "symbols": symbols,
                "paylines": [], # Focus on cluster wins
                "wild_symbol_id": 5,
                "scatter_symbol_id": 4,
                "min_symbols_to_match": min_match,
                "is_cascading": is_cascading,
                "cascade_type": cascade_type if is_cascading else None,
                "win_multipliers": win_multipliers if is_cascading else [],
                "bonus_features": {},
                "reel": {"symbolSize": { "width": 100, "height": 100 }}
            }
        }
        self.mock_load_config.return_value = current_config
        self.slot.is_cascading = is_cascading
        self.slot.cascade_type = cascade_type
        self.slot.min_symbols_to_match = min_match
        # Ensure win_multipliers is stored as a JSON string in the model if that's how it's expected
        self.slot.win_multipliers = json.dumps(win_multipliers) if win_multipliers else "[]"
        db.session.commit()


    def test_cluster_win_no_wilds_no_cascade(self):
        min_match = 4
        payouts_sym1 = {"4": 10.0} # 10x for 4 SymbolA
        self.helper_configure_cluster_game(min_match=min_match, cluster_payouts_sym1=payouts_sym1)

        # Grid: 4 SymbolA (id=1)
        test_grid = [
            [1, 1, 2, 3, 2],
            [1, 1, 3, 2, 3],
            [3, 2, 3, 4, 3] # Changed Wild (5) to non-winning SymbolC (3) to ensure no wilds
        ]
        self.mock_generate_grid.return_value = test_grid
        bet_amount = 100
        expected_win = 100 * 10.0 # 1000

        result = handle_spin(self.user, self.slot, self.game_session, bet_amount)
        self.assertEqual(result['win_amount_sats'], expected_win)
        self.assertTrue(any(wl['type'] == 'cluster' and wl['symbol_id'] == 1 and wl['count'] == 4 for wl in result['winning_lines']))

    def test_cluster_win_one_wild_no_cascade(self):
        min_match = 5
        payouts_sym1 = {"5": 15.0} # 15x for 5 SymbolA
        self.helper_configure_cluster_game(min_match=min_match, cluster_payouts_sym1=payouts_sym1)

        # Grid: 4 SymbolA (id=1), 1 Wild (id=5)
        test_grid = [
            [1, 1, 2, 3, 2],
            [1, 1, 3, 2, 3],
            [5, 2, 3, 4, 3] # Wild at (2,0)
        ]
        self.mock_generate_grid.return_value = test_grid
        bet_amount = 100
        expected_win = 100 * 15.0 # 1500

        result = handle_spin(self.user, self.slot, self.game_session, bet_amount)
        self.assertEqual(result['win_amount_sats'], expected_win)
        winning_line_info = next((wl for wl in result['winning_lines'] if wl['type'] == 'cluster' and wl['symbol_id'] == 1), None)
        self.assertIsNotNone(winning_line_info)
        self.assertEqual(winning_line_info['count'], 5) # Effective count
        # Check if wild position is included
        self.assertTrue(any(pos == [2,0] for pos in winning_line_info['positions']))
        # Check if SymbolA positions are included
        self.assertTrue(any(pos == [0,0] for pos in winning_line_info['positions']))

    def test_cluster_win_multiple_wilds_no_cascade(self):
        min_match = 5
        payouts_sym1 = {"5": 15.0}
        self.helper_configure_cluster_game(min_match=min_match, cluster_payouts_sym1=payouts_sym1)

        # Grid: 3 SymbolA (id=1), 2 Wilds (id=5)
        test_grid = [
            [1, 1, 2, 3, 5], # Wild at (0,4)
            [1, 5, 3, 2, 3], # Wild at (1,1)
            [3, 2, 3, 4, 3]
        ]
        self.mock_generate_grid.return_value = test_grid
        bet_amount = 100
        expected_win = 100 * 15.0 # 1500

        result = handle_spin(self.user, self.slot, self.game_session, bet_amount)
        self.assertEqual(result['win_amount_sats'], expected_win)
        winning_line_info = next((wl for wl in result['winning_lines'] if wl['type'] == 'cluster' and wl['symbol_id'] == 1), None)
        self.assertIsNotNone(winning_line_info)
        self.assertEqual(winning_line_info['count'], 5)
        self.assertTrue(any(pos == [0,4] for pos in winning_line_info['positions']))
        self.assertTrue(any(pos == [1,1] for pos in winning_line_info['positions']))

    def test_cluster_win_wilds_contribute_to_multiple_types_no_cascade(self):
        min_match = 5
        payouts_sym1 = {"5": 10.0} # 10x for 5 SymbolA
        payouts_sym2 = {"5": 20.0} # 20x for 5 SymbolB
        self.helper_configure_cluster_game(min_match=min_match, cluster_payouts_sym1=payouts_sym1, cluster_payouts_sym2=payouts_sym2)

        # Grid: 4 SymbolA (id=1), 4 SymbolB (id=2), 1 Wild (id=5)
        test_grid = [
            [1, 1, 1, 1, 2],
            [2, 2, 2, 2, 3],
            [5, 3, 3, 4, 3] # Wild at (2,0)
        ]
        self.mock_generate_grid.return_value = test_grid
        bet_amount = 100
        expected_win_sym1 = 100 * 10.0 # 1000
        expected_win_sym2 = 100 * 20.0 # 2000
        expected_total_win = expected_win_sym1 + expected_win_sym2 # 3000

        result = handle_spin(self.user, self.slot, self.game_session, bet_amount)
        self.assertEqual(result['win_amount_sats'], expected_total_win)

        win_for_sym1 = next((wl for wl in result['winning_lines'] if wl['symbol_id'] == 1 and wl['type'] == 'cluster'), None)
        win_for_sym2 = next((wl for wl in result['winning_lines'] if wl['symbol_id'] == 2 and wl['type'] == 'cluster'), None)

        self.assertIsNotNone(win_for_sym1)
        self.assertEqual(win_for_sym1['count'], 5)
        self.assertEqual(win_for_sym1['win_amount_sats'], expected_win_sym1)
        self.assertTrue(any(pos == [2,0] for pos in win_for_sym1['positions'])) # Wild included

        self.assertIsNotNone(win_for_sym2)
        self.assertEqual(win_for_sym2['count'], 6) # Effective count is 5 literal + 1 wild
        self.assertEqual(win_for_sym2['win_amount_sats'], expected_win_sym2)
        self.assertTrue(any(pos == [2,0] for pos in win_for_sym2['positions'])) # Wild included

    def test_cluster_no_win_insufficient_symbols_with_wilds(self):
        min_match = 5
        payouts_sym1 = {"5": 10.0}
        self.helper_configure_cluster_game(min_match=min_match, cluster_payouts_sym1=payouts_sym1)

        # Grid: 1 SymbolA (id=1), 3 Wilds (id=5). Total effective = 4. min_match = 5.
        test_grid = [
            [1, 5, 2, 3, 5],
            [3, 5, 3, 2, 3],
            [4, 2, 3, 4, 3]
        ]
        self.mock_generate_grid.return_value = test_grid
        bet_amount = 100
        expected_win = 0

        result = handle_spin(self.user, self.slot, self.game_session, bet_amount)
        self.assertEqual(result['win_amount_sats'], expected_win)

    def test_cluster_win_with_wilds_and_cascade(self):
        min_match = 4
        payouts_sym1 = {"4": 10.0} # 10x for 4 SymbolA
        self.helper_configure_cluster_game(min_match=min_match, cluster_payouts_sym1=payouts_sym1,
                                           is_cascading=True, cascade_type="fall_from_top", win_multipliers=[2.0])

        # Grid: 4 SymbolA (id=1), 0 Wilds for the initial win part.
        # Payout for 4 SymA is 10x. Expected win 1000.
        initial_grid = [
            [1, 1, 2, 3, 4], # Row 0
            [1, 1, 3, 2, 3], # Row 1
            [2, 3, 4, 2, 6]  # Row 2: Changed symbol 5 (Wild) to 2 to ensure no wilds in initial grid
        ]
        self.mock_generate_grid.return_value = initial_grid

        # Mock cascade fill: assume 4 new non-winning symbols (e.g., id 3)
        # This needs to provide enough side_effects for all symbols that are filled.
        # If 4 symbols are removed, and cascade is fall_from_top, it's complex.
        # Let's simplify: assume mock_choices is called once per empty cell to be filled from top.
        # (0,0), (0,1), (1,0), (1,1) are removed.
        # Col 0: (0,0) removed. (1,0) removed. (2,0) is 2.
        # After fall: grid[2,0] becomes 2. grid[1,0] needs fill. grid[0,0] needs fill.
        # Col 1: (0,1) removed. (1,1) removed. (2,1) is 3.
        # After fall: grid[2,1] becomes 3. grid[1,1] needs fill. grid[0,1] needs fill.
        # Mock cascade fill: 4 symbols (1,1,1,1) removed from (0,0),(0,1),(1,0),(1,1)
        # Needs 4 new symbols for the top positions in first two columns if "fall_from_top"
        # Using a non-winning symbol (e.g. 6)
        # _generate_weighted_random_symbols calls choices(..., k=num_to_replace) once per cascade fill (per column for fall_from_top).
        # Initial win removes 4 symbols at (0,0),(0,1),(1,0),(1,1).
        # Cascade 1, "fall_from_top":
        # Col 0: (0,0) & (1,0) are empty. empty_slots_in_col = 2. Call _generate_weighted_random_symbols(k=2).
        # Col 1: (0,1) & (1,1) are empty. empty_slots_in_col = 2. Call _generate_weighted_random_symbols(k=2).
        # Col 2: (untouched)
        # Col 3: (untouched)
        # Col 4: (untouched)
        # So, for the first cascade fill, expect two calls to choices, each with k=2.
        # Using symbol ID 3 which is "OtherSym" and should not form a cluster win.
        # Provide enough for two full cascade fill rounds to prevent StopIteration.
        # Round 1:
        # Col 0 (k=2) -> [3,3]
        # Col 1 (k=2) -> [3,3]
        # Round 2 (ifเกิด):
        # Col 0 (k=2) -> [3,3]
        # Col 1 (k=2) -> [3,3]
        self.mock_choices.side_effect = [
            [3, 3], [3, 3],  # For first cascade fill (Col 0, Col 1)
            [3, 3], [3, 3]   # For a potential second cascade fill (Col 0, Col 1)
        ]

        bet_amount = 100
        initial_balance = self.user.balance
        expected_win_initial = 100 * 10.0 # 1000 (no cascade multiplier on initial win)
        # Assume no further wins from cascade for simplicity in this test.
        expected_total_win = expected_win_initial

        result = handle_spin(self.user, self.slot, self.game_session, bet_amount)

        self.assertEqual(result['win_amount_sats'], expected_total_win)
        self.assertEqual(self.user.balance, initial_balance - bet_amount + expected_total_win)

        winning_line_info = next((wl for wl in result['winning_lines'] if wl['type'] == 'cluster' and wl['symbol_id'] == 1), None)
        self.assertIsNotNone(winning_line_info)
        self.assertEqual(winning_line_info['count'], 4) # 3xA + 1xW

        # Check that the SlotSpin record reflects the initial grid and total win
        slot_spin_record = SlotSpin.query.filter_by(game_session_id=self.game_session.id).first()
        self.assertIsNotNone(slot_spin_record)
        self.assertEqual(slot_spin_record.win_amount, expected_total_win)
        self.assertEqual(slot_spin_record.spin_result, initial_grid) # spin_result should be initial grid
        self.assertEqual(slot_spin_record.current_multiplier_level, 0) # Since only initial win, no *successful* cascade win.

        # Check transactions
        transactions = Transaction.query.order_by(Transaction.id.asc()).all()
        self.assertEqual(len(transactions), 2) # Wager and Win
        self.assertEqual(transactions[0].amount, -bet_amount)
        self.assertEqual(transactions[1].amount, expected_total_win)

    # TODO: Add more complex cascade tests involving wilds, e.g.,
    # - Wilds contribute to an initial cluster, are removed.
    # - New symbols fall, and remaining/new wilds contribute to a *new* cluster win (possibly different symbol type).
    # - This would involve more complex mocking of `self.mock_choices.side_effect`.

    def test_reel_strip_logic_produces_valid_grid(self):
        # 1. Configure BASE_GAME_CONFIG for reel_strips
        reel_strip_config = {
            "game": {
                **BASE_GAME_CONFIG["game"],
                "layout": {
                    "rows": 3,
                    "columns": 3, # Simpler for this test
                    "paylines": [{"id": "line_1", "coords": [[0,0],[0,1],[0,2]]}] # A simple payline
                },
                "symbols": [ # Ensure all symbols on strips are defined here
                    {"id": 1, "name": "SymbolA", "asset": "symA.png", "weight": 10},
                    {"id": 2, "name": "SymbolB", "asset": "symB.png", "weight": 20},
                    {"id": 3, "name": "SymbolC", "asset": "symC.png", "weight": 30},
                    {"id": 10, "name": "StripOnly1", "asset": "so1.png", "weight": 1},
                    {"id": 11, "name": "StripOnly2", "asset": "so2.png", "weight": 1},
                    {"id": 12, "name": "StripOnly3", "asset": "so3.png", "weight": 1},
                ],
                "reel_strips": [
                    [1, 10, 2, 11, 3, 12],  # Reel 0
                    [2, 11, 3, 12, 1, 10],  # Reel 1
                    [3, 12, 1, 10, 2, 11]   # Reel 2
                ],
                "wild_symbol_id": None, # No wilds for simplicity here
                "scatter_symbol_id": None, # No scatters for simplicity
            }
        }
        self.mock_load_config.return_value = reel_strip_config

        # Ensure slot model matches config rows/cols for generate_spin_grid's internal logic
        self.slot.num_rows = reel_strip_config["game"]["layout"]["rows"]
        self.slot.num_columns = reel_strip_config["game"]["layout"]["columns"]
        db.session.commit()

        # 2. Un-mock generate_spin_grid for this test. We want to test its actual reel strip logic.
        #    We might need to mock secrets.SystemRandom().randrange if we want deterministic start_index.
        #    For now, let's test if it produces a valid grid based on strips.
        self.patcher_generate_grid.stop() # Stop the mock for this specific test

        # Mock randrange to control the start_index for each reel
        mock_randrange_patcher = patch('secrets.SystemRandom.randrange')
        mock_randrange = mock_randrange_patcher.start()
        mock_randrange.side_effect = [0, 1, 2] # start_index for col 0, col 1, col 2

        bet_amount = 100
        result = handle_spin(self.user, self.slot, self.game_session, bet_amount)

        # 3. Assertions
        spin_grid = result['spin_result']
        self.assertIsNotNone(spin_grid)
        self.assertEqual(len(spin_grid), reel_strip_config["game"]["layout"]["rows"])
        self.assertEqual(len(spin_grid[0]), reel_strip_config["game"]["layout"]["columns"])

        config_symbols_map = {s['id']: s for s in reel_strip_config["game"]["symbols"]}
        all_possible_strip_symbols = set()
        for strip in reel_strip_config["game"]["reel_strips"]:
            for sym_id in strip:
                all_possible_strip_symbols.add(sym_id)

        for r_idx, row in enumerate(spin_grid):
            for c_idx, symbol_id in enumerate(row):
                self.assertIn(symbol_id, all_possible_strip_symbols, f"Symbol {symbol_id} at [{r_idx}][{c_idx}] not in any reel strip.")
                self.assertIn(symbol_id, config_symbols_map.keys(), f"Symbol {symbol_id} at [{r_idx}][{c_idx}] not in config symbols.")

        # Expected grid based on randrange side_effect [0,1,2] and rows=3
        # Reel 0 (strip [1, 10, 2, 11, 3, 12]), start_index 0: [1, 10, 2]
        # Reel 1 (strip [2, 11, 3, 12, 1, 10]), start_index 1: [11, 3, 12]
        # Reel 2 (strip [3, 12, 1, 10, 2, 11]), start_index 2: [1, 10, 2]
        expected_grid = [
            [1, 11, 1],
            [10, 3, 10],
            [2, 12, 2]
        ]
        self.assertEqual(spin_grid, expected_grid, "Generated grid does not match expected from reel strips and mocked randrange.")

        # Stop the local patcher for randrange and restart the class-level patcher
        mock_randrange_patcher.stop()
        self.patcher_generate_grid.start() # Ensure it's mocked again for other tests


    def test_multiple_payline_wins_simultaneously(self):
        multi_payline_config = {
            "game": {
                **BASE_GAME_CONFIG["game"],
                "layout": {
                    "rows": 3,
                    "columns": 3,
                    "paylines": [
                        {"id": "line_top", "coords": [[0,0],[0,1],[0,2]]},    # Top row
                        {"id": "line_middle", "coords": [[1,0],[1,1],[1,2]]} # Middle row
                    ]
                },
                "symbols": [ # Symbol 1 pays 10x for 3, Symbol 2 pays 5x for 3
                    {"id": 1, "name": "SymbolA", "asset": "symA.png", "value_multipliers": {"3": 10}, "weight": 10},
                    {"id": 2, "name": "SymbolB", "asset": "symB.png", "value_multipliers": {"3": 5}, "weight": 20},
                    {"id": 3, "name": "SymbolC", "asset": "symC.png", "weight": 30},
                ],
                 "wild_symbol_id": None,
            }
        }
        self.mock_load_config.return_value = multi_payline_config

        # Grid: Top row wins with 3xA (id=1), Middle row wins with 3xB (id=2)
        test_grid = [
            [1, 1, 1], # Win for SymbolA (10x)
            [2, 2, 2], # Win for SymbolB (5x)
            [3, 3, 3]
        ]
        self.mock_generate_grid.return_value = test_grid

        bet_amount = 100 # Assume bet_per_line is total_bet / num_paylines.
                        # For this test, calculate_win uses base_bet_unit = total_bet / 100.
                        # Let's assume total_bet is applied per line for multiplier for simplicity in test expectation.
                        # SymbolA win = 100 * 10 = 1000
                        # SymbolB win = 100 * 5 = 500
                        # Total win = 1500. (This matches current calculate_win logic where base_bet_unit is used)

        # Recalculate based on current calculate_win logic:
        # base_bet_unit = total_bet_sats (100)
        # SymA win: 100 * 10 = 1000.
        # SymB win: 100 * 5 = 500.
        # Total win = 1000 + 500 = 1500.
        expected_win_sym_a = 1000
        expected_win_sym_b = 500
        expected_total_win = expected_win_sym_a + expected_win_sym_b


        result = handle_spin(self.user, self.slot, self.game_session, bet_amount)

        self.assertEqual(result['win_amount_sats'], expected_total_win)
        self.assertEqual(len(result['winning_lines']), 2)

        line_top_win = next((line for line in result['winning_lines'] if line['line_id'] == "line_top"), None)
        line_middle_win = next((line for line in result['winning_lines'] if line['line_id'] == "line_middle"), None)

        self.assertIsNotNone(line_top_win)
        self.assertEqual(line_top_win['symbol_id'], 1)
        self.assertEqual(line_top_win['win_amount_sats'], expected_win_sym_a)

        self.assertIsNotNone(line_middle_win)
        self.assertEqual(line_middle_win['symbol_id'], 2)
        self.assertEqual(line_middle_win['win_amount_sats'], expected_win_sym_b)

    def test_bonus_active_spin_no_bet_deduction_and_multiplier(self):
        self.game_session.bonus_active = True
        self.game_session.bonus_spins_remaining = 1
        self.game_session.bonus_multiplier = 2.0
        db.session.commit()

        # Config for a simple win
        bonus_win_config = {
            "game": {
                **BASE_GAME_CONFIG["game"],
                "layout": {"rows": 3, "columns": 3, "paylines": [{"id": "line_1", "coords": [[0,0],[0,1],[0,2]]}]},
                "symbols": [{"id": 1, "name": "SymbolA", "asset": "symA.png", "value_multipliers": {"3": 10}, "weight": 10}],
                "wild_symbol_id": None,
            }
        }
        self.mock_load_config.return_value = bonus_win_config

        # Grid for a win
        winning_grid = [[1, 1, 1], [2, 2, 2], [3, 3, 3]]
        self.mock_generate_grid.return_value = winning_grid

        initial_balance = self.user.balance
        bet_amount = 100 # This bet amount should not be deducted

        # Raw win: SymA (id=1) 3 times. Multiplier 10. base_bet_unit = total_bet_sats (100). Raw win = 100 * 10 = 1000.
        expected_raw_win = 1000 # This is the raw win before bonus multiplier
        expected_multiplied_win = int(expected_raw_win * self.game_session.bonus_multiplier) # 1000 * 2.0 = 2000

        result = handle_spin(self.user, self.slot, self.game_session, bet_amount)

        self.assertEqual(result['win_amount_sats'], expected_multiplied_win)
        # Balance should be initial_balance + multiplied_win (no bet deduction)
        self.assertEqual(self.user.balance, initial_balance + expected_multiplied_win)
        self.assertEqual(self.game_session.bonus_spins_remaining, 0)
        self.assertFalse(self.game_session.bonus_active) # Bonus ends as spins are 0

        # Verify no wager transaction was created for this bonus spin
        wager_tx = Transaction.query.filter_by(user_id=self.user.id, transaction_type='wager').first()
        self.assertIsNone(wager_tx)

        win_tx = Transaction.query.filter_by(user_id=self.user.id, transaction_type='win').first()
        self.assertIsNotNone(win_tx)
        self.assertEqual(win_tx.amount, expected_multiplied_win)


    def test_handle_spin_with_invalid_config_structure(self):
        malformed_config = {
            "game": {
                "name": "Test Slot",
                "short_name": "test_slot1",
                # Missing "layout" deliberately
                "symbols": "this should be a list" # Invalid type
            }
        }
        self.mock_load_config.return_value = malformed_config

        bet_amount = 100
        # Expecting error due to game.symbols being a string instead of a list
        with self.assertRaisesRegex(ValueError, "Config error for slot 'test_slot1': game.symbols must be a list."):
            handle_spin(self.user, self.slot, self.game_session, bet_amount)

        # Test another malformed case
        malformed_config_2 = {
            "game": {
                "name": "Test Slot",
                "short_name": "test_slot1",
                "layout": { "rows": 3, "columns": 5, "paylines": "not a list"}, # Invalid paylines type
                 "symbols": [BASE_GAME_CONFIG["game"]["symbols"][0]]
            }
        }
        self.mock_load_config.return_value = malformed_config_2
        with self.assertRaisesRegex(ValueError, "Config error for slot 'test_slot1': game.layout.paylines must be a list."):
            handle_spin(self.user, self.slot, self.game_session, bet_amount)


if __name__ == '__main__':
    unittest.main()
