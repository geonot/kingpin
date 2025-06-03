# casino_be/utils/plinko_helper.py

# (No model imports needed for this subtask, use comments for DB interaction points)

# --- Constants ---
PAYOUT_MULTIPLIERS = {
    '0.5x': 0.5,
    '2x': 2.0,
    '5x': 5.0,
}

STAKE_CONFIG = {
    'Low': {'min_bet': 0.10, 'max_bet': 1.00, 'color': 'green'},
    'Medium': {'min_bet': 1.01, 'max_bet': 5.00, 'color': 'yellow'},
    'High': {'min_bet': 5.01, 'max_bet': 20.00, 'color': 'red'}
}

# --- Functions ---
def get_stake_options():
    """
    Returns a simplified dictionary of stake options for the frontend.
    """
    return {label: {'color': STAKE_CONFIG[label]['color']} for label in STAKE_CONFIG}

def validate_plinko_params(stake_amount, chosen_stake_label, slot_landed_label):
    """
    Validates Plinko game parameters using global STAKE_CONFIG and PAYOUT_MULTIPLIERS.
    Returns a dictionary {'success': True} or {'success': False, 'error': 'message'}.
    """
    if chosen_stake_label not in STAKE_CONFIG:
        return {'success': False, 'error': f"Invalid stake label '{chosen_stake_label}'. Valid labels are: {list(STAKE_CONFIG.keys())}"}

    tier_config = STAKE_CONFIG[chosen_stake_label]
    
    try:
        current_stake_amount = float(stake_amount)
    except ValueError:
        return {'success': False, 'error': f"Invalid stake amount format: '{stake_amount}'. Must be a number."}

    if not (tier_config['min_bet'] <= current_stake_amount <= tier_config['max_bet']):
        return {'success': False, 'error': f"Stake amount {current_stake_amount} out of range for {chosen_stake_label} tier ({tier_config['min_bet']}-{tier_config['max_bet']})."}

    if slot_landed_label not in PAYOUT_MULTIPLIERS:
        return {'success': False, 'error': f"Invalid slot landed label '{slot_landed_label}'. Valid labels are: {list(PAYOUT_MULTIPLIERS.keys())}"}
    
    return {'success': True}


def calculate_winnings(stake_amount_sats, slot_landed_label):
    """
    Calculates winnings based on stake amount in satoshis and the slot landed label.
    Uses the global PAYOUT_MULTIPLIERS.
    Returns winnings in satoshis (integer).
    Note: Assumes parameters have been validated by schema or validate_plinko_params.
    """
    multiplier = PAYOUT_MULTIPLIERS.get(slot_landed_label)
    if multiplier is None:
        # This should ideally not be reached if params are pre-validated.
        print(f"Critical Error: Invalid slot label '{slot_landed_label}' in calculate_winnings.")
        return 0 # Return integer satoshis
    
    try:
        # Ensure stake_amount_sats is an integer (or can be treated as such)
        current_stake_sats = int(stake_amount_sats)
    except ValueError:
        print(f"Critical Error: Invalid stake_amount_sats format '{stake_amount_sats}' in calculate_winnings.")
        return 0 # Return integer satoshis
        
    # Perform calculation and ensure the result is an integer (satoshis)
    # Floating point precision with multipliers can be an issue, round appropriately if needed,
    # but for simple multipliers like 0.5, 2, 5, direct multiplication then int conversion should be fine.
    # For more complex multipliers (e.g. 0.33), careful handling of fractions of satoshis would be needed.
    # Here, we assume standard multipliers that result in whole or easily convertible satoshis.
    return int(current_stake_sats * multiplier)


# Example Usage (can be commented out or removed for production)
if __name__ == '__main__':
    print("--- Stake Options ---")
    print(get_stake_options())

    print("\n--- Testing validate_plinko_params ---")
    print(f"Valid params (1.0, Low, 2x): {validate_plinko_params(1.0, 'Low', '2x')}")
    print(f"Invalid stake label (VeryLow): {validate_plinko_params(1.0, 'VeryLow', '2x')}")
    print(f"Invalid stake amount format (abc): {validate_plinko_params('abc', 'Low', '2x')}")
    print(f"Stake out of range (0.05, Low): {validate_plinko_params(0.05, 'Low', '2x')}")
    print(f"Stake out of range (1.50, Low): {validate_plinko_params(1.50, 'Low', '2x')}")
    print(f"Invalid slot label (100x): {validate_plinko_params(2.0, 'Medium', '100x')}")

    print("\n--- Testing calculate_winnings (input/output in satoshis) ---")
    # These tests assume valid inputs as `validate_plinko_params` would be called first for other params.
    # Input stake is now in satoshis.
    print(f"Stake 1000 sats, Slot '2x': Winnings = {calculate_winnings(1000, '2x')} sats") # Expected 2000
    print(f"Stake 1000 sats, Slot '0.5x': Winnings = {calculate_winnings(1000, '0.5x')} sats") # Expected 500
    # Test with an invalid slot label
    print(f"Stake 1000 sats, Slot 'invalid_for_calc': Winnings = {calculate_winnings(1000, 'invalid_for_calc')} sats") # Expected 0
    # Test with invalid stake_amount format (though schema/validation should catch this before this point)
    # print(f"Stake 'abc_sats', Slot '2x': Winnings = {calculate_winnings('abc_sats', '2x')} sats") # Expected 0


    print("\n--- Simulating API call flow using refactored functions ---")
    test_scenarios = [
        (1.0, 'Low', '2x'),             # Valid
        (0.05, 'Low', '2x'),            # Stake too low
        (2.0, 'Medium', '0.5x'),        # Valid
        (10.0, 'High', '5x'),           # Valid
        (5.0, 'Medium', 'nonexistent'), # Invalid slot
        ("bad_stake", 'Medium', '2x')   # Invalid stake format
    ]

    for stake, label, slot in test_scenarios:
        print(f"\nTesting with: Stake={stake}, Label='{label}', Slot='{slot}'")
        validation_result = validate_plinko_params(stake, label, slot)
        print(f"Validation Result: {validation_result}")

        if validation_result['success']:
            # Simulate actions that would happen in the API endpoint
            simulated_user_balance = 100.0  # Reset for each scenario for simplicity
            print(f"  Simulated current balance: {simulated_user_balance}")

            # Assume stake is float from validation, convert to sats for internal logic
            SATOSHIS_PER_UNIT_TEST = 100_000_000 # Example, align with actual app logic
            
            try:
                stake_float_from_validation = float(stake)
            except ValueError:
                 print(f"  Invalid stake format for scenario: {stake}")
                 continue

            stake_sats_for_logic = int(stake_float_from_validation * SATOSHIS_PER_UNIT_TEST)
            
            simulated_user_balance_sats = 100 * SATOSHIS_PER_UNIT_TEST # e.g., 100 units in satoshis
            print(f"  Simulated current balance: {simulated_user_balance_sats} sats")


            if simulated_user_balance_sats >= stake_sats_for_logic:
                simulated_user_balance_sats -= stake_sats_for_logic
                print(f"  Simulated balance after debit: {simulated_user_balance_sats} sats")
                
                winnings_sats_value = calculate_winnings(stake_sats_for_logic, slot)
                print(f"  Calculated winnings: {winnings_sats_value} sats")
                
                simulated_user_balance_sats += winnings_sats_value
                print(f"  Simulated final balance: {simulated_user_balance_sats} sats")
                
                # API response would typically be in main unit (float) or both
                winnings_float_for_response = winnings_sats_value / SATOSHIS_PER_UNIT_TEST
                new_balance_float_for_response = simulated_user_balance_sats / SATOSHIS_PER_UNIT_TEST
                print(f"  API-like Response: success=True, winnings={winnings_float_for_response}, new_balance={new_balance_float_for_response}, message='Processed'")
            else:
                print(f"  API-like Response: success=False, error='Insufficient funds', current_balance_sats={simulated_user_balance_sats}")
        else:
            print(f"  API-like Response: success=False, error='{validation_result.get('error')}'")
# Note: Removed trailing ``` from the original file content that was causing SyntaxError.
