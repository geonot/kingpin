import unittest
from unittest.mock import MagicMock, patch
import os
import json
from flask import Flask # Import Flask
from datetime import datetime, timezone # Import datetime and timezone

# It's common to need to adjust imports based on Python's path and module structure.
# Assuming 'casino_be' is the root package or is in PYTHONPATH.
from casino_be.utils.spin_handler_new import (
    handle_spin,
    generate_spin_grid,
    calculate_win,
    check_bonus_trigger,
    load_game_config,
    _validate_game_config,
    get_symbol_payout,
    handle_cascade_fill,
    _generate_weighted_random_symbols
)
# We will also need to mock database models and other dependencies.
# For now, let's define some placeholder mocks that can be expanded later.

# --- Mock Model Classes (copied from test_bonus_service.py for now) ---
class MockUser:
    def __init__(self, id, balance):
        self.id = id
        self.balance = balance

class MockSlot:
    def __init__(self, id, name, short_name, symbols=None):
        self.id = id
        self.name = name
        self.short_name = short_name
        # `symbols` in Slot model would typically be a relationship to SlotSymbol.
        # For testing spin_handler_new.py, this might be a list of mock SlotSymbol objects
        # or just a list of symbol IDs or configurations if that's what the functions expect.
        self.symbols = symbols if symbols is not None else []


class MockGameSession:
    def __init__(self, id, user_id, slot_id):
        self.id = id
        self.user_id = user_id
        self.slot_id = slot_id
        self.bonus_active = False
        self.bonus_spins_remaining = 0
        self.bonus_multiplier = 1.0
        self.num_spins = 0
        self.amount_wagered = 0
        self.amount_won = 0

class MockSlotSymbol:
    def __init__(self, symbol_internal_id, name="Test Symbol", img_link="test.png", value_multiplier=0.0, data=None):
        self.symbol_internal_id = symbol_internal_id
        self.name = name
        self.img_link = img_link
        self.value_multiplier = value_multiplier
        self.data = data if data is not None else {}

class MockBonusCode: # Added
    def __init__(self, id, code_id, bonus_type, subtype, amount=None, amount_sats=None,
                 wagering_requirement_multiplier=None, uses_remaining=None, is_active=True,
                 description=None):
        self.id = id
        self.code_id = code_id
        self.type = bonus_type
        self.subtype = subtype
        self.amount = amount
        self.amount_sats = amount_sats
        self.wagering_requirement_multiplier = wagering_requirement_multiplier
        self.uses_remaining = uses_remaining
        self.is_active = is_active
        self.description = description
        self.updated_at = None
        self.created_at = datetime.now(timezone.utc)


class MockUserBonus: # Added
    _next_id = 1
    def __init__(self, user_id, bonus_code_id, bonus_amount_awarded_sats,
                 wagering_requirement_sats, wagering_progress_sats=0,
                 is_active=True, is_completed=False, is_cancelled=False):
        self.id = MockUserBonus._next_id
        MockUserBonus._next_id += 1
        self.user_id = user_id
        self.bonus_code_id = bonus_code_id
        self.bonus_amount_awarded_sats = bonus_amount_awarded_sats
        self.wagering_requirement_sats = wagering_requirement_sats
        self.wagering_progress_sats = wagering_progress_sats
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

class MockTransaction: # Added
    _next_id = 1
    def __init__(self, user_id, amount, transaction_type, status='completed', details=None):
        self.id = MockTransaction._next_id
        MockTransaction._next_id += 1
        self.user_id = user_id
        self.amount = amount
        self.transaction_type = transaction_type
        self.status = status
        self.details = details if details is not None else {}
        self.created_at = datetime.now(timezone.utc)
        self.updated_at = None

    @classmethod
    def reset_id_counter(cls):
        cls._next_id = 1


# Example basic game config structure (can be expanded or loaded from a test file)
BASE_GAME_CONFIG = {
    "game": {
        "slot_id": 1,
        "name": "Test Slot",
        "short_name": "testslot",
        "asset_dir": "/testslot/",
        "layout": {"rows": 3, "columns": 5},
        "symbol_count": 3,
        "scatter_symbol_id": 3, # Assuming symbol ID 3 is scatter
        "wild_symbol_id": 2,    # Assuming symbol ID 2 is wild
        "symbols": [
            {"id": 1, "name": "Symbol A", "icon": "/testslot/s_a.png", "value": 1.0, "weight": 10.0, "value_multipliers": {"3": 1, "4": 2, "5": 5}},
            {"id": 2, "name": "Wild", "icon": "/testslot/s_wild.png", "value": None, "is_wild": True, "weight": 1.0},
            {"id": 3, "name": "Scatter", "icon": "/testslot/s_scatter.png", "value": None, "is_scatter": True, "weight": 1.0, "scatter_payouts": {"3": 5, "4": 10, "5": 25}}
        ],
        "layout": { # Ensure paylines is under layout for BASE_GAME_CONFIG as well
            "rows": 3,
            "columns": 5,
            "paylines": [
                {"id": 0, "coords": [[1,0],[1,1],[1,2],[1,3],[1,4]]} # Middle row
            ]
        },
        "bonus_features": {
            "free_spins": {
                "trigger_count": 3, # Min scatters to trigger
                "spins_awarded": 10,
                "multiplier": 2.0
            }
        },
        "is_cascading": False,
        "reel_strips": None # Default to weighted random for now
    }
}
# BASE_GAME_CONFIG['game']['symbols_map'] = {s['id']: s for s in BASE_GAME_CONFIG['game']['symbols']}
# symbols_map will be recreated correctly in setUp to ensure integer keys for the mock.

class TestSpinHandlerNew(unittest.TestCase):

    def setUp(self):
        # Create a Flask app context
        self.app = Flask(__name__)
        self.app_context = self.app.app_context()
        self.app_context.push()

        # Mock common dependencies
        self.mock_user = MockUser(id=1, balance=1000)
        self.mock_slot = MockSlot(id=1, name="Test Slot", short_name="testslot")
        self.mock_slot.symbols = [
            MockSlotSymbol(symbol_internal_id=1),
            MockSlotSymbol(symbol_internal_id=2),
            MockSlotSymbol(symbol_internal_id=3)
        ]
        self.mock_game_session = MockGameSession(id=1, user_id=self.mock_user.id, slot_id=self.mock_slot.id)

        self.patcher_db_session = patch('casino_be.utils.spin_handler_new.db.session')
        self.mock_db_session = self.patcher_db_session.start()

        # Now patch logger after app context is available
        self.patcher_logger = patch('casino_be.utils.spin_handler_new.current_app.logger')
        self.mock_logger = self.patcher_logger.start()

        self.patcher_load_config = patch('casino_be.utils.spin_handler_new.load_game_config')
        self.mock_load_config = self.patcher_load_config.start()

        # Prepare a clean config for each test.
        # The actual load_game_config in spin_handler_new.py constructs cfg_symbols_map
        # with integer keys: {s['id']: s for s in ...}.
        # We must ensure our mock returns a config where 'symbols_map' also has integer keys
        # if the functions being tested rely on load_game_config for this structure.
        temp_config = json.loads(json.dumps(BASE_GAME_CONFIG))
        # If BASE_GAME_CONFIG had a 'symbols_map' key that went through json.dumps/loads,
        # its keys might be strings. We rebuild it from 'symbols' list to ensure int keys.
        temp_config['game']['symbols_map'] = {s['id']: s for s in temp_config['game']['symbols']}
        self.mock_load_config.return_value = temp_config

        self.patcher_user_bonus_query = patch('casino_be.utils.spin_handler_new.UserBonus.query')
        self.mock_user_bonus_query = self.patcher_user_bonus_query.start()
        self.mock_user_bonus_query.filter_by.return_value.first.return_value = None

        MockUserBonus.reset_id_counter() # Reset for each test
        MockTransaction.reset_id_counter() # Reset for each test


    def tearDown(self):
        self.patcher_db_session.stop()
        self.patcher_logger.stop()
        self.patcher_load_config.stop()
        self.patcher_user_bonus_query.stop()

        # Pop the app context
        self.app_context.pop()

    def test_example_placeholder(self):
        self.assertEqual(1 + 1, 2)

    # test_load_game_config_success_primary_path has been removed as it was causing
    # issues with the class-level mock object self.mock_load_config by stopping
    # and restarting the patcher, potentially leading to different mock instances
    # being used across tests. A separate test class for load_game_config would be better.

    def test_validate_game_config_valid(self):
        try:
            _validate_game_config(json.loads(json.dumps(BASE_GAME_CONFIG)), "testslot")
        except ValueError:
            self.fail("_validate_game_config raised ValueError unexpectedly for valid config.")

    def test_validate_game_config_invalid_missing_game_key(self):
        invalid_config = {"some_other_key": {}}
        with self.assertRaisesRegex(ValueError, "game' key must be a dictionary"):
            _validate_game_config(invalid_config, "testslot")

    def test_validate_game_config_invalid_layout_rows(self):
        invalid_config = {
            "game": {"name": "Test", "short_name":"ts", "layout": {"rows": "invalid", "columns": 5}}
        }
        with self.assertRaisesRegex(ValueError, "game.layout.rows must be a positive integer"):
            _validate_game_config(invalid_config, "testslot")

    def test_generate_spin_grid_basic(self):
        rows, cols = 3, 5
        db_symbols_mock = [MockSlotSymbol(s_id) for s_id in [1,2,3]]
        # Use the config provided by the mock_load_config setup
        current_config = self.mock_load_config.return_value

        grid = generate_spin_grid(rows, cols, db_symbols_mock,
                                  current_config['game']['wild_symbol_id'],
                                  current_config['game']['scatter_symbol_id'],
                                  current_config['game']['symbols_map'])
        self.assertEqual(len(grid), rows)
        self.assertEqual(len(grid[0]), cols)
        for r in range(rows):
            for c in range(cols):
                self.assertIn(grid[r][c], [s['id'] for s in current_config['game']['symbols']])

    def test_generate_spin_grid_with_reel_strips(self):
        rows, cols = 3, 5
        db_symbols_mock = [MockSlotSymbol(s_id) for s_id in range(1, 6)]
        reel_strips_config = [
            [1,2,3,1,2], [2,3,4,2,3], [3,4,5,3,4], [4,5,1,4,5], [5,1,2,5,1]
        ]
        current_config = json.loads(json.dumps(BASE_GAME_CONFIG))
        current_config['game']['reel_strips'] = reel_strips_config # Add to config for this test

        with patch('secrets.SystemRandom.randrange', return_value=0) as mock_randrange:
            grid = generate_spin_grid(rows, cols, db_symbols_mock,
                                      current_config['game']['wild_symbol_id'],
                                      current_config['game']['scatter_symbol_id'],
                                      {s_id: {"id": s_id} for s_id in range(1,6)}, # Simplified map for this test
                                      reel_strips_config) # Pass directly as arg too

        self.assertEqual(len(grid), rows)
        self.assertEqual(len(grid[0]), cols)
        self.assertEqual(mock_randrange.call_count, cols)
        for c_idx in range(cols):
            for r_idx in range(rows):
                self.assertEqual(grid[r_idx][c_idx], reel_strips_config[c_idx][r_idx])

    def test_get_symbol_payout_normal_symbol(self):
        current_config = self.mock_load_config.return_value
        payout = get_symbol_payout(symbol_id=1, count=3, config_symbols_map=current_config['game']['symbols_map'], is_scatter=False)
        self.assertEqual(payout, 1.0)

    def test_get_symbol_payout_scatter_symbol(self):
        current_config = self.mock_load_config.return_value
        payout = get_symbol_payout(symbol_id=3, count=3, config_symbols_map=current_config['game']['symbols_map'], is_scatter=True)
        self.assertEqual(payout, 5.0)

    def test_get_symbol_payout_invalid_symbol(self):
        current_config = self.mock_load_config.return_value
        payout = get_symbol_payout(symbol_id=99, count=3, config_symbols_map=current_config['game']['symbols_map'], is_scatter=False)
        self.assertEqual(payout, 0.0)

    def test_get_symbol_payout_insufficient_count(self):
        current_config = self.mock_load_config.return_value
        payout = get_symbol_payout(symbol_id=1, count=2, config_symbols_map=current_config['game']['symbols_map'], is_scatter=False)
        self.assertEqual(payout, 0.0)

    def test_calculate_win_single_payline_win(self):
        grid = [[2,2,2,2,2], [1,1,1,3,2], [3,3,3,3,3]]
        current_config = self.mock_load_config.return_value
        # Paylines are now under game.layout.paylines
        paylines_from_config = current_config['game']['layout']['paylines']
        bet_amount_sats = len(paylines_from_config) * 1 # Min bet assuming 1 per line

        win_info = calculate_win(grid, paylines_from_config, current_config['game']['symbols_map'],
                                 bet_amount_sats, current_config['game']['wild_symbol_id'],
                                 current_config['game']['scatter_symbol_id'], None)

        # Bet per line = bet_amount_sats / num_paylines. Here, 1 payline.
        # Payout for 3x Symbol 1 is 1.0. So win = 1 * 1.0 = 1.
        # If bet_amount_sats was e.g. 10 (for 1 line), win = 10 * 1.0 = 10
        bet_per_line = bet_amount_sats / len(paylines_from_config) # Use the correct paylines variable
        expected_win = bet_per_line * 1.0

        self.assertEqual(win_info['total_win_sats'], expected_win)
        self.assertEqual(len(win_info['winning_lines']), 1)
        self.assertEqual(win_info['winning_lines'][0]['symbol_id'], 1)
        self.assertEqual(win_info['winning_lines'][0]['count'], 3)
        # Convert to list of tuples for set comparison if order doesn't matter, or sort.
        # Here, direct comparison of one coord is fine for simplicity.
        self.assertIn(tuple([1,0]), [tuple(c) for c in win_info['winning_symbol_coords']])


    def test_calculate_win_scatter_win(self):
        grid = [[3,1,1,1,3], [1,3,1,3,1], [1,1,3,1,1]] # 5 scatters
        current_config = self.mock_load_config.return_value
        # Paylines are now under game.layout.paylines
        paylines_from_config = current_config['game']['layout']['paylines']
        bet_amount_sats = 10

        win_info = calculate_win(grid, paylines_from_config, current_config['game']['symbols_map'],
                                 bet_amount_sats, current_config['game']['wild_symbol_id'],
                                 current_config['game']['scatter_symbol_id'], None)

        scatter_payout_multiplier = current_config['game']['symbols_map'][3]['scatter_payouts']['5']
        self.assertEqual(win_info['total_win_sats'], bet_amount_sats * scatter_payout_multiplier)
        self.assertTrue(any(line['line_id'] == 'scatter' for line in win_info['winning_lines']))

    def test_check_bonus_trigger_sufficient_scatters(self):
        grid = [[3,1,2,1,3], [1,3,1,2,1], [2,1,3,1,2]] # 3 scatters
        current_config = self.mock_load_config.return_value
        trigger_info = check_bonus_trigger(grid,
                                          current_config['game']['scatter_symbol_id'],
                                          current_config['game']['bonus_features'])
        self.assertTrue(trigger_info['triggered'])
        self.assertEqual(trigger_info['spins_awarded'], current_config['game']['bonus_features']['free_spins']['spins_awarded'])
        self.assertEqual(trigger_info['multiplier'], current_config['game']['bonus_features']['free_spins']['multiplier'])

    def test_check_bonus_trigger_insufficient_scatters(self):
        grid = [[3,1,2,1,3], [1,1,1,2,1], [2,1,1,1,2]] # 2 scatters
        current_config = self.mock_load_config.return_value
        trigger_info = check_bonus_trigger(grid,
                                          current_config['game']['scatter_symbol_id'],
                                          current_config['game']['bonus_features'])
        self.assertFalse(trigger_info['triggered'])

    def test_handle_cascade_fill_fall_from_top(self):
        initial_grid = [[1, None, 3], [None, 5, None], [6, 7, 8]]
        winning_coords_to_clear = [(0,1), (1,0), (1,2)]
        db_symbols_mock = [MockSlotSymbol(s_id) for s_id in [1,3,5,6,7,8, 99]]
        current_config = self.mock_load_config.return_value
        # Ensure the test symbol '99' is part of the config symbols map for generation
        # Make a copy to avoid modifying the config used by other tests via mock_load_config
        symbols_map_for_test = current_config['game']['symbols_map'].copy()
        symbols_map_for_test[99] = {"id": 99, "name": "New Sym", "weight": 1.0}


        with patch('casino_be.utils.spin_handler_new._generate_weighted_random_symbols', return_value=[99, 99, 99]) as mock_gen_sym:
            new_grid = handle_cascade_fill(
                initial_grid, winning_coords_to_clear, "fall_from_top",
                db_symbols_mock, symbols_map_for_test, # Use extended map for this test
                current_config['game']['wild_symbol_id'],
                current_config['game']['scatter_symbol_id']
            )

        expected_grid = [[99, 99, 99], [1, 5, 3], [6, 7, 8]]
        self.assertEqual(new_grid, expected_grid)
        # _generate_weighted_random_symbols is called per column if there are empty slots at the top after fall
        self.assertEqual(mock_gen_sym.call_count, 3)


    @patch('casino_be.utils.spin_handler_new.generate_spin_grid')
    @patch('casino_be.utils.spin_handler_new.calculate_win')
    @patch('casino_be.utils.spin_handler_new.check_bonus_trigger')
    def test_handle_spin_normal_spin_no_win_no_bonus(
        self, mock_check_bonus, mock_calculate_win, mock_generate_grid
    ):
        bet_amount = 10
        self.mock_user.balance = 100
        mock_generate_grid.return_value = [[1,1,2],[1,2,1],[2,1,1]]
        mock_calculate_win.return_value = {"total_win_sats": 0, "winning_lines": [], "winning_symbol_coords": []}
        mock_check_bonus.return_value = {"triggered": False}

        result = handle_spin(self.mock_user, self.mock_slot, self.mock_game_session, bet_amount)

        self.assertEqual(result['win_amount_sats'], 0)
        self.assertFalse(result['bonus_triggered'])
        self.assertEqual(self.mock_user.balance, 100 - bet_amount)
        self.assertEqual(self.mock_game_session.amount_wagered, bet_amount)
        self.assertEqual(self.mock_game_session.amount_won, 0)
        # Expect 1 Transaction (wager) and 1 SlotSpin to be added
        self.assertEqual(self.mock_db_session.add.call_count, 2)
        self.mock_db_session.commit.assert_not_called()

    @patch('casino_be.utils.spin_handler_new.generate_spin_grid')
    @patch('casino_be.utils.spin_handler_new.calculate_win')
    @patch('casino_be.utils.spin_handler_new.check_bonus_trigger')
    def test_handle_spin_normal_spin_with_win(
        self, mock_check_bonus, mock_calculate_win, mock_generate_grid
    ):
        bet_amount = 10
        win_amount = 50
        self.mock_user.balance = 100
        mock_generate_grid.return_value = [[1,1,1],[2,2,2],[3,3,3]]
        mock_calculate_win.return_value = {
            "total_win_sats": win_amount,
            "winning_lines": [{"line_id":0, "symbol_id":1, "count":3, "win_amount_sats": win_amount, "positions":[[0,0],[0,1],[0,2]]}],
            "winning_symbol_coords": [[0,0],[0,1],[0,2]]
        }
        mock_check_bonus.return_value = {"triggered": False}

        result = handle_spin(self.mock_user, self.mock_slot, self.mock_game_session, bet_amount)

        self.assertEqual(result['win_amount_sats'], win_amount)
        self.assertEqual(self.mock_user.balance, 100 - bet_amount + win_amount)
        self.assertEqual(self.mock_game_session.amount_wagered, bet_amount)
        self.assertEqual(self.mock_game_session.amount_won, win_amount)
        self.assertEqual(self.mock_db_session.add.call_count, 3) # Wager Tx, Win Tx, Spin Record

    @patch('casino_be.utils.spin_handler_new.generate_spin_grid')
    @patch('casino_be.utils.spin_handler_new.calculate_win')
    @patch('casino_be.utils.spin_handler_new.check_bonus_trigger')
    def test_handle_spin_triggers_bonus(
        self, mock_check_bonus, mock_calculate_win, mock_generate_grid
    ):
        bet_amount = 10
        self.mock_user.balance = 100
        mock_generate_grid.return_value = [[3,3,3],[1,1,1],[2,2,2]]
        mock_calculate_win.return_value = {"total_win_sats": 0, "winning_lines": [], "winning_symbol_coords": []}
        # Use the config from mock_load_config for consistency
        current_config_for_bonus = self.mock_load_config.return_value
        mock_check_bonus.return_value = {
            "triggered": True,
            "spins_awarded": current_config_for_bonus['game']['bonus_features']['free_spins']['spins_awarded'],
            "multiplier": current_config_for_bonus['game']['bonus_features']['free_spins']['multiplier']
        }

        result = handle_spin(self.mock_user, self.mock_slot, self.mock_game_session, bet_amount)

        self.assertTrue(result['bonus_triggered'])
        self.assertTrue(self.mock_game_session.bonus_active)
        self.assertEqual(self.mock_game_session.bonus_spins_remaining, current_config_for_bonus['game']['bonus_features']['free_spins']['spins_awarded'])
        self.assertEqual(self.mock_game_session.bonus_multiplier, current_config_for_bonus['game']['bonus_features']['free_spins']['multiplier'])
        self.assertEqual(self.mock_user.balance, 100 - bet_amount)

    @patch('casino_be.utils.spin_handler_new.generate_spin_grid')
    @patch('casino_be.utils.spin_handler_new.calculate_win')
    def test_handle_spin_bonus_spin_active(
        self, mock_calculate_win, mock_generate_grid
    ):
        bet_amount_for_call = 0 # Actual bet for bonus spin is 0
        win_amount_raw = 50
        initial_bonus_spins = 5
        bonus_multiplier = 2.0

        self.mock_user.balance = 100
        self.mock_game_session.bonus_active = True
        self.mock_game_session.bonus_spins_remaining = initial_bonus_spins
        self.mock_game_session.bonus_multiplier = bonus_multiplier

        mock_generate_grid.return_value = [[1,1,1],[2,2,2],[3,3,3]]
        mock_calculate_win.return_value = {
            "total_win_sats": win_amount_raw,
            "winning_lines": [{"line_id":0, "symbol_id":1, "count":3, "win_amount_sats": win_amount_raw, "positions":[[0,0],[0,1],[0,2]]}],
            "winning_symbol_coords": [[0,0],[0,1],[0,2]]
        }

        result = handle_spin(self.mock_user, self.mock_slot, self.mock_game_session, bet_amount_for_call)

        self.assertEqual(result['win_amount_sats'], int(win_amount_raw * bonus_multiplier))
        self.assertEqual(self.mock_game_session.bonus_spins_remaining, initial_bonus_spins - 1)
        self.assertEqual(self.mock_user.balance, 100 + int(win_amount_raw * bonus_multiplier))
        self.assertEqual(self.mock_game_session.amount_wagered, 0)
        # Session amount_won should accumulate total winnings in the session
        self.assertEqual(self.mock_game_session.amount_won, int(win_amount_raw * bonus_multiplier))
        self.assertTrue(result['bonus_active'])

    def test_handle_spin_insufficient_balance(self):
        bet_amount = 100
        self.mock_user.balance = 50

        with self.assertRaisesRegex(ValueError, "Insufficient balance"):
            handle_spin(self.mock_user, self.mock_slot, self.mock_game_session, bet_amount)

        self.mock_db_session.rollback.assert_called_once()

    def test_handle_spin_invalid_bet_amount_non_positive(self):
        """Test handle_spin with a non-positive bet amount."""
        with self.assertRaisesRegex(ValueError, "Invalid bet amount"):
            handle_spin(self.mock_user, self.mock_slot, self.mock_game_session, 0)
        self.mock_db_session.rollback.assert_called_once()

    def test_handle_spin_invalid_bet_not_divisible_by_paylines(self):
        """Test handle_spin with bet not divisible by number of paylines."""
        expected_short_name = "payline_check_slot"

        # ABSOLUTELY MINIMAL CONFIG ensuring all keys accessed by handle_spin are present
        ultra_minimal_config = {
            "game": {
                "name": "ultra_min",
                "short_name": expected_short_name,
                "layout": {
                    "rows": 3,
                    "columns": 5,
                    "paylines": [{"id": i, "coords": [[0,0],[0,1],[0,2],[0,3],[0,4]]} for i in range(5)] # 5 paylines, nested under layout
                },
                "symbols": [{"id": 1, "name": "S1"}],
                # "paylines" key directly under "game" is now removed as per new structure.
                "wild_symbol_id": None,
                "scatter_symbol_id": None,
                "bonus_features": {},
                "is_cascading": False,
                "cascade_type": None,
                "min_symbols_to_match": None,
                "win_multipliers": [],
                "reel_strips": None
            }
        }

        # This internal function will be our side_effect
        def mock_load_game_config_side_effect(slot_short_name_arg):
            self.assertEqual(slot_short_name_arg, expected_short_name)
            return ultra_minimal_config

        self.mock_load_config.reset_mock()
        self.mock_load_config.side_effect = mock_load_game_config_side_effect

        test_slot = MockSlot(id=1, name="Payline Check Slot", short_name=expected_short_name)

        with self.assertRaisesRegex(ValueError, "must be evenly divisible by number of paylines"):
            handle_spin(self.mock_user, test_slot, self.mock_game_session, 7)

        self.mock_load_config.assert_called_once_with(expected_short_name)
        self.mock_db_session.rollback.assert_called_once()

    # --- Tests for bonus logic within spin_handler_new ---

    def test_check_bonus_trigger_no_config(self):
        """Test check_bonus_trigger when no bonus_features config exists."""
        grid = [[1,2,3],[1,2,3],[1,2,3]] # Example grid
        scatter_id = 3
        bonus_features_config = {} # No 'free_spins' key
        result = check_bonus_trigger(grid, scatter_id, bonus_features_config)
        self.assertFalse(result['triggered'])

    def test_check_bonus_trigger_no_scatter_id(self):
        """Test check_bonus_trigger when scatter_symbol_id is None."""
        grid = [[1,2,3],[1,2,3],[1,2,3]]
        bonus_features_config = {"free_spins": {"trigger_count": 3, "spins_awarded": 10, "multiplier": 2.0}}
        # scatter_symbol_id in game_config might be None if not defined for the slot
        result = check_bonus_trigger(grid, None, bonus_features_config)
        self.assertFalse(result['triggered']) # Should not trigger if no scatter ID to check for

    # test_check_bonus_trigger_sufficient_scatters and insufficient_scatters are already present and seem okay.

    @patch('casino_be.utils.spin_handler_new.generate_spin_grid')
    @patch('casino_be.utils.spin_handler_new.calculate_win')
    @patch('casino_be.utils.spin_handler_new.check_bonus_trigger') # Keep this mock for direct control
    def test_handle_spin_triggers_bonus_updates_session(
        self, mock_check_bonus_trigger, mock_calculate_win, mock_generate_grid
    ):
        """Test that when a bonus is triggered, game_session is updated correctly."""
        bet_amount = 10
        self.mock_user.balance = 100
        mock_generate_grid.return_value = [[3,3,3],[1,1,1],[2,2,2]] # Example grid
        mock_calculate_win.return_value = {"total_win_sats": 0, "winning_lines": [], "winning_symbol_coords": []}

        # Configure check_bonus_trigger to return a triggered bonus
        bonus_award_details = {"triggered": True, "spins_awarded": 15, "multiplier": 2.5}
        mock_check_bonus_trigger.return_value = bonus_award_details

        # Ensure game session starts with no bonus active
        self.mock_game_session.bonus_active = False
        self.mock_game_session.bonus_spins_remaining = 0
        self.mock_game_session.bonus_multiplier = 1.0

        result = handle_spin(self.mock_user, self.mock_slot, self.mock_game_session, bet_amount)

        self.assertTrue(result['bonus_triggered'])
        self.assertTrue(self.mock_game_session.bonus_active)
        self.assertEqual(self.mock_game_session.bonus_spins_remaining, 15)
        self.assertEqual(self.mock_game_session.bonus_multiplier, 2.5)
        # Ensure check_bonus_trigger was actually called
        mock_check_bonus_trigger.assert_called_once()


    @patch('casino_be.utils.spin_handler_new.generate_spin_grid')
    @patch('casino_be.utils.spin_handler_new.calculate_win')
    # No need to mock check_bonus_trigger here, as it shouldn't be called during an active bonus spin
    def test_handle_spin_active_bonus_spin_logic(
        self, mock_calculate_win, mock_generate_grid
    ):
        """Test logic during an active bonus spin (bet is 0, multiplier applies, spins decrement)."""
        bet_amount_for_call = 10 # This would be the player's selected bet, but it's not charged
        raw_win_amount = 50

        self.mock_user.balance = 100
        self.mock_game_session.bonus_active = True
        self.mock_game_session.bonus_spins_remaining = 5
        self.mock_game_session.bonus_multiplier = 3.0 # Example multiplier

        mock_generate_grid.return_value = [[1,1,1],[2,2,2],[3,3,3]] # Example winning grid
        mock_calculate_win.return_value = {
            "total_win_sats": raw_win_amount,
            "winning_lines": [{"line_id":0, "symbol_id":1, "count":3, "win_amount_sats": raw_win_amount, "positions":[[0,0],[0,1],[0,2]]}],
            "winning_symbol_coords": [[0,0],[0,1],[0,2]]
        }

        result = handle_spin(self.mock_user, self.mock_slot, self.mock_game_session, bet_amount_for_call)

        self.assertTrue(result['is_bonus_spin']) # This key needs to be added to the return dict of handle_spin
        self.assertEqual(result['win_amount_sats'], int(raw_win_amount * self.mock_game_session.bonus_multiplier))
        self.assertEqual(self.mock_game_session.bonus_spins_remaining, 4)
        self.assertEqual(self.mock_user.balance, 100 + int(raw_win_amount * self.mock_game_session.bonus_multiplier))
        self.assertEqual(self.mock_game_session.amount_wagered, 0) # Initial wagered amount for session, not for this specific bonus spin cost
        self.assertEqual(result['bet_amount'], 0) # actual_bet_this_spin should be 0 in spin record
        self.assertTrue(self.mock_game_session.bonus_active) # Still active

    @patch('casino_be.utils.spin_handler_new.generate_spin_grid')
    @patch('casino_be.utils.spin_handler_new.calculate_win')
    def test_handle_spin_bonus_spins_run_out(
        self, mock_calculate_win, mock_generate_grid
    ):
        """Test that bonus_active becomes False when bonus_spins_remaining hits zero."""
        self.mock_user.balance = 100
        self.mock_game_session.bonus_active = True
        self.mock_game_session.bonus_spins_remaining = 1 # Last bonus spin
        self.mock_game_session.bonus_multiplier = 2.0

        mock_generate_grid.return_value = [[1,1,1],[2,2,2],[3,3,3]]
        mock_calculate_win.return_value = {"total_win_sats": 10, "winning_lines": [], "winning_symbol_coords": []}

        result = handle_spin(self.mock_user, self.mock_slot, self.mock_game_session, 10)

        self.assertEqual(self.mock_game_session.bonus_spins_remaining, 0)
        self.assertFalse(self.mock_game_session.bonus_active) # Should now be false
        self.assertEqual(result['bonus_active'], False)
        self.assertEqual(result['bonus_spins_remaining'], 0)
        self.assertEqual(result['bonus_multiplier'], 1.0) # Should reset to default

    @patch('casino_be.utils.spin_handler_new.generate_spin_grid')
    @patch('casino_be.utils.spin_handler_new.calculate_win')
    @patch('casino_be.utils.spin_handler_new.check_bonus_trigger')
    def test_handle_spin_wagering_progress_on_paid_spin_with_active_bonus(
        self, mock_check_bonus, mock_calculate_win, mock_generate_grid
    ):
        """Test wagering progress for UserBonus on a paid spin when a UserBonus is active."""
        bet_amount = 20
        self.mock_user.balance = 100

        # Setup active UserBonus for the user
        mock_active_user_bonus = MockUserBonus(
            user_id=self.mock_user.id,
            bonus_code_id=10,
            bonus_amount_awarded_sats=1000,
            wagering_requirement_sats=100, # Wagering requirement
            wagering_progress_sats=50,     # Initial progress
            is_active=True
        )
        self.mock_user_bonus_query.filter_by.return_value.first.return_value = mock_active_user_bonus

        # This is a paid spin, so game_session bonus state is not used for spin execution itself
        self.mock_game_session.bonus_active = False
        self.mock_game_session.bonus_spins_remaining = 0

        mock_generate_grid.return_value = [[1,2,1],[2,1,2],[1,1,2]] # Non-winning grid
        mock_calculate_win.return_value = {"total_win_sats": 0, "winning_lines": [], "winning_symbol_coords": []}
        mock_check_bonus.return_value = {"triggered": False} # No slot bonus triggered

        handle_spin(self.mock_user, self.mock_slot, self.mock_game_session, bet_amount)

        self.assertEqual(mock_active_user_bonus.wagering_progress_sats, 50 + bet_amount)
        self.assertTrue(mock_active_user_bonus.is_active) # Wagering not yet met (70 < 100)
        self.assertFalse(mock_active_user_bonus.is_completed)
        self.assertIsNotNone(mock_active_user_bonus.updated_at)


    @patch('casino_be.utils.spin_handler_new.generate_spin_grid')
    @patch('casino_be.utils.spin_handler_new.calculate_win')
    @patch('casino_be.utils.spin_handler_new.check_bonus_trigger')
    def test_handle_spin_wagering_progress_completes_bonus(
        self, mock_check_bonus, mock_calculate_win, mock_generate_grid
    ):
        """Test UserBonus completion when wagering requirement is met."""
        bet_amount = 50
        self.mock_user.balance = 200

        mock_active_user_bonus = MockUserBonus(
            user_id=self.mock_user.id, bonus_code_id=11,
            bonus_amount_awarded_sats=1000,
            wagering_requirement_sats=100,
            wagering_progress_sats=50, # Progress is 50, needs 50 more. Bet is 50.
            is_active=True
        )
        self.mock_user_bonus_query.filter_by.return_value.first.return_value = mock_active_user_bonus

        self.mock_game_session.bonus_active = False
        self.mock_game_session.bonus_spins_remaining = 0

        mock_generate_grid.return_value = [[1,2,1],[2,1,2],[1,1,2]]
        mock_calculate_win.return_value = {"total_win_sats": 0, "winning_lines": [], "winning_symbol_coords": []}
        mock_check_bonus.return_value = {"triggered": False}

        handle_spin(self.mock_user, self.mock_slot, self.mock_game_session, bet_amount)

        self.assertEqual(mock_active_user_bonus.wagering_progress_sats, 100)
        self.assertFalse(mock_active_user_bonus.is_active) # Should become inactive
        self.assertTrue(mock_active_user_bonus.is_completed) # Should become completed
        self.assertIsNotNone(mock_active_user_bonus.completed_at)

    # Test that wagering progress is NOT updated on a bonus spin (free spin from game_session)
    @patch('casino_be.utils.spin_handler_new.generate_spin_grid')
    @patch('casino_be.utils.spin_handler_new.calculate_win')
    def test_handle_spin_no_wagering_progress_on_bonus_spin(
        self, mock_calculate_win, mock_generate_grid
    ):
        bet_amount_for_call = 10 # This bet is not charged and should not count for wagering

        mock_active_user_bonus = MockUserBonus(
            user_id=self.mock_user.id, bonus_code_id=12,
            bonus_amount_awarded_sats=500,
            wagering_requirement_sats=200,
            wagering_progress_sats=20,
            is_active=True
        )
        self.mock_user_bonus_query.filter_by.return_value.first.return_value = mock_active_user_bonus

        # This IS a bonus spin from game_session
        self.mock_game_session.bonus_active = True
        self.mock_game_session.bonus_spins_remaining = 3

        mock_generate_grid.return_value = [[1,2,1],[2,1,2],[1,1,2]]
        mock_calculate_win.return_value = {"total_win_sats": 0, "winning_lines": [], "winning_symbol_coords": []}
        # check_bonus_trigger is not called on bonus spins

        initial_wagering_progress = mock_active_user_bonus.wagering_progress_sats
        initial_updated_at = mock_active_user_bonus.updated_at

        handle_spin(self.mock_user, self.mock_slot, self.mock_game_session, bet_amount_for_call)

        # Wagering progress should NOT change because it was a bonus spin from game session
        self.assertEqual(mock_active_user_bonus.wagering_progress_sats, initial_wagering_progress)
        self.assertEqual(mock_active_user_bonus.updated_at, initial_updated_at) # updated_at should not change
        self.assertTrue(mock_active_user_bonus.is_active)
        self.assertFalse(mock_active_user_bonus.is_completed)


if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False)
