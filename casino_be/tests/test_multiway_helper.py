import unittest
from unittest.mock import patch, MagicMock
import json
import secrets # To mock choices if needed for future cascade tests in multiway

from casino_be.app import app, db
from casino_be.models import User, Slot, GameSession, SlotSpin, Transaction, SlotSymbol
from casino_be.utils.multiway_helper import handle_multiway_spin # Target function

# Default configuration values that can be overridden by specific tests
BASE_MULTIWAY_GAME_CONFIG = {
    "game": {
        "slot_id": 2, # Different from spin_handler test slot
        "name": "Test Multiway Slot",
        "short_name": "test_multiway1",
        "layout": {"rows": 3, "columns": 5}, # Max rows/cols, actual panes vary
        "symbols": [
            {"id": 1, "name": "SymbolA", "asset": "symA.png", "ways_payouts": {"3": 10, "4": 20, "5": 50}, "weight": 10.0},
            {"id": 2, "name": "SymbolB", "asset": "symB.png", "ways_payouts": {"3": 5, "4": 10, "5": 20}, "weight": 20.0},
            {"id": 3, "name": "SymbolC", "asset": "symC.png", "weight": 30.0},
            {"id": 4, "name": "Scatter", "asset": "scatter.png", "scatter_payouts": {"3": 5, "4": 10, "5": 25}, "weight": 5.0}, # Scatter
            {"id": 5, "name": "Wild", "asset": "wild.png", "weight": 3.0} # Wild
        ],
        "wild_symbol_id": 5,
        "scatter_symbol_id": 4,
        "bonus_features": { # To be configured by tests
            # "free_spins": {
            #     "trigger_symbol_id": 4, # Scatter
            #     "trigger_count": 3,
            #     "spins_awarded": 10,
            #     "multiplier": 2.0
            # }
        },
        "is_multiway": True, # Important for multiway
        "bet_ways_divisor": 25.0, # Example divisor
        "min_match_for_ways_win": 3,
        # Multiway slots might not typically use cascading or global win multipliers in the same way
        "is_cascading": False,
        "cascade_type": None,
        "win_multipliers": [],
        "reel_configurations": { # Example, actual can be varied by slot model
            "possible_counts_per_reel": [[3,4,5],[3,4,5],[3,4,5],[3,4,5],[3,4,5]]
        }
    }
}

class TestMultiwaySpinHandler(unittest.TestCase):
    def setUp(self):
        self.app = app
        # self.app.config.update(TESTING=True) # Ensure testing config if not already set by env vars
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        self.user = User(username='testmultiwayuser', email='testmw@example.com', password='password')
        self.user.balance = 100000 # Sats
        db.session.add(self.user)

        self.slot = Slot(
            id=2, # Match config
            name="Test Multiway Slot",
            short_name="test_multiway1",
            num_rows=3, # Max rows
            num_columns=5, # Num reels
            num_symbols=11, # Added default based on config
            asset_directory="/test_assets/", # Added missing non-nullable field
            is_active=True,
            rtp=95.0,
            volatility="High",
            is_multiway=True,
            reel_configurations={"possible_counts_per_reel": [[3],[3],[3],[3],[3]]} # Default, can be overridden
        )
        db.session.add(self.slot)
        # Create SlotSymbol instances based on BASE_MULTIWAY_GAME_CONFIG
        for symbol_data in BASE_MULTIWAY_GAME_CONFIG['game']['symbols']:
            slot_symbol = SlotSymbol(
                slot_id=self.slot.id,
                symbol_internal_id=symbol_data['id'],
                name=symbol_data['name'],
                img_link=symbol_data['asset'], # Assuming 'asset' is the img_link
                value_multiplier=0.0, # Default, as payouts are in ways_payouts/scatter_payouts
                data=symbol_data # Store whole symbol config in data if needed
            )
            db.session.add(slot_symbol)
        db.session.commit()

        self.game_session = GameSession(user_id=self.user.id, slot_id=self.slot.id, game_type='slot')
        db.session.add(self.game_session)
        db.session.commit()

        self.mock_load_config = patch('casino_be.utils.multiway_helper.load_multiway_game_config').start()
        self.mock_load_config.return_value = BASE_MULTIWAY_GAME_CONFIG

        self.mock_generate_grid = patch('casino_be.utils.multiway_helper.generate_multiway_spin_grid').start()
        # Default mock grid structure for multiway
        self.default_multiway_grid_data = {
            "panes_per_reel": [3, 3, 3, 3, 3],
            "symbols_grid": [
                [1,2,3],[1,2,3],[1,2,3],[1,2,3],[1,2,3] # Placeholder
            ]
        }
        self.mock_generate_grid.return_value = self.default_multiway_grid_data

        # Mock for check_bonus_trigger's use of random if it were more complex (not strictly needed for current setup)
        self.mock_choices = patch('secrets.SystemRandom.choices').start()


    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()
        patch.stopall()

    def helper_configure_multiway_bonus_game(self, trigger_symbol_id=4, trigger_count=3, spins_awarded=10, multiplier=2.0, retrigger_spins=5, retrigger_multiplier=None):
        """Helper to configure bonus features for multiway slot tests."""
        config = json.loads(json.dumps(BASE_MULTIWAY_GAME_CONFIG)) # Deep copy
        config['game']['bonus_features'] = {
            "free_spins": {
                "trigger_symbol_id": trigger_symbol_id,
                "trigger_count": trigger_count,
                "spins_awarded": spins_awarded,
                "multiplier": multiplier,
                # For simplicity, assume re-triggers use the same config or add to existing spins
                # More complex re-trigger logic would need specific config fields
            }
        }
        # Logic for retrigger if different from initial trigger (simplified for now)
        # config['game']['bonus_features']['free_spins']['retrigger_spins_awarded'] = retrigger_spins
        # if retrigger_multiplier is not None:
        #     config['game']['bonus_features']['free_spins']['retrigger_multiplier'] = retrigger_multiplier

        self.mock_load_config.return_value = config


    def test_multiway_free_spin_trigger(self):
        scatter_id = BASE_MULTIWAY_GAME_CONFIG['game']['scatter_symbol_id']
        self.helper_configure_multiway_bonus_game(trigger_symbol_id=scatter_id, trigger_count=3, spins_awarded=10, multiplier=2.0)

        # Grid with 3 scatter symbols (id 4)
        # Multiway grid: list of lists, where inner lists are reels
        trigger_grid_data = {
            "panes_per_reel": [3, 3, 3, 3, 3],
            "symbols_grid": [
                [scatter_id, 1, 2], # Reel 1
                [1, scatter_id, 2], # Reel 2
                [2, 1, scatter_id], # Reel 3
                [1, 2, 3],          # Reel 4
                [1, 2, 3]           # Reel 5
            ]
        }
        self.mock_generate_grid.return_value = trigger_grid_data

        bet_amount = 100
        result = handle_multiway_spin(self.user, self.slot, self.game_session, bet_amount)

        self.assertTrue(result['bonus_triggered'])
        self.assertTrue(self.game_session.bonus_active)
        self.assertEqual(self.game_session.bonus_spins_remaining, 10)
        self.assertEqual(self.game_session.bonus_multiplier, 2.0)

    def test_multiway_bonus_spin_behavior_win_and_cost(self):
        scatter_id = BASE_MULTIWAY_GAME_CONFIG['game']['scatter_symbol_id']
        wild_id = BASE_MULTIWAY_GAME_CONFIG['game']['wild_symbol_id']
        sym_a_id = 1 # Pays 10 for 3 ways

        self.helper_configure_multiway_bonus_game(multiplier=3.0) # 3x bonus multiplier
        self.game_session.bonus_active = True
        self.game_session.bonus_spins_remaining = 5
        self.game_session.bonus_multiplier = 3.0
        db.session.commit()

        initial_balance = self.user.balance

        # Grid for a win: 3 SymbolA (id 1) on first 3 reels, 1 per reel = 1 way
        # SymbolA ways_payouts: {"3": 10 ...}
        # Effective bet for ways = total_bet_sats / bet_ways_divisor = 100 / 25 = 4
        # Base win = 1 (way) * 10 (multiplier) * 4 (effective_bet) = 40
        # Bonus win = 40 * 3.0 (bonus_multiplier) = 120
        winning_grid_data = {
            "panes_per_reel": [1, 1, 1, 3, 3],
            "symbols_grid": [
                [sym_a_id], [sym_a_id], [sym_a_id], [2,3,4], [2,3,4]
            ]
        }
        self.mock_generate_grid.return_value = winning_grid_data

        bet_amount = 100 # This is the "original" bet amount for win calculation scaling
        result = handle_multiway_spin(self.user, self.slot, self.game_session, bet_amount)

        expected_win = 120
        self.assertEqual(result['win_amount_sats'], expected_win)
        # Balance should only increase by win, no bet deducted
        self.assertEqual(self.user.balance, initial_balance + expected_win)
        self.assertEqual(self.game_session.bonus_spins_remaining, 4)
        self.assertTrue(result['bonus_active']) # Still active

        slot_spin_record = SlotSpin.query.order_by(SlotSpin.id.desc()).first()
        self.assertIsNotNone(slot_spin_record)
        self.assertTrue(slot_spin_record.is_bonus_spin)
        self.assertEqual(slot_spin_record.bet_amount, 0) # No actual bet cost
        self.assertEqual(slot_spin_record.win_amount, expected_win)

        # Check no new wager transaction for this bonus spin
        wager_tx = Transaction.query.filter_by(user_id=self.user.id, transaction_type='wager').order_by(Transaction.id.desc()).first()
        if wager_tx: # If there was a previous wager
             self.assertNotEqual(wager_tx.slot_spin_id, slot_spin_record.id)


    def test_multiway_free_spin_retrigger(self):
        scatter_id = BASE_MULTIWAY_GAME_CONFIG['game']['scatter_symbol_id']
        initial_spins = 5
        initial_multiplier = 2.0
        spins_awarded_on_trigger = 10 # From helper default

        self.helper_configure_multiway_bonus_game(
            trigger_symbol_id=scatter_id, trigger_count=3,
            spins_awarded=spins_awarded_on_trigger, multiplier=initial_multiplier
        )

        self.game_session.bonus_active = True
        self.game_session.bonus_spins_remaining = initial_spins
        self.game_session.bonus_multiplier = initial_multiplier
        db.session.commit()

        # Grid with 3 scatter symbols to re-trigger
        retrigger_grid_data = {
            "panes_per_reel": [3,3,3,3,3],
            "symbols_grid": [
                [scatter_id, 1, 2], [1, scatter_id, 2], [2, 1, scatter_id], [1,2,3], [1,2,3]
            ]
        }
        self.mock_generate_grid.return_value = retrigger_grid_data

        bet_amount = 100 # Original bet amount
        result = handle_multiway_spin(self.user, self.slot, self.game_session, bet_amount)

        # Spins remaining: initial_spins (5) - 1 (for current spin) + spins_awarded_on_trigger (10) = 14
        self.assertEqual(self.game_session.bonus_spins_remaining, initial_spins - 1 + spins_awarded_on_trigger)
        self.assertTrue(result['bonus_triggered']) # Retrigger is also a "trigger"
        self.assertTrue(self.game_session.bonus_active)
        # Multiplier update logic: handle_spin takes the new multiplier if one is awarded.
        # Our helper sets up the bonus_features.free_spins.multiplier.
        # check_bonus_trigger returns this multiplier. handle_spin applies it.
        self.assertEqual(self.game_session.bonus_multiplier, initial_multiplier) # Assuming retrigger gives same multiplier type


    def test_multiway_bonus_end_after_last_spin(self):
        self.helper_configure_multiway_bonus_game(multiplier=2.0)
        self.game_session.bonus_active = True
        self.game_session.bonus_spins_remaining = 1 # Last bonus spin
        self.game_session.bonus_multiplier = 2.0
        db.session.commit()

        # Any grid, win or no win
        self.mock_generate_grid.return_value = self.default_multiway_grid_data

        bet_amount = 100
        result = handle_multiway_spin(self.user, self.slot, self.game_session, bet_amount)

        self.assertFalse(result['bonus_active'])
        self.assertFalse(self.game_session.bonus_active)
        self.assertEqual(self.game_session.bonus_spins_remaining, 0)
        self.assertEqual(self.game_session.bonus_multiplier, 1.0) # Reset to default

        slot_spin_record = SlotSpin.query.order_by(SlotSpin.id.desc()).first()
        self.assertTrue(slot_spin_record.is_bonus_spin) # This spin was a bonus spin


if __name__ == '__main__':
    unittest.main()
