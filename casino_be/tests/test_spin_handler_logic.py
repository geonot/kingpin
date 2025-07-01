import unittest
from unittest.mock import patch, MagicMock
from decimal import Decimal

# Assuming the app structure allows this import path when tests are run
from casino_be.utils.spin_handler_new import handle_spin
from casino_be.models import User, Slot, GameSession, SlotSymbol, UserBonus # Minimal models for type hinting and setup
from casino_be.app import create_app # For app context
from casino_be.config import TestingConfig

class TestSpinHandlerLogic(unittest.TestCase):

    def setUp(self):
        # Create a Flask app instance with testing config for context
        self.app, _ = create_app(TestingConfig)
        self.app_context = self.app.app_context()
        self.app_context.push()
        # Note: No db.create_all() as we are unit testing logic, not DB interaction here primarily

    def tearDown(self):
        self.app_context.pop()

    @patch('casino_be.utils.spin_handler_new.load_game_config')
    @patch('casino_be.utils.spin_handler_new.generate_spin_grid')
    @patch('casino_be.utils.spin_handler_new.calculate_win')
    @patch('casino_be.utils.spin_handler_new.check_bonus_trigger')
    @patch('casino_be.utils.spin_handler_new.handle_cascade_fill')
    @patch('casino_be.utils.spin_handler_new.db') # Mock db session
    def test_handle_spin_basic_win(
        self, mock_db, mock_handle_cascade_fill, mock_check_bonus_trigger,
        mock_calculate_win, mock_generate_spin_grid, mock_load_game_config
    ):
        # --- Mock Configurations and Inputs ---
        mock_user = MagicMock(spec=User)
        mock_user.id = 1
        mock_user.balance = 100000 # 1 BTC in satoshis

        mock_slot = MagicMock(spec=Slot)
        mock_slot.id = 1
        mock_slot.short_name = "testslot"
        mock_slot.is_multiway = False # For this test, assume not multiway
        mock_slot.symbols = [MagicMock(spec=SlotSymbol)] # Needs at least one symbol for some internal logic

        mock_game_session = MagicMock(spec=GameSession)
        mock_game_session.id = 1
        mock_game_session.bonus_active = False
        mock_game_session.bonus_spins_remaining = 0
        mock_game_session.amount_wagered = 0
        mock_game_session.amount_won = 0
        mock_game_session.num_spins = 0

        bet_amount_sats = 100

        # Mock return values for dependencies
        mock_game_config = {
            "game": {
                "layout": {"rows": 3, "columns": 5, "paylines": [{"id": "line1", "coords": [[0,0],[0,1],[0,2]]}]},
                "symbols": [{"id": 1, "name": "A"}, {"id": 2, "name": "B"}], # Simplified
                "symbols_map": {1: {"id": 1, "name": "A"}, 2: {"id": 2, "name": "B"}}, # Simplified
                "wild_symbol_id": None,
                "scatter_symbol_id": None,
                "is_cascading": False,
            }
        }
        mock_load_game_config.return_value = mock_game_config

        mock_spin_grid = [[1, 1, 1, 2, 2], [2, 2, 2, 2, 2], [2, 2, 2, 2, 2]]
        mock_generate_spin_grid.return_value = mock_spin_grid

        mock_win_info = {
            "total_win_sats": 500, # Example win
            "winning_lines": [{"line_id": "line1", "symbol_id": 1, "count": 3, "win_amount_sats": 500}],
            "winning_symbol_coords": [[0,0],[0,1],[0,2]]
        }
        mock_calculate_win.return_value = mock_win_info

        mock_check_bonus_trigger.return_value = {'triggered': False}

        # --- Call the function ---
        # Mock UserBonus query
        mock_query_result = MagicMock()
        mock_query_result.first.return_value = None # No active bonus
        mock_db.session.query(UserBonus).filter_by.return_value = mock_query_result


        result = handle_spin(mock_user, mock_slot, mock_game_session, bet_amount_sats)

        # --- Assertions ---
        self.assertIsNotNone(result)
        self.assertEqual(result['win_amount_sats'], 500)
        self.assertEqual(mock_user.balance, 100000 - bet_amount_sats + 500)
        self.assertEqual(mock_game_session.amount_wagered, bet_amount_sats)
        self.assertEqual(mock_game_session.amount_won, 500)
        self.assertEqual(mock_game_session.num_spins, 1)

        mock_load_game_config.assert_called_once_with(mock_slot.short_name)
        mock_generate_spin_grid.assert_called_once()
        mock_calculate_win.assert_called_once()
        mock_check_bonus_trigger.assert_called_once()

        # Ensure transactions were attempted (mock_db.session.add was called)
        # Two transactions: one for wager, one for win
        self.assertEqual(mock_db.session.add.call_count, 2 + 1) # Wager, Win, SlotSpin

if __name__ == '__main__':
    unittest.main()
