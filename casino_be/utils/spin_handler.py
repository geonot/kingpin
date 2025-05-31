import random
from datetime import datetime, timezone
from models import db, SlotSpin, SlotSymbol

# --- Configuration ---
MIN_MATCH_FOR_PAYLINE_WIN = 3
MIN_MATCH_FOR_SCATTER_WIN = 3
SCATTER_PAY_MULTIPLIER_BASE = 2 # Multiplier per scatter symbol (e.g., 3 scatters = bet * 3 * base)

def handle_spin(user, slot, game_session, bet_amount_sats):
    """
    Handles the logic for a single slot machine spin.

    Args:
        user (User): The user performing the spin.
        slot (Slot): The slot machine being played.
        game_session (GameSession): The current active game session.
        bet_amount_sats (int): The amount bet in Satoshis.

    Returns:
        dict: A dictionary containing the results of the spin.
              Includes spin_result, win_amount_sats, winning_lines, bonus info, etc.

    Raises:
        ValueError: If the bet amount is invalid or user has insufficient balance (redundant check).
    """
    # --- Pre-Spin Validation ---
    if not isinstance(bet_amount_sats, int) or bet_amount_sats <= 0:
        raise ValueError("Invalid bet amount. Must be a positive integer (satoshis).")

    # Redundant balance check (already done in route), but good for safety
    if user.balance < bet_amount_sats:
        raise ValueError("Insufficient balance for this bet.")

    # --- Determine Spin Type and Deduct Bet ---
    is_bonus_spin = False
    current_multiplier = 1.0

    if game_session.bonus_active and game_session.bonus_spins_remaining > 0:
        is_bonus_spin = True
        current_multiplier = game_session.bonus_multiplier
        game_session.bonus_spins_remaining -= 1
        # Don't deduct bet during a bonus spin
    else:
        # This is a normal spin, deduct the bet
        user.balance -= bet_amount_sats
        # Log the wager transaction? Maybe aggregate later.

    # --- Generate Spin Result ---
    # Fetch symbols for weighting (could be cached or preloaded)
    symbols = slot.symbols # Assumes eager loading via lazy='joined'
    if not symbols:
        raise RuntimeError(f"No symbols found for slot ID {slot.id}. Cannot generate spin.")

    # Note: num_symbols in Slot table should match len(symbols)
    spin_result_grid = generate_spin_grid(slot.num_rows, slot.num_columns, symbols, slot.wild_symbol_id, slot.scatter_symbol_id)

    # --- Calculate Wins ---
    paylines = define_paylines(slot.num_rows, slot.num_columns) # Get payline definitions
    win_info = calculate_win(
        spin_result_grid,
        paylines,
        symbols, # Pass full symbol objects
        bet_amount_sats,
        slot.wild_symbol_id,
        slot.scatter_symbol_id
    )

    win_amount_sats = win_info['total_win_sats']
    winning_lines = win_info['winning_lines'] # List of WinLineSchema structure

    # --- Apply Bonus Multiplier ---
    if is_bonus_spin:
        win_amount_sats = int(win_amount_sats * current_multiplier) # Apply multiplier to the win

    # --- Check for Bonus Trigger (on non-bonus spins) ---
    bonus_triggered = False
    if not is_bonus_spin:
        bonus_triggered = check_bonus_trigger(
            spin_result_grid,
            slot.scatter_symbol_id,
            slot.bonus_type,
            slot.bonus_spins_trigger_count
        )

    # --- Update Session State ---
    # Start bonus if triggered and not already active
    if bonus_triggered and not game_session.bonus_active:
        game_session.bonus_active = True
        # Reset spins/multiplier based on slot config
        game_session.bonus_spins_remaining = slot.bonus_spins_awarded
        game_session.bonus_multiplier = slot.bonus_multiplier # Use the slot's configured bonus multiplier
        current_multiplier = game_session.bonus_multiplier # Update current multiplier for response data
    # End bonus if active and spins run out
    elif game_session.bonus_active and game_session.bonus_spins_remaining <= 0:
        game_session.bonus_active = False
        game_session.bonus_multiplier = 1.0 # Reset multiplier
        current_multiplier = 1.0 # Update current multiplier for response data

    # Update session aggregates
    game_session.num_spins += 1
    if not is_bonus_spin: # Only count wager on non-bonus spins
        game_session.amount_wagered += bet_amount_sats
    game_session.amount_won += win_amount_sats

    # --- Update User Balance ---
    if win_amount_sats > 0:
        user.balance += win_amount_sats
        # Log win transaction?

    # --- Create Spin Record ---
    new_spin = SlotSpin(
        game_session_id=game_session.id,
        spin_result=spin_result_grid,
        win_amount=win_amount_sats,
        bet_amount=bet_amount_sats if not is_bonus_spin else 0, # Record 0 bet for bonus spins
        is_bonus_spin=is_bonus_spin,
        spin_time=datetime.now(timezone.utc)
    )
    db.session.add(new_spin)
    # Note: Commit happens in the calling route (app.py)

    # --- Return Results ---
    return {
        "spin_result": spin_result_grid,
        "win_amount_sats": win_amount_sats,
        "winning_lines": winning_lines,
        "bonus_triggered": bonus_triggered,
        "bonus_active": game_session.bonus_active,
        "bonus_spins_remaining": game_session.bonus_spins_remaining if game_session.bonus_active else 0,
        "bonus_multiplier": current_multiplier, # Return the multiplier active during THIS spin
        "game_session": game_session, # Pass back session object for route to serialize
        "user": user # Pass back user object for route to serialize
    }

def generate_spin_grid(rows, columns, symbols, wild_symbol_internal_id, scatter_symbol_internal_id):
    """
    Generates a grid of symbol internal IDs based on weighted probabilities.
    Symbols list contains SlotSymbol objects.
    """
    if not symbols:
        return [[1 for _ in range(columns)] for _ in range(rows)] # Fallback

    symbol_ids = [s.symbol_internal_id for s in symbols]
    num_distinct_symbols = len(symbol_ids)

    # --- Simple Weighting Example ---
    # Give lower probability to wild and scatter, slightly higher to high-value symbols
    # This needs significant tuning based on desired RTP and volatility.
    # TODO: Load weights from Slot configuration or a dedicated weighting table.
    weights = []
    total_value = sum(s.value_multiplier or 0 for s in symbols if s.value_multiplier)
    avg_value = total_value / len([s for s in symbols if s.value_multiplier]) if total_value > 0 else 1

    for symbol in symbols:
        s_id = symbol.symbol_internal_id
        value = symbol.value_multiplier or 0

        if s_id == wild_symbol_internal_id:
            weights.append(0.5) # Lower weight for wild
        elif s_id == scatter_symbol_internal_id:
            weights.append(0.4) # Lower weight for scatter
        elif value > avg_value * 1.5: # Higher value symbols
             weights.append(1.5)
        else: # Standard symbols
            weights.append(1.0)

    # Normalize weights
    total_weight = sum(weights)
    if total_weight == 0: # Prevent division by zero if all weights are 0
        weights = [1.0 / num_distinct_symbols] * num_distinct_symbols
    else:
        weights = [w / total_weight for w in weights]
    # --- End Weighting Example ---

    # Generate grid using weighted random choice
    grid = []
    for r in range(rows):
        row_symbols = []
        for c in range(columns):
            chosen_symbol_id = random.choices(symbol_ids, weights=weights, k=1)[0]
            row_symbols.append(chosen_symbol_id)
        grid.append(row_symbols)

    return grid


def define_paylines(rows, columns):
    """
    Defines standard paylines for common grid sizes.
    Returns a list of lists, where each inner list contains [row, col] coordinates.
    """
    # TODO: Load paylines from Slot configuration or database table.
    if rows == 3 and columns == 5:
        # Common 20-25 paylines for a 3x5 slot (example uses 10)
        return [
            # Horizontal Lines
            [[0, 0], [0, 1], [0, 2], [0, 3], [0, 4]],  # Line 0: Top row
            [[1, 0], [1, 1], [1, 2], [1, 3], [1, 4]],  # Line 1: Middle row
            [[2, 0], [2, 1], [2, 2], [2, 3], [2, 4]],  # Line 2: Bottom row
            # Diagonal / V Shapes
            [[0, 0], [1, 1], [2, 2], [1, 3], [0, 4]],  # Line 3: V shape
            [[2, 0], [1, 1], [0, 2], [1, 3], [2, 4]],  # Line 4: Inverted V
            # Zigzag Shapes
            [[0, 0], [0, 1], [1, 2], [2, 3], [2, 4]],  # Line 5
            [[2, 0], [2, 1], [1, 2], [0, 3], [0, 4]],  # Line 6
            [[1, 0], [0, 1], [0, 2], [0, 3], [1, 4]],  # Line 7 (Shallow U)
            [[1, 0], [2, 1], [2, 2], [2, 3], [1, 4]],  # Line 8 (Deep U)
            # More complex shapes
            [[0, 0], [1, 1], [0, 2], [1, 3], [0, 4]],  # Line 9 (W shape type)
            # Add more paylines up to 20 or 25...
        ]
    # Add patterns for other grid sizes if supported
    elif rows == 4 and columns == 5:
        # Define paylines for 4x5 grid...
        return [] # Placeholder
    else:
        # Default or error for unsupported sizes
        return []

def get_payout_multiplier(symbol_internal_id, consecutive_count, symbols):
    """
    Determines the payout multiplier based on the symbol and count.
    This should ideally query a payout table (SlotPayout model).
    Using a simplified placeholder logic here.
    """
    # TODO: Replace with database lookup (SlotPayout table)
    # Payouts usually depend on symbol AND count (e.g., 3x, 4x, 5x)

    symbol = next((s for s in symbols if s.symbol_internal_id == symbol_internal_id), None)
    if not symbol or not symbol.value_multiplier:
        return 0.0 # No payout for this symbol

    base_multiplier = symbol.value_multiplier

    # Example exponential increase (adjust formula based on desired payouts)
    if consecutive_count == 3:
        return base_multiplier * 1.0
    elif consecutive_count == 4:
        return base_multiplier * 2.5
    elif consecutive_count == 5:
        return base_multiplier * 5.0
    # Add more cases if columns > 5
    else:
        return 0.0 # No win for less than 3 consecutive


def calculate_win(grid, paylines, symbols, bet_amount_sats, wild_symbol_internal_id, scatter_symbol_internal_id):
    """
    Calculates total win amount and identifies winning lines based on the grid and paylines.

    Args:
        grid (list[list[int]]): The grid of symbol internal IDs.
        paylines (list[list[list[int]]]): List of payline coordinates.
        symbols (list[SlotSymbol]): List of SlotSymbol objects for the slot.
        bet_amount_sats (int): The bet amount in Satoshis.
        wild_symbol_internal_id (int | None): The internal ID of the wild symbol.
        scatter_symbol_internal_id (int | None): The internal ID of the scatter symbol.

    Returns:
        dict: Contains 'total_win_sats' and 'winning_lines' (list of WinLineSchema dicts).
    """
    total_win_sats = 0
    winning_lines_data = []
    num_rows = len(grid)
    num_cols = len(grid[0]) if num_rows > 0 else 0

    # --- Payline Wins ---
    for line_idx, payline_coords in enumerate(paylines):
        line_symbols = []
        line_positions = []

        # Get symbols and positions along the payline
        for r, c in payline_coords:
            if 0 <= r < num_rows and 0 <= c < num_cols:
                symbol_id = grid[r][c]
                line_symbols.append(symbol_id)
                line_positions.append([r, c])
            else:
                # Payline coordinate out of bounds (should not happen with valid config)
                line_symbols.append(None) # Use None as placeholder
                line_positions.append(None)

        # Check for wins starting from the left-most reel
        first_symbol = line_symbols[0]
        if first_symbol is None or first_symbol == scatter_symbol_internal_id:
            continue # Paylines don't start with scatter or out-of-bounds

        consecutive_count = 0
        match_symbol_id = None
        winning_positions_on_line = []

        # Determine the symbol to match (handle wild at start)
        if first_symbol == wild_symbol_internal_id:
            # Find first non-wild symbol to determine matching type
            first_non_wild_idx = -1
            for i in range(1, len(line_symbols)):
                if line_symbols[i] is not None and line_symbols[i] != wild_symbol_internal_id and line_symbols[i] != scatter_symbol_internal_id:
                    match_symbol_id = line_symbols[i]
                    first_non_wild_idx = i
                    break
            if match_symbol_id is None: # Line consists only of wilds (and maybe scatters)
                 # Treat as win of highest paying standard symbol? Or specific wild payout?
                 # For simplicity, let's assign a high-value symbol or skip if no rule defined.
                 # Find highest value symbol:
                 highest_value_symbol = max((s for s in symbols if s.value_multiplier and s.symbol_internal_id != scatter_symbol_internal_id), key=lambda x: x.value_multiplier, default=None)
                 if highest_value_symbol:
                    match_symbol_id = highest_value_symbol.symbol_internal_id
                 else:
                    continue # No standard symbols to match wild against

            # Count consecutive wilds up to the first non-wild (or end of line)
            consecutive_count = first_non_wild_idx if first_non_wild_idx != -1 else len(line_symbols)
            winning_positions_on_line.extend(line_positions[:consecutive_count])

        else:
            # First symbol is a standard symbol
            match_symbol_id = first_symbol
            consecutive_count = 1
            winning_positions_on_line.append(line_positions[0])


        # Continue counting matches from the next position
        start_index = consecutive_count # Start checking after the initial sequence
        for i in range(start_index, len(line_symbols)):
            current_symbol = line_symbols[i]
            if current_symbol == match_symbol_id or current_symbol == wild_symbol_internal_id:
                consecutive_count += 1
                winning_positions_on_line.append(line_positions[i])
            else:
                break # Sequence broken

        # Check if the count meets minimum requirement and calculate payout
        if consecutive_count >= MIN_MATCH_FOR_PAYLINE_WIN:
            payout_multiplier = get_payout_multiplier(match_symbol_id, consecutive_count, symbols)
            if payout_multiplier > 0:
                # Calculate win based on bet per line (if applicable) or total bet
                # Assuming bet_amount_sats is the total bet for the spin
                # Win = Bet * Multiplier (adjust if Bet is per line)
                line_win_sats = int(bet_amount_sats * payout_multiplier)
                total_win_sats += line_win_sats

                winning_lines_data.append({
                    "line_index": line_idx,
                    "symbol_id": match_symbol_id,
                    "count": consecutive_count,
                    "positions": winning_positions_on_line,
                    "win_amount": line_win_sats
                })

    # --- Scatter Wins ---
    scatter_positions = []
    scatter_count = 0
    if scatter_symbol_internal_id is not None:
        for r in range(num_rows):
            for c in range(num_cols):
                if grid[r][c] == scatter_symbol_internal_id:
                    scatter_count += 1
                    scatter_positions.append([r, c])

        if scatter_count >= MIN_MATCH_FOR_SCATTER_WIN:
            # Scatter win calculation (e.g., Bet * Count * BaseMultiplier)
            # TODO: Refine scatter payout logic - load from config/DB?
            scatter_payout_multiplier = get_payout_multiplier(scatter_symbol_internal_id, scatter_count, symbols) # Check if scatters have direct payout values
            if scatter_payout_multiplier > 0:
                 scatter_win_sats = int(bet_amount_sats * scatter_payout_multiplier)
            else:
                 # Fallback: use simple count * base multiplier if no direct payout defined
                 scatter_win_sats = int(bet_amount_sats * scatter_count * SCATTER_PAY_MULTIPLIER_BASE)

            total_win_sats += scatter_win_sats
            winning_lines_data.append({
                "line_index": "scatter", # Special identifier for scatter wins
                "symbol_id": scatter_symbol_internal_id,
                "count": scatter_count,
                "positions": scatter_positions,
                "win_amount": scatter_win_sats
            })

    return {
        "total_win_sats": total_win_sats,
        "winning_lines": winning_lines_data
    }

def check_bonus_trigger(grid, scatter_symbol_internal_id, bonus_type, trigger_count):
    """Checks if conditions are met to trigger a bonus round."""
    if not bonus_type or not scatter_symbol_internal_id:
        return False # No bonus configured or no scatter symbol

    scatter_count = 0
    for row in grid:
        for symbol_id in row:
            if symbol_id == scatter_symbol_internal_id:
                scatter_count += 1

    # Standard trigger: >= required number of scatters
    if bonus_type in ["free_spins", "standard"] and scatter_count >= trigger_count:
        return True

    # Add conditions for other bonus types if needed

    return False

