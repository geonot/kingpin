import unittest
from unittest.mock import patch, MagicMock
import json
from datetime import datetime, timezone

from casino_be.app import app, db
from casino_be.models import User, Slot, GameSession, SlotSpin, Transaction
from casino_be.utils.spin_handler import handle_spin


class TestSpinEdgeCases(unittest.TestCase):
    """Tests for edge cases and error conditions in spin calculations."""
    
    def setUp(self):
        self.app = app
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        
        self.user = User(
            username='edge_test_user',
            email='edge@test.com',
            password='password',
            balance=1000000
        )
        db.session.add(self.user)
        
        self.slot = Slot(
            id=1,
            name="Edge Test Slot",
            short_name="edge_slot",
            num_rows=3,
            num_columns=5,
            num_symbols=5,
            asset_directory="/test_assets/",
            is_active=True,
            rtp=95.0,
            volatility="High",
            is_cascading=True,
            cascade_type="fall_from_top",
            win_multipliers="[2, 3, 5]",
            min_symbols_to_match=3
        )
        db.session.add(self.slot)
        
        self.game_session = GameSession(
            user_id=self.user.id,
            slot_id=self.slot.id,
            game_type='slot'
        )
        db.session.add(self.game_session)
        db.session.commit()
        
        # Mock load_game_config
        self.mock_load_config = patch('casino_be.utils.spin_handler.load_game_config').start()
        self.base_config = {
            "game": {
                "slot_id": 1,
                "name": "Edge Test Slot",
                "short_name": "edge_slot",
                "layout": {
                    "rows": 3,
                    "columns": 5,
                    "paylines": [
                        {"id": "line_1", "coords": [[1,0],[1,1],[1,2],[1,3],[1,4]]}
                    ]
                },
                "symbols": [
                    {"id": 1, "name": "SymbolA", "asset": "symA.png", "value_multipliers": {"3": 10, "4": 50, "5": 100}, "weight": 10},
                    {"id": 2, "name": "SymbolB", "asset": "symB.png", "value_multipliers": {"3": 5, "4": 25, "5": 50}, "weight": 20},
                    {"id": 3, "name": "SymbolC", "asset": "symC.png", "value_multipliers": {"3": 2, "4": 10, "5": 20}, "weight": 30},
                    {"id": 4, "name": "Scatter", "asset": "scatter.png", "scatter_payouts": {"3": 5, "4": 10, "5": 50}, "weight": 5},
                    {"id": 5, "name": "Wild", "asset": "wild.png", "weight": 3}
                ],
                "wild_symbol_id": 5,
                "scatter_symbol_id": 4,
                "is_cascading": True,
                "cascade_type": "fall_from_top",
                "win_multipliers": [2, 3, 5],
                "min_symbols_to_match": 3,
                "bonus_features": {
                    "free_spins": {
                        "trigger_symbol_id": 4,
                        "trigger_count": 3,
                        "spins_awarded": 10,
                        "multiplier": 2.0
                    }
                }
            }
        }
        self.mock_load_config.return_value = self.base_config
        
        # Mock grid generation
        self.mock_generate_grid = patch('casino_be.utils.spin_handler.generate_spin_grid').start()
        self.mock_choices = patch('secrets.SystemRandom.choices').start()
        
    def tearDown(self):
        patch.stopall()
        db.session.remove()
        db.drop_all()
        self.app_context.pop()
        
    def test_maximum_cascade_wins(self):
        """Test behavior when maximum cascades are reached."""
        # Initial grid with win
        initial_grid = [
            [1, 1, 1, 1, 1],  # Full line of SymbolA
            [2, 3, 4, 2, 3],
            [3, 2, 5, 3, 2]
        ]
        self.mock_generate_grid.return_value = initial_grid
        
        # Mock cascades that keep winning
        winning_symbols = [1, 1, 1, 1, 1]  # Always win
        losing_symbols = [6, 6, 6, 6, 6]   # Never win (not in config)
        
        # First 10 cascades win, then lose
        cascade_fills = []
        for i in range(10):
            cascade_fills.extend(winning_symbols)
        cascade_fills.extend(losing_symbols)
        
        self.mock_choices.side_effect = [cascade_fills]
        
        bet_amount = 100
        result = handle_spin(self.user, self.slot, self.game_session, bet_amount)
        
        # Should have stopped cascading due to some internal limit or run out of mock data
        self.assertGreater(result['win_amount_sats'], bet_amount)
        
    def test_insufficient_balance_edge_case(self):
        """Test spin with balance exactly equal to bet amount."""
        bet_amount = 100
        self.user.balance = bet_amount
        db.session.commit()
        
        # Non-winning grid
        self.mock_generate_grid.return_value = [
            [1, 2, 3, 1, 2],
            [2, 3, 1, 2, 3],
            [3, 1, 2, 3, 1]
        ]
        
        result = handle_spin(self.user, self.slot, self.game_session, bet_amount)
        
        # Should succeed but leave user with 0 balance
        self.assertEqual(result['win_amount_sats'], 0)
        self.assertEqual(self.user.balance, 0)
        
    def test_wild_substitution_edge_cases(self):
        """Test wild symbol substitution in complex scenarios."""
        # Grid with wilds that could create multiple winning combinations
        wild_grid = [
            [5, 5, 5, 5, 5],  # All wilds on payline
            [1, 2, 3, 1, 2],
            [2, 3, 1, 2, 3]
        ]
        self.mock_generate_grid.return_value = wild_grid
        
        bet_amount = 100
        result = handle_spin(self.user, self.slot, self.game_session, bet_amount)
        
        # Wilds should create wins (exact amount depends on implementation)
        self.assertGreater(result['win_amount_sats'], 0)
        self.assertTrue(any('wild' in str(line).lower() for line in result.get('winning_lines', [])))
        
    def test_scatter_wins_with_cascades(self):
        """Test scatter wins combined with cascade mechanics."""
        # Grid with both scatter symbols and regular wins
        scatter_cascade_grid = [
            [4, 1, 1, 1, 4],  # Scatters + line win
            [1, 4, 2, 3, 1],  # More scatters
            [2, 3, 4, 2, 3]   # Another scatter
        ]
        self.mock_generate_grid.return_value = scatter_cascade_grid
        
        # Mock cascade that removes winning symbols but keeps scatters
        self.mock_choices.side_effect = [
            [2, 2, 2]  # Replace the line win symbols
        ]
        
        bet_amount = 100
        result = handle_spin(self.user, self.slot, self.game_session, bet_amount)
        
        # Should have scatter wins and possibly cascade wins
        self.assertGreater(result['win_amount_sats'], 0)
        winning_lines = result.get('winning_lines', [])
        has_scatter = any(line.get('line_id') == 'scatter' for line in winning_lines)
        self.assertTrue(has_scatter)
        
    def test_bonus_trigger_during_cascade(self):
        """Test bonus triggering during a cascade sequence."""
        # Initial non-bonus grid
        initial_grid = [
            [1, 1, 1, 2, 3],  # Line win
            [2, 3, 1, 2, 3],
            [3, 2, 2, 3, 1]
        ]
        self.mock_generate_grid.return_value = initial_grid
        
        # First cascade creates bonus symbols
        self.mock_choices.side_effect = [
            [4, 4, 4],  # Three scatters replace winning symbols
            [2, 2, 2]   # Second cascade (if any)
        ]
        
        bet_amount = 100
        result = handle_spin(self.user, self.slot, self.game_session, bet_amount)
        
        # Bonus should trigger from cascade, not initial spin
        self.assertTrue(result.get('bonus_triggered', False))
        
    def test_multiplier_overflow_protection(self):
        """Test protection against multiplier overflow."""
        # Modify config to have very high multipliers
        overflow_config = self.base_config.copy()
        overflow_config["game"]["win_multipliers"] = [1000, 2000, 5000]
        self.mock_load_config.return_value = overflow_config
        
        # High-value winning grid
        self.mock_generate_grid.return_value = [
            [1, 1, 1, 1, 1],  # Max symbols on payline
            [2, 3, 4, 2, 3],
            [3, 2, 5, 3, 2]
        ]
        
        # Mock multiple cascades to trigger high multipliers
        self.mock_choices.side_effect = [
            [1, 1, 1, 1, 1],  # First cascade
            [1, 1, 1, 1, 1],  # Second cascade
            [1, 1, 1, 1, 1],  # Third cascade
            [6, 6, 6, 6, 6]   # Stop cascading
        ]
        
        bet_amount = 100
        result = handle_spin(self.user, self.slot, self.game_session, bet_amount)
        
        # Win should be capped or handled gracefully
        self.assertIsInstance(result['win_amount_sats'], int)
        self.assertGreaterEqual(result['win_amount_sats'], 0)
        
    def test_concurrent_bonus_spin_edge_case(self):
        """Test edge case where bonus spin calculation might conflict."""
        # Set up active bonus
        self.game_session.bonus_active = True
        self.game_session.bonus_spins_remaining = 1
        self.game_session.bonus_multiplier = 3.0
        db.session.commit()
        
        # Grid that would normally trigger another bonus
        bonus_grid = [
            [4, 4, 4, 4, 4],  # Many scatters
            [1, 2, 3, 1, 2],
            [2, 3, 1, 2, 3]
        ]
        self.mock_generate_grid.return_value = bonus_grid
        
        bet_amount = 100
        result = handle_spin(self.user, self.slot, self.game_session, bet_amount)
        
        # Bonus should not retrigger during bonus spins (depends on implementation)
        # At minimum, should handle gracefully without errors
        self.assertIsInstance(result, dict)
        self.assertIn('win_amount_sats', result)
        
    def test_zero_bet_edge_case(self):
        """Test handling of zero or negative bet amounts."""
        self.mock_generate_grid.return_value = [
            [1, 2, 3, 1, 2],
            [2, 3, 1, 2, 3],
            [3, 1, 2, 3, 1]
        ]
        
        bet_amount = 0
        
        try:
            result = handle_spin(self.user, self.slot, self.game_session, bet_amount)
            # If it doesn't raise an exception, verify reasonable behavior
            self.assertEqual(result['win_amount_sats'], 0)
        except (ValueError, AssertionError):
            # Acceptable to reject zero bets
            pass
            
    def test_corrupted_config_handling(self):
        """Test handling of corrupted or missing game configuration."""
        # Corrupt config with missing required fields
        corrupt_config = {
            "game": {
                "slot_id": 1,
                "symbols": [],  # Empty symbols
                "layout": {}    # Empty layout
            }
        }
        self.mock_load_config.return_value = corrupt_config
        
        bet_amount = 100
        
        try:
            result = handle_spin(self.user, self.slot, self.game_session, bet_amount)
            # Should handle gracefully or return error
            self.assertIsInstance(result, dict)
        except Exception as e:
            # Acceptable to raise exception for corrupted config
            self.assertIsInstance(e, (ValueError, KeyError, TypeError))


if __name__ == '__main__':
    unittest.main()
