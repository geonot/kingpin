import unittest
import os
import sys
import random

# Adjust path to import from casino_be.utils
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from casino_be.utils.slot_tester import SlotTester
# For direct testing of calculate_win and get_symbol_payout
from casino_be.utils.spin_handler import calculate_win, get_symbol_payout
from casino_be.models import Slot, SlotSymbol # For type hints or creating specific mock objects if needed

# Define the base path for test configuration files
TEST_CONFIG_BASE_PATH = "casino_be/tests/test_data/slot_tester_configs"

class TestSlotTester(unittest.TestCase):

    def test_config_loading_and_mock_creation(self):
        print("\nRunning test_config_loading_and_mock_creation...")
        tester = SlotTester(slot_short_name="test_slot1", num_spins=1, bet_amount_sats=10)
        loaded = tester.load_configuration(test_config_base_path=TEST_CONFIG_BASE_PATH)

        self.assertTrue(loaded, "Configuration should be loaded successfully.")
        self.assertIsNotNone(tester.game_config, "game_config should not be None.")
        self.assertIsNotNone(tester.slot_properties, "slot_properties (mock Slot) should not be None.")

        self.assertEqual(tester.slot_properties.name, "Test Slot 1")
        self.assertEqual(tester.slot_properties.num_rows, 3)
        self.assertEqual(tester.slot_properties.num_columns, 3)
        self.assertEqual(len(tester.slot_properties.symbols), 3)
        self.assertEqual(tester.slot_properties.symbols[0].symbol_internal_id, 1)
        self.assertEqual(tester.slot_properties.symbols[1].name, "ScatterS")
        self.assertEqual(tester.slot_properties.scatter_symbol_id, 2, "Scatter Symbol ID on mock Slot not loaded correctly.")
        print("test_config_loading_and_mock_creation: PASSED")

    def test_calculate_win_simple_payline(self):
        print("\nRunning test_calculate_win_simple_payline...")
        # Load the config to get necessary parameters
        tester = SlotTester(slot_short_name="test_slot1", num_spins=1, bet_amount_sats=30) # 3 lines, 10 per line
        tester.load_configuration(test_config_base_path=TEST_CONFIG_BASE_PATH)
        game_data = tester.game_config['game']

        grid = [[1,1,1], [3,3,3], [3,3,3]] # 3 Cherries (ID 1) on payline 0, no other wins

        config_paylines = game_data['paylines']
        config_symbols_map = {s['id']: s for s in game_data['symbols']}
        total_bet_sats = 30 # Assuming 3 lines, 10 per line, or just a total bet.
                            # calculate_win uses total_bet_sats and derives bet_per_line.
        wild_symbol_id = game_data['symbol_wild']
        scatter_symbol_id = game_data['symbol_scatter']

        # For calculate_win, bet_per_line is derived. If 1 payline, bet_per_line = total_bet
        # If multiple paylines are defined in config and assumed active, it's total_bet / num_paylines
        # Our test_slot1 has 1 payline.
        # Payout for symbol 1, 3 matches is multiplier 10.
        # Win = (total_bet_sats / num_paylines) * multiplier = (30 / 1) * 10 = 300

        win_info = calculate_win(
            grid, config_paylines, config_symbols_map, total_bet_sats,
            wild_symbol_id, scatter_symbol_id,
            game_data.get('min_symbols_to_match')
        )

        self.assertEqual(win_info['total_win_sats'], 300, "Payline win calculation is incorrect.")
        self.assertTrue(any(line['line_id'] == 0 and line['symbol_id'] == 1 for line in win_info['winning_lines']), "Winning line detail missing or incorrect.")
        print("test_calculate_win_simple_payline: PASSED")

    def test_calculate_win_scatter(self):
        print("\nRunning test_calculate_win_scatter...")
        tester = SlotTester(slot_short_name="test_slot1", num_spins=1, bet_amount_sats=100)
        tester.load_configuration(test_config_base_path=TEST_CONFIG_BASE_PATH)
        game_data = tester.game_config['game']

        grid = [[2,2,2], [1,1,1], [1,1,1]] # Simplified grid: 3 Scatters (ID 2) on first row

        config_paylines = game_data['paylines']
        config_symbols_map = {s['id']: s for s in game_data['symbols']}
        total_bet_sats = 100
        wild_symbol_id = game_data['symbol_wild']
        scatter_symbol_id = game_data['symbol_scatter']

        # Scatter payout for 3 matches of symbol 2 is multiplier 5 (of total bet)
        # Win = total_bet_sats * 5 = 100 * 5 = 500

        win_info = calculate_win(
            grid, config_paylines, config_symbols_map, total_bet_sats,
            wild_symbol_id, scatter_symbol_id,
            game_data.get('min_symbols_to_match')
        )

        self.assertEqual(win_info['total_win_sats'], 500, "Scatter win calculation is incorrect.")
        self.assertTrue(any(line['line_id'] == 'scatter' and line['symbol_id'] == 2 for line in win_info['winning_lines']), "Scatter win detail missing or incorrect.")
        print("test_calculate_win_scatter: PASSED")

    def test_bonus_trigger_and_mechanics(self):
        print("\nRunning test_bonus_trigger_and_mechanics...")
        tester = SlotTester(slot_short_name="test_slot1", num_spins=10, bet_amount_sats=10)
        tester.load_configuration(test_config_base_path=TEST_CONFIG_BASE_PATH)
        tester.initialize_simulation_state()

        # To reliably test bonus, we need to force a grid.
        # This requires modifying how _simulate_one_spin gets its grid, or mocking generate_spin_grid.
        # For this test, let's assume generate_spin_grid can be influenced or mocked.
        # Monkey-patching generate_spin_grid where it's used (in slot_tester module)
        # Need to import the module itself to patch its members
        import casino_be.utils.slot_tester as slot_tester_module
        original_gsg_in_tester_module = slot_tester_module.generate_spin_grid

        try:
            # More extreme grid to ensure scatter count is high
            def mock_generate_trigger_grid(*args, **kwargs):
                print("DEBUG_TEST: Using mock_generate_TRIGGER_grid")
                return [[2,2,2],[2,2,2],[2,2,2]] # Grid with 9 scatters (ID 2)

            slot_tester_module.generate_spin_grid = mock_generate_trigger_grid

            spin_data_trigger = tester._simulate_one_spin()

            self.assertTrue(spin_data_trigger['bonus_triggered'], "Bonus should be triggered.")
            self.assertTrue(tester.mock_session.bonus_active, "Mock session bonus_active should be True.")
            self.assertEqual(tester.mock_session.bonus_spins_remaining, 5, "Bonus spins remaining incorrect.")
            self.assertEqual(tester.mock_session.bonus_multiplier, 2.0, "Bonus multiplier incorrect.")

            # Simulate a bonus spin
            def mock_generate_bonus_win_grid(*args, **kwargs):
                print("DEBUG_TEST: Using mock_generate_BONUS_WIN_grid")
                return [[1,1,1],[2,3,2],[3,2,3]]

            slot_tester_module.generate_spin_grid = mock_generate_bonus_win_grid
            spin_data_bonus_win = tester._simulate_one_spin()

            self.assertTrue(tester.mock_session.bonus_active, "Still in bonus.")
            self.assertEqual(tester.mock_session.bonus_spins_remaining, 4, "Bonus spins should decrease.")
            self.assertEqual(spin_data_bonus_win['win_amount_sats'], 300, "Bonus win multiplier not applied correctly. Expected 100 (payline) + 50 (scatter) = 150 raw, * 2 bonus_mult = 300.")

        finally:
            # Restore original function in the slot_tester module
            slot_tester_module.generate_spin_grid = original_gsg_in_tester_module

        print("test_bonus_trigger_and_mechanics: PASSED")

    def test_get_symbol_payout_direct(self):
        print("\nRunning test_get_symbol_payout_direct...")
        # This test needs access to get_symbol_payout, which is in spin_handler
        # Ensure get_symbol_payout is imported:
        # from casino_be.utils.spin_handler import get_symbol_payout

        # Minimal setup to get config_symbols_map
        tester = SlotTester(slot_short_name="test_slot1", num_spins=1, bet_amount_sats=10)
        tester.load_configuration(test_config_base_path=TEST_CONFIG_BASE_PATH)
        game_data = tester.game_config['game']
        config_symbols_map = {s['id']: s for s in game_data['symbols']}

        # Test payline symbol 1, 3 matches
        # Expected multiplier: 10.0 from "value_multipliers": {"3": 10}
        payline_mult = get_symbol_payout(symbol_id=1, count=3, config_symbols_map=config_symbols_map, is_scatter=False)
        self.assertEqual(payline_mult, 10.0, "get_symbol_payout direct for payline symbol 1 failed.")

        # Test scatter symbol 2, 3 matches
        # Expected multiplier: 5.0 from "payouts": {"3": 5}
        scatter_mult = get_symbol_payout(symbol_id=2, count=3, config_symbols_map=config_symbols_map, is_scatter=True)
        self.assertEqual(scatter_mult, 5.0, "get_symbol_payout direct for scatter symbol 2 failed.")
        print("test_get_symbol_payout_direct: assertions passed.")


    def test_rtp_calculation_simple(self):
        print("\nRunning test_rtp_calculation_simple...")
        tester = SlotTester(slot_short_name="test_slot1", num_spins=2, bet_amount_sats=10)
        # Manually set statistics
        tester.spin_results_data = [
            {'win_amount_sats': 100, 'actual_bet_this_spin': 10, 'bonus_active': False, 'is_bonus_spin': False, 'bonus_triggered': False},
            {'win_amount_sats': 0, 'actual_bet_this_spin': 10, 'bonus_active': False, 'is_bonus_spin': False, 'bonus_triggered': False}
        ]
        tester.num_spins = 2 # Crucial: must match spin_results_data length for some calculations
        tester.total_bet = 20
        tester.total_win = 100
        tester.hit_count = 1
        tester.bonus_triggers = 0
        tester.total_bonus_win = 0
        tester.is_in_bonus_previously = False # ensure correct state for bonus calcs

        tester.calculate_derived_statistics()

        self.assertAlmostEqual(tester.overall_rtp, 500.0, places=1, msg="Overall RTP calculation incorrect.")
        self.assertAlmostEqual(tester.hit_frequency, 50.0, places=1, msg="Hit frequency calculation incorrect.")
        print("test_rtp_calculation_simple: PASSED")

    def test_reel_strip_generation_basic(self):
        print("\nRunning test_reel_strip_generation_basic...")
        tester = SlotTester(slot_short_name="test_slot1", num_spins=1, bet_amount_sats=10)
        tester.load_configuration(test_config_base_path=TEST_CONFIG_BASE_PATH)
        tester.initialize_simulation_state()

        spin_data = tester._simulate_one_spin()
        self.assertIsNotNone(spin_data, "_simulate_one_spin should return data.")

        grid = spin_data['spin_result']
        game_reel_strips = tester.game_config['game']['reel_strips']

        self.assertEqual(len(grid[0]), len(game_reel_strips), "Grid column count should match reel_strips count.")

        for r_idx, row in enumerate(grid):
            for c_idx, symbol_id in enumerate(row):
                self.assertIn(symbol_id, game_reel_strips[c_idx],
                              f"Symbol {symbol_id} at [{r_idx}][{c_idx}] not found in reel strip {c_idx}.")
        print("test_reel_strip_generation_basic: PASSED")

if __name__ == "__main__":
    print("--- Running SlotTester Unit Tests ---")
    # Create a TestLoader
    loader = unittest.TestLoader()
    # Create a TestSuite
    suite = unittest.TestSuite()
    # Add tests to the suite
    suite.addTest(loader.loadTestsFromTestCase(TestSlotTester))
    # Create a TestResult object (optional, for more detailed results)
    # result = unittest.TestResult()
    # Create a TextTestRunner
    runner = unittest.TextTestRunner(verbosity=2) # verbosity=2 for more detailed output
    # Run the tests
    test_results = runner.run(suite)

    # Exit with a non-zero code if tests failed
    if not test_results.wasSuccessful():
        sys.exit(1)
    print("--- All SlotTester Unit Tests Passed ---")
