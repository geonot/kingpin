import unittest
from casino_be.utils.plinko_helper import (
    validate_plinko_params,
    calculate_winnings,
    get_stake_options,
    STAKE_CONFIG,
    PAYOUT_MULTIPLIERS
)
from casino_be.app import app # Add this import

class TestPlinkoHelper(unittest.TestCase):

    def setUp(self):
        self.app_context = app.app_context()
        self.app_context.push()

    def tearDown(self):
        if self.app_context:
            self.app_context.pop()

    def test_get_stake_options(self):
        options = get_stake_options()
        self.assertIsInstance(options, dict)
        for tier, config in STAKE_CONFIG.items():
            self.assertIn(tier, options)
            self.assertEqual(options[tier]['color'], config['color'])

    def test_validate_plinko_params_valid(self):
        # Test valid parameters for each tier
        self.assertTrue(validate_plinko_params(0.5, 'Low', '0.5x')['success'])
        self.assertTrue(validate_plinko_params(1.0, 'Low', '2x')['success'])
        
        self.assertTrue(validate_plinko_params(2.0, 'Medium', '5x')['success'])
        self.assertTrue(validate_plinko_params(5.0, 'Medium', '0.5x')['success'])

        self.assertTrue(validate_plinko_params(10.0, 'High', '2x')['success'])
        self.assertTrue(validate_plinko_params(20.0, 'High', '5x')['success'])

    def test_validate_plinko_params_invalid_stake_label(self):
        result = validate_plinko_params(1.0, 'InvalidTier', '0.5x')
        self.assertFalse(result['success'])
        self.assertIn("Invalid stake label", result['error'])

    def test_validate_plinko_params_invalid_stake_amount_format(self):
        result = validate_plinko_params("not_a_number", 'Low', '0.5x')
        self.assertFalse(result['success'])
        self.assertIn("Invalid stake amount format", result['error'])

    def test_validate_plinko_params_stake_amount_out_of_range(self):
        # Low Tier
        result_low_min = validate_plinko_params(0.05, 'Low', '0.5x') # Below min
        self.assertFalse(result_low_min['success'])
        self.assertIn("out of range for Low tier", result_low_min['error'])

        result_low_max = validate_plinko_params(1.01, 'Low', '0.5x') # Above max
        self.assertFalse(result_low_max['success'])
        self.assertIn("out of range for Low tier", result_low_max['error'])

        # Medium Tier
        result_medium_min = validate_plinko_params(1.00, 'Medium', '0.5x')
        self.assertFalse(result_medium_min['success'])
        self.assertIn("out of range for Medium tier", result_medium_min['error'])

        result_medium_max = validate_plinko_params(5.01, 'Medium', '0.5x')
        self.assertFalse(result_medium_max['success'])
        self.assertIn("out of range for Medium tier", result_medium_max['error'])

        # High Tier
        result_high_min = validate_plinko_params(5.00, 'High', '0.5x')
        self.assertFalse(result_high_min['success'])
        self.assertIn("out of range for High tier", result_high_min['error'])

        result_high_max = validate_plinko_params(20.01, 'High', '0.5x')
        self.assertFalse(result_high_max['success'])
        self.assertIn("out of range for High tier", result_high_max['error'])

    def test_validate_plinko_params_invalid_slot_label(self):
        result = validate_plinko_params(1.0, 'Low', '100x') # Invalid slot
        self.assertFalse(result['success'])
        self.assertIn("Invalid slot landed label", result['error'])

    def test_calculate_winnings(self):
        # Test with valid multipliers and stake amounts (in satoshis)
        # Assuming PAYOUT_MULTIPLIERS is available in this scope
        self.assertEqual(calculate_winnings(1000, '0.5x'), 500) # 1000 * 0.5
        self.assertEqual(calculate_winnings(1000, '2x'), 2000)   # 1000 * 2
        self.assertEqual(calculate_winnings(1000, '5x'), 5000)   # 1000 * 5
        
        # Test with different stake amount
        self.assertEqual(calculate_winnings(500, '2x'), 1000)    # 500 * 2

        # Test with zero stake amount
        self.assertEqual(calculate_winnings(0, '2x'), 0)

        # Test with invalid slot landed label (should return 0)
        self.assertEqual(calculate_winnings(1000, 'invalid_slot'), 0)
        
        # Test with non-integer stake amount (should be handled by int conversion, or error if not convertible)
        # The function now expects integer satoshis, so float inputs that are whole numbers are fine.
        self.assertEqual(calculate_winnings(1000.0, '2x'), 2000) 
        # String that can be int()
        self.assertEqual(calculate_winnings("1000", '2x'), 2000) 

    def test_calculate_winnings_invalid_stake_format(self):
        # Test with stake amount that cannot be converted to int
        # The function prints an error and returns 0 in this case.
        self.assertEqual(calculate_winnings("abc", '2x'), 0)


if __name__ == '__main__':
    unittest.main()
