import random
from flask import current_app

# European Roulette: numbers 0-36
ROULETTE_NUMBERS = list(range(37)) # 0 to 36

# Define colors for numbers (0 is green, 1-10 and 19-28 odd are red, even are black, etc.)
RED_NUMBERS = {1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36}
BLACK_NUMBERS = {2, 4, 6, 8, 10, 11, 13, 15, 17, 20, 22, 24, 26, 28, 29, 31, 33, 35}
GREEN_NUMBER = {0}

# Payout multipliers
PAYOUTS = {
    "straight_up": 35,  # Bet on a single number
    "split": 17,        # Bet on two adjacent numbers
    "street": 11,       # Bet on a row of three numbers
    "corner": 8,        # Bet on four numbers that form a square
    "six_line": 5,      # Bet on two adjacent rows (six numbers)
    "column": 2,        # Bet on one of the three columns
    "dozen": 2,         # Bet on one of three dozens (1-12, 13-24, 25-36)
    "even_money": 1     # Red/Black, Even/Odd, 1-18/19-36
}

def spin_wheel():
    """Simulates spinning the roulette wheel. Returns a random winning number (0-36)."""
    import secrets
    secure_random = secrets.SystemRandom()
    return secure_random.choice(ROULETTE_NUMBERS)

def get_bet_type_multiplier(bet_type: str, bet_value, winning_number: int) -> int:
    """
    Calculates the payout multiplier for a given bet type and winning number.
    bet_type: e.g., "straight_up", "red", "even", "column_1", "dozen_1", "number_7"
    bet_value: The specific number or group chosen by the player for certain bet types.
               For "straight_up", it's the number itself (e.g., 7).
               For "column", it's the column number (1, 2, or 3).
               For "dozen", it's the dozen number (1, 2, or 3).
               For color/even/odd etc., this might not be needed or can be implicit.
    winning_number: The number that resulted from the wheel spin.
    Returns the multiplier (e.g., 35 for straight_up) if the bet wins, otherwise 0.
    """
    if winning_number not in ROULETTE_NUMBERS:
        raise ValueError("Invalid winning number")

    # Straight up bet (e.g., bet_type="straight_up", bet_value=7)
    if bet_type == "straight_up":
        if winning_number == int(bet_value):
            return PAYOUTS["straight_up"]
        return 0

    # Red/Black (e.g., bet_type="red")
    if bet_type == "red":
        return PAYOUTS["even_money"] if winning_number in RED_NUMBERS else 0
    if bet_type == "black":
        return PAYOUTS["even_money"] if winning_number in BLACK_NUMBERS else 0

    # Even/Odd (e.g., bet_type="even")
    if bet_type == "even": # 0 is not even or odd for payout purposes
        return PAYOUTS["even_money"] if winning_number != 0 and winning_number % 2 == 0 else 0
    if bet_type == "odd":
        return PAYOUTS["even_money"] if winning_number % 2 != 0 else 0 # 0 is not odd

    # Low (1-18) / High (19-36) (e.g., bet_type="low")
    if bet_type == "low":
        return PAYOUTS["even_money"] if 1 <= winning_number <= 18 else 0
    if bet_type == "high":
        return PAYOUTS["even_money"] if 19 <= winning_number <= 36 else 0

    # Dozens (e.g., bet_type="dozen_1", bet_value=1 for first dozen)
    # Assumes bet_value is 1, 2, or 3
    if bet_type.startswith("dozen_"):
        try:
            dozen = int(bet_value)
            if dozen == 1 and 1 <= winning_number <= 12: return PAYOUTS["dozen"]
            if dozen == 2 and 13 <= winning_number <= 24: return PAYOUTS["dozen"]
            if dozen == 3 and 25 <= winning_number <= 36: return PAYOUTS["dozen"]
            return 0
        except ValueError: # Should not happen if bet_value is validated upstream
            return 0


    # Columns (e.g., bet_type="column_1", bet_value=1 for first column)
    # Assumes bet_value is 1, 2, or 3
    if bet_type.startswith("column_"):
        try:
            column = int(bet_value)
            # Column 1: 1, 4, 7, ..., 34
            # Column 2: 2, 5, 8, ..., 35
            # Column 3: 3, 6, 9, ..., 36
            if winning_number == 0: return 0 # 0 is not in any column
            if column == 1 and winning_number % 3 == 1: return PAYOUTS["column"]
            if column == 2 and winning_number % 3 == 2: return PAYOUTS["column"]
            if column == 3 and winning_number % 3 == 0: return PAYOUTS["column"] # Note: 3,6,9...36 are %3==0
            return 0
        except ValueError:
            return 0

    # Bet types requiring a list of numbers in bet_value
    elif bet_type == "split":
        if not (isinstance(bet_value, list) and len(bet_value) == 2 and all(isinstance(n, int) for n in bet_value)):
            current_app.logger.error(f"Invalid bet_value for split bet: {bet_value}. Expected list of 2 integers.")
            return 0
        return PAYOUTS["split"] if winning_number in bet_value else 0
    elif bet_type == "street":
        if not (isinstance(bet_value, list) and len(bet_value) == 3 and all(isinstance(n, int) for n in bet_value)):
            current_app.logger.error(f"Invalid bet_value for street bet: {bet_value}. Expected list of 3 integers.")
            return 0
        # Additional validation for street might be needed, e.g. numbers are consecutive or form a valid street.
        # For now, just checking if winning_number is in the list.
        return PAYOUTS["street"] if winning_number in bet_value else 0
    elif bet_type == "corner":
        if not (isinstance(bet_value, list) and len(bet_value) == 4 and all(isinstance(n, int) for n in bet_value)):
            current_app.logger.error(f"Invalid bet_value for corner bet: {bet_value}. Expected list of 4 integers.")
            return 0
        # Additional validation for corner might be needed, e.g. numbers form a valid square on the board.
        return PAYOUTS["corner"] if winning_number in bet_value else 0
    elif bet_type == "six_line":
        if not (isinstance(bet_value, list) and len(bet_value) == 6 and all(isinstance(n, int) for n in bet_value)):
            current_app.logger.error(f"Invalid bet_value for six_line bet: {bet_value}. Expected list of 6 integers.")
            return 0
        # Additional validation for six_line might be needed.
        return PAYOUTS["six_line"] if winning_number in bet_value else 0
    # End of newly added bet types. TODO comment updated.
    # Bet types like split, street, corner, six_line implemented above.
    # These complex bet types depend on the layout and specific numbers chosen,
    # and assume bet_value is a list of numbers for these types.
    # Further validation of the bet_value list against actual roulette layout rules
    # (e.g., numbers in a split are adjacent, numbers in a street are consecutive)
    # is not implemented here but may be necessary for a full robust system.

    current_app.logger.warning(f"Unhandled bet_type '{bet_type}' or invalid bet_value '{bet_value}'.")
    return 0


def calculate_payout(bet_amount: float, multiplier: int) -> float:
    """Calculates the total payout (including stake)."""
    return bet_amount * (multiplier + 1) if multiplier > 0 else 0
