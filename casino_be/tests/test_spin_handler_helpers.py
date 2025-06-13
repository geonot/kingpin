import unittest
import secrets # Used by the functions, so good to have for context, maybe mocking later
from unittest.mock import MagicMock, patch

# Assuming the spin_handler.py is in casino_be.utils
# Adjust the import path if your file structure is different or if it's a module
from casino_be.utils.spin_handler import (
    _generate_weighted_random_symbols,
    _calculate_payline_wins_for_grid,
    _calculate_scatter_wins_for_grid,
    _calculate_cluster_wins_for_grid,
    check_bonus_trigger,
    handle_cascade_fill,
    get_symbol_payout # Also used by calculate_win helpers
)

# Mock SlotSymbol class/object to mimic SQLAlchemy model instances
class MockSlotSymbol:
    def __init__(self, symbol_internal_id, name="Test Symbol", img_link="test.png", value_multiplier=1.0, data=None):
        self.symbol_internal_id = symbol_internal_id
        self.name = name
        self.img_link = img_link
        self.value_multiplier = value_multiplier # Though not directly used by these helpers, good for completeness
        self.data = data if data is not None else {}

    def __repr__(self):
        return f"<MockSlotSymbol {self.name} (ID: {self.symbol_internal_id})>"

class TestSpinHandlerHelpers(unittest.TestCase):

    def setUp(self):
        """Setup common mock data for tests."""
        self.mock_secure_random = secrets.SystemRandom() # Use real one for now, can be mocked if needed for determinism

        # --- Mock Symbol Configurations (config_symbols_map) ---
        self.config_symbols_map_simple = {
            1: {"id": 1, "name": "Cherry", "weight": 10, "value_multipliers": {"3": 5, "2": 2}},
            2: {"id": 2, "name": "Lemon", "weight": 8, "value_multipliers": {"3": 4, "2": 1.5}},
            3: {"id": 3, "name": "Orange", "weight": 6, "value_multipliers": {"3": 3, "2": 1}},
            4: {"id": 4, "name": "Wild", "weight": 3, "is_wild": True, "value_multipliers": {"3": 10, "2": 5}}, # Wild pays
            5: {"id": 5, "name": "Scatter", "weight": 2, "is_scatter": True, "scatter_payouts": {"3": 5, "2": 2}} # Scatter pays
        }
        self.db_symbols_simple = [
            MockSlotSymbol(symbol_internal_id=1), MockSlotSymbol(symbol_internal_id=2),
            MockSlotSymbol(symbol_internal_id=3), MockSlotSymbol(symbol_internal_id=4),
            MockSlotSymbol(symbol_internal_id=5)
        ]

        self.config_symbols_map_cluster = {
            1: {"id": 1, "name": "RedGem", "weight": 10, "cluster_payouts": {"5": 2, "6": 3}},
            2: {"id": 2, "name": "BlueGem", "weight": 10, "cluster_payouts": {"5": 2, "6": 3}}, # Payout for 5 of BlueGem
            3: {"id": 3, "name": "GreenGem", "weight": 10, "cluster_payouts": {"5": 2, "6": 3}},
            4: {"id": 4, "name": "WildCluster", "weight": 2, "is_wild": True}
        }
        self.db_symbols_cluster = [
            MockSlotSymbol(symbol_internal_id=1), MockSlotSymbol(symbol_internal_id=2),
            MockSlotSymbol(symbol_internal_id=3), MockSlotSymbol(symbol_internal_id=4)
        ]

        # --- Mock Paylines ---
        self.config_paylines_simple = [
            {"id": "line1", "coords": [[0,0], [0,1], [0,2]]}, # Top row
            {"id": "line2", "coords": [[1,0], [1,1], [1,2]]}, # Middle row
        ]

    # --- Tests for _generate_weighted_random_symbols ---
    def test_gwr_returns_correct_count(self):
        symbols = _generate_weighted_random_symbols(3, self.config_symbols_map_simple, self.db_symbols_simple, self.mock_secure_random)
        self.assertEqual(len(symbols), 3)

    def test_gwr_symbol_ids_are_valid(self):
        symbols = _generate_weighted_random_symbols(50, self.config_symbols_map_simple, self.db_symbols_simple, self.mock_secure_random)
        valid_ids = self.config_symbols_map_simple.keys()
        for s_id in symbols:
            self.assertIn(s_id, valid_ids)

    def test_gwr_empty_db_symbols_uses_config_keys_if_possible(self):
        symbols = _generate_weighted_random_symbols(3, self.config_symbols_map_simple, [], self.mock_secure_random)
        self.assertEqual(len(symbols), 3)
        for s_id in symbols:
            self.assertIn(s_id, self.config_symbols_map_simple.keys())

    def test_gwr_all_zero_weights_uniform_distribution(self):
        zero_weight_map = {
            1: {"id": 1, "name": "A", "weight": 0},
            2: {"id": 2, "name": "B", "weight": 0}
        }
        db_syms = [MockSlotSymbol(1), MockSlotSymbol(2)]
        symbols = _generate_weighted_random_symbols(10, zero_weight_map, db_syms, self.mock_secure_random)
        self.assertEqual(len(symbols), 10)
        for s_id in symbols:
            self.assertIn(s_id, zero_weight_map.keys())

    def test_gwr_no_spinable_symbols_raises_error(self):
        with self.assertRaises(ValueError) as context:
            _generate_weighted_random_symbols(3, {}, [], self.mock_secure_random)
        self.assertTrue("No numeric symbol IDs available" in str(context.exception) or \
                        "No symbols available for choice" in str(context.exception))


    # --- Tests for get_symbol_payout (used by calculate_win helpers) ---
    def test_get_symbol_payout_payline(self):
        payout = get_symbol_payout(1, 3, self.config_symbols_map_simple, is_scatter=False)
        self.assertEqual(payout, 5)
        payout = get_symbol_payout(2, 2, self.config_symbols_map_simple, is_scatter=False)
        self.assertEqual(payout, 1.5)
        payout = get_symbol_payout(1, 1, self.config_symbols_map_simple, is_scatter=False)
        self.assertEqual(payout, 0.0)
        payout = get_symbol_payout(99, 3, self.config_symbols_map_simple, is_scatter=False)
        self.assertEqual(payout, 0.0)

    def test_get_symbol_payout_scatter(self):
        payout = get_symbol_payout(5, 3, self.config_symbols_map_simple, is_scatter=True)
        self.assertEqual(payout, 5)
        payout = get_symbol_payout(5, 2, self.config_symbols_map_simple, is_scatter=True)
        self.assertEqual(payout, 2)

    # --- Tests for _calculate_payline_wins_for_grid ---
    def test_cpw_no_win(self):
        grid = [[1,2,3], [3,2,1], [2,3,1]]
        results = _calculate_payline_wins_for_grid(grid, self.config_paylines_simple, self.config_symbols_map_simple, 100, 4, 5, 3, 3)
        self.assertEqual(results["win_sats"], 0)
        self.assertEqual(len(results["winning_lines"]), 0)
        self.assertEqual(len(results["winning_coords"]), 0)

    def test_cpw_single_payline_win(self):
        grid = [[1,1,1], [2,3,4], [5,1,2]]
        results = _calculate_payline_wins_for_grid(grid, self.config_paylines_simple, self.config_symbols_map_simple, 100, 4, 5, 3, 3)
        self.assertEqual(results["win_sats"], 5)
        self.assertEqual(len(results["winning_lines"]), 1)
        self.assertEqual(results["winning_lines"][0]["line_id"], "line1")
        self.assertEqual(results["winning_lines"][0]["symbol_id"], 1)
        self.assertEqual(results["winning_lines"][0]["count"], 3)
        self.assertEqual(len(results["winning_coords"]), 3)

    def test_cpw_multiple_payline_wins(self):
        grid = [[1,1,1], [2,2,2], [3,3,5]]
        results = _calculate_payline_wins_for_grid(grid, self.config_paylines_simple, self.config_symbols_map_simple, 100, 4, 5, 3, 3)
        self.assertEqual(results["win_sats"], 5 + 5)
        self.assertEqual(len(results["winning_lines"]), 2)

    def test_cpw_wild_contribution(self):
        grid = [[1,4,1], [2,3,2], [4,5,4]]
        results = _calculate_payline_wins_for_grid(grid, self.config_paylines_simple, self.config_symbols_map_simple, 100, 4, 5, 3, 3)
        self.assertEqual(results["win_sats"], 5)
        self.assertEqual(results["winning_lines"][0]["symbol_id"], 1)
        self.assertEqual(results["winning_lines"][0]["count"], 3)

    def test_cpw_wild_starts_line_then_regular(self):
        grid = [[4,1,1], [2,3,2], [3,4,5]]
        results = _calculate_payline_wins_for_grid(grid, self.config_paylines_simple, self.config_symbols_map_simple, 100, 4, 5, 3, 3)
        self.assertEqual(results["win_sats"], 5)
        self.assertEqual(results["winning_lines"][0]["symbol_id"], 1)
        self.assertEqual(results["winning_lines"][0]["count"], 3)
        self.assertIn(tuple([0,0]), results["winning_coords"])
        self.assertIn(tuple([0,1]), results["winning_coords"])
        self.assertIn(tuple([0,2]), results["winning_coords"])

    def test_cpw_line_of_only_wilds_pays(self):
        grid = [[4,4,4], [1,2,3], [1,2,3]]
        results = _calculate_payline_wins_for_grid(grid, self.config_paylines_simple, self.config_symbols_map_simple, 100, 4, 5, 3, 3)
        self.assertEqual(results["win_sats"], 10)
        self.assertEqual(results["winning_lines"][0]["symbol_id"], 4)
        self.assertEqual(results["winning_lines"][0]["count"], 3)

    # --- Tests for _calculate_scatter_wins_for_grid ---
    def test_csw_scatter_win(self):
        grid = [[5,1,2], [3,5,4], [1,2,5]]
        results = _calculate_scatter_wins_for_grid(grid, 5, self.config_symbols_map_simple, 100)
        self.assertEqual(results["win_sats"], 500)
        self.assertEqual(len(results["winning_lines"]), 1)
        self.assertEqual(results["winning_lines"][0]["symbol_id"], 5)
        self.assertEqual(results["winning_lines"][0]["count"], 3)
        self.assertEqual(len(results["winning_coords"]), 3)
        self.assertIn(tuple([0,0]), results["winning_coords"])
        self.assertIn(tuple([1,1]), results["winning_coords"])
        self.assertIn(tuple([2,2]), results["winning_coords"])

    def test_csw_not_enough_scatters(self):
        grid = [[5,1,2], [3,1,4], [1,2,5]]
        results = _calculate_scatter_wins_for_grid(grid, 5, self.config_symbols_map_simple, 100)
        self.assertEqual(results["win_sats"], 200)
        self.assertEqual(len(results["winning_lines"]), 1)

    def test_csw_no_scatter_symbol_configured(self):
        grid = [[1,1,1], [2,2,2], [3,3,3]]
        results = _calculate_scatter_wins_for_grid(grid, None, self.config_symbols_map_simple, 100)
        self.assertEqual(results["win_sats"], 0)

    # --- Tests for _calculate_cluster_wins_for_grid ---
    def test_ccw_no_min_symbols_to_match(self):
        grid = [[1,1,1,1,1], [2,2,2,2,2], [3,3,3,3,3]]
        results = _calculate_cluster_wins_for_grid(grid, self.config_symbols_map_cluster, 100, 4, None, None)
        self.assertEqual(results["win_sats"], 0)

    def test_ccw_cluster_win(self):
        # This grid has 6 of symbol 1 (RedGem) and no other symbol forms a cluster. No wilds.
        grid = [[1,1,1,7,8], [1,1,1,9,6], [5,2,3,2,3]]
        # RedGem (ID 1) 6-of-a-kind pays 3x total_bet_sats (100 * 3 = 300)
        results = _calculate_cluster_wins_for_grid(grid, self.config_symbols_map_cluster, 100, 4, None, 5) # min_symbols_to_match = 5
        self.assertEqual(results["win_sats"], 300)
        self.assertEqual(len(results["winning_lines"]), 1)
        self.assertEqual(results["winning_lines"][0]["symbol_id"], 1)
        self.assertEqual(results["winning_lines"][0]["count"], 6) # 6 literal + 0 wilds
        self.assertEqual(len(results["winning_coords"]), 6) # Ensure all 6 symbols are marked

    def test_ccw_cluster_win_with_wilds(self):
        # Grid: 3 RedGems (ID 1), 2 Wilds (ID 4). Effective count = 5 for RedGem.
        grid_for_5_cluster_with_wilds = [[1,4,1,2,3], [4,1,2,3,2], [3,2,3,2,3]]
        # Expected payout for 5 RedGems (ID 1) is 2x total_bet_sats = 200
        results_5_cluster = _calculate_cluster_wins_for_grid(grid_for_5_cluster_with_wilds, self.config_symbols_map_cluster, 100, 4, None, 5)
        self.assertEqual(results_5_cluster["win_sats"], 200)
        self.assertEqual(len(results_5_cluster["winning_lines"]), 1)
        self.assertEqual(results_5_cluster["winning_lines"][0]["symbol_id"], 1)
        self.assertEqual(results_5_cluster["winning_lines"][0]["count"], 3 + 2) # 3 literal + 2 wilds
        self.assertEqual(len(results_5_cluster["winning_coords"]), 3 + 2) # Positions of 3 RedGems and 2 Wilds

    def test_ccw_insufficient_for_cluster(self):
        grid = [[1,2,3,4,1], [2,3,4,1,2], [3,4,1,2,3]] # Max 4 of any symbol (ID 1 has 4, ID 2 has 4, ID 3 has 4), not enough for min_symbols_to_match = 5
        results = _calculate_cluster_wins_for_grid(grid, self.config_symbols_map_cluster, 100, 4, None, 5)
        self.assertEqual(results["win_sats"], 0)

    # --- Tests for check_bonus_trigger ---
    def test_cbt_trigger_free_spins(self):
        grid = [[5,1,5], [2,5,3], [4,2,1]] # 3 scatters (ID 5)
        bonus_features = {"free_spins": {"trigger_symbol_id": 5, "trigger_count": 3, "spins_awarded": 10, "multiplier": 2.0}}
        result = check_bonus_trigger(grid, 5, bonus_features)
        self.assertTrue(result["triggered"])
        self.assertEqual(result["type"], "free_spins")
        self.assertEqual(result["spins_awarded"], 10)
        self.assertEqual(result["multiplier"], 2.0)

    def test_cbt_not_enough_scatters_for_trigger(self):
        grid = [[5,1,2], [2,5,3], [4,2,1]] # 2 scatters
        bonus_features = {"free_spins": {"trigger_symbol_id": 5, "trigger_count": 3, "spins_awarded": 10, "multiplier": 2.0}}
        result = check_bonus_trigger(grid, 5, bonus_features)
        self.assertFalse(result["triggered"])

    def test_cbt_no_free_spins_config(self):
        grid = [[5,1,5], [2,5,3], [4,2,1]]
        result = check_bonus_trigger(grid, 5, {}) # Empty bonus_features
        self.assertFalse(result["triggered"])

    # --- Tests for handle_cascade_fill ---
    def test_hcf_fall_from_top(self):
        # Grid *before* winning symbols are removed by handle_cascade_fill
        grid_before_clear = [[1, 99, 3], [98, 2, 97], [3, 96, 1]]
        winning_coords = [[0,1], [1,0], [1,2], [2,1]] # Coordinates of 99, 98, 97, 96

        db_syms = [MockSlotSymbol(10), MockSlotSymbol(11), MockSlotSymbol(1), MockSlotSymbol(2), MockSlotSymbol(3)]
        cfg_sym_map = {
            1: {"id": 1, "weight":1}, 2: {"id": 2, "weight":1}, 3: {"id": 3, "weight":1},
            10: {"id": 10, "name": "New1", "weight": 1},
            11: {"id": 11, "name": "New2", "weight": 1}
        }

        with patch('secrets.SystemRandom.choices', side_effect=[[10], [11,10], [11]]):
             new_grid = handle_cascade_fill(grid_before_clear, winning_coords, "fall_from_top", db_syms, cfg_sym_map, None, None)

        expected_grid = [[10,11,11], [1,10,3], [3,2,1]]
        self.assertEqual(new_grid, expected_grid)


    def test_hcf_replace_in_place(self):
        grid_before_clear = [[1,1,1], [2,88,2], [3,3,89]]
        winning_coords = [[1,1], [2,2]]
        db_syms = [MockSlotSymbol(10), MockSlotSymbol(11), MockSlotSymbol(1), MockSlotSymbol(2), MockSlotSymbol(3), MockSlotSymbol(88), MockSlotSymbol(89)]
        cfg_sym_map = {
            1: {"id": 1, "weight":1}, 2: {"id": 2, "weight":1}, 3: {"id": 3, "weight":1},
            88:{"id":88, "weight":1}, 89:{"id":89, "weight":1},
            10: {"id": 10, "name": "NewA", "weight": 1},
            11: {"id": 11, "name": "NewB", "weight": 1}
        }

        with patch('secrets.SystemRandom.choices', return_value=[10, 11]):
            new_grid = handle_cascade_fill(grid_before_clear, winning_coords, "replace_in_place", db_syms, cfg_sym_map, None, None)

        expected_grid = [[1,1,1], [2,10,2], [3,3,11]]
        self.assertEqual(new_grid, expected_grid)


    def test_hcf_no_winning_coords(self):
        grid = [[1,2,3],[4,5,1],[2,3,4]]
        original_grid_copy = [row[:] for row in grid]
        new_grid = handle_cascade_fill(grid, [], "fall_from_top", self.db_symbols_simple, self.config_symbols_map_simple, None, None)
        self.assertEqual(new_grid, original_grid_copy)


if __name__ == '__main__':
    unittest.main()
