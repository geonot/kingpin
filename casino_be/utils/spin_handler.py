import random
import json
import os
from datetime import datetime, timezone
from models import db, SlotSpin, GameSession, User, Transaction # Added GameSession, User, Transaction
# SlotSymbol might not be directly used if all config comes from JSON, but keep for now

# --- Configuration ---
# Constants like MIN_MATCH_FOR_PAYLINE_WIN will likely come from gameConfig.json or be implicitly handled by payout tables.
# MIN_MATCH_FOR_SCATTER_WIN also likely from config.
# SCATTER_PAY_MULTIPLIER_BASE will be replaced by config.


# Base path for slot configurations
SLOT_CONFIG_BASE_PATH = "public/slots" # Adjust if your structure is different, e.g., "casino_be/static/slots"

def load_game_config(slot_short_name):
    """Loads the game configuration JSON file for a given slot."""
    # Construct path like "public/slots/slot1/gameConfig.json"
    config_path = os.path.join(SLOT_CONFIG_BASE_PATH, slot_short_name, "gameConfig.json")
    if not os.path.exists(config_path):
        # Fallback: try checking if slot_short_name is a direct path or stored in slot.asset_directory
        # This part depends on how slot.asset_directory is structured.
        # For now, assume slot_short_name is the directory name under SLOT_CONFIG_BASE_PATH
        raise FileNotFoundError(f"Game configuration not found for slot '{slot_short_name}' at {config_path}")

    with open(config_path, 'r') as f:
        config = json.load(f)
    return config

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
    """
    Handles the logic for a single slot machine spin using gameConfig.json.
    """
    try:
        # --- Load Game Configuration ---
        game_config = load_game_config(slot.short_name)

        # Extract key configurations
        cfg_layout = game_config.get('game', {}).get('layout', {})
        cfg_symbols_map = {s['id']: s for s in game_config.get('game', {}).get('symbols', [])}
        cfg_paylines = cfg_layout.get('paylines', [])
        cfg_rows = cfg_layout.get('rows', 3)
        cfg_columns = cfg_layout.get('columns', 5)
        cfg_wild_symbol_id = game_config.get('game', {}).get('wild_symbol_id')
        cfg_scatter_symbol_id = game_config.get('game', {}).get('scatter_symbol_id')
        cfg_bonus_features = game_config.get('game', {}).get('bonus_features', {})

        # --- Pre-Spin Validation ---
        if not isinstance(bet_amount_sats, int) or bet_amount_sats <= 0:
            raise ValueError("Invalid bet amount. Must be a positive integer (satoshis).")

        if user.balance < bet_amount_sats and not (game_session.bonus_active and game_session.bonus_spins_remaining > 0) :
            raise ValueError("Insufficient balance for this bet.")

        # --- Determine Spin Type and Deduct Bet ---
        is_bonus_spin = False
        current_spin_multiplier = 1.0 # Multiplier for the current spin's winnings

        if game_session.bonus_active and game_session.bonus_spins_remaining > 0:
            is_bonus_spin = True
            current_spin_multiplier = game_session.bonus_multiplier # Use session's bonus multiplier
            game_session.bonus_spins_remaining -= 1
            # Bet is not deducted during a bonus spin
            actual_bet_this_spin = 0
        else:
            user.balance -= bet_amount_sats
            actual_bet_this_spin = bet_amount_sats
            # Create Wager Transaction
            wager_tx = Transaction(
                user_id=user.id,
                amount=-bet_amount_sats, # Negative for wager
                type='wager',
                description=f'Slot wager: {slot.name} - Spin ID to be linked',
                game_session_id=game_session.id
            )
            db.session.add(wager_tx)
            # game_session.transactions.append(wager_tx) # Add to session if relationship is set up

        # --- Generate Spin Result ---
        # slot.symbols still provides the available symbols from DB.
        # We'll use cfg_symbols_map for properties like multipliers, is_wild, is_scatter
        # The generate_spin_grid function might need to be aware of symbol IDs from config
        spin_result_grid = generate_spin_grid(
            cfg_rows,
            cfg_columns,
            slot.symbols, # List of SlotSymbol ORM objects
            cfg_wild_symbol_id,
            cfg_scatter_symbol_id,
            cfg_symbols_map # Pass the config symbols map for weighting or other properties
        )

        # --- Calculate Wins ---
        # calculate_win will now use cfg_paylines and cfg_symbols_map
        win_info = calculate_win(
            spin_result_grid,
            cfg_paylines,
            cfg_symbols_map, # Use the symbol data from config
            bet_amount_sats, # This is the total bet for the spin
            cfg_wild_symbol_id,
            cfg_scatter_symbol_id,
            cfg_bonus_features.get('free_spins', {}).get('multiplier', 1.0) if is_bonus_spin else 1.0
            # Pass bet_amount_sats, num_paylines for per-line calculation
        )

        win_amount_sats = win_info['total_win_sats']
        winning_lines = win_info['winning_lines']

        # Apply current spin multiplier (e.g., from active free spins bonus)
        # Note: win_info from calculate_win should be raw win, multiplier applied here or inside if it's complex
        if is_bonus_spin and current_spin_multiplier > 1.0:
            win_amount_sats = int(win_amount_sats * current_spin_multiplier)
            # Update individual winning line amounts if necessary
            for line in winning_lines:
                if line.get('win_amount', 0) > 0 : # Check if 'win_amount' exists and is positive
                    line['win_amount'] = int(line['win_amount'] * current_spin_multiplier)


        # --- Check for Bonus Trigger (on non-bonus spins) ---
        bonus_triggered_this_spin = False
        newly_awarded_spins = 0
        new_bonus_multiplier = 1.0

        if not is_bonus_spin: # Bonus can only be triggered on a normal spin
            bonus_trigger_info = check_bonus_trigger(
                spin_result_grid,
                cfg_scatter_symbol_id,
                cfg_bonus_features
            )
            if bonus_trigger_info['triggered']:
                bonus_triggered_this_spin = True
                newly_awarded_spins = bonus_trigger_info.get('spins_awarded', 0)
                new_bonus_multiplier = bonus_trigger_info.get('multiplier', 1.0)


        # --- Update Session State for Bonus ---
        if bonus_triggered_this_spin:
            if not game_session.bonus_active: # Starting a new bonus
                game_session.bonus_active = True
                game_session.bonus_spins_remaining = newly_awarded_spins
                game_session.bonus_multiplier = new_bonus_multiplier
            else: # Re-trigger or additional spins during an active bonus
                game_session.bonus_spins_remaining += newly_awarded_spins
                # Optionally, decide if multiplier updates or accumulates, based on game rules
                # For now, assume it takes the new multiplier if retriggered, or keeps existing if just adding spins.
                if new_bonus_multiplier != game_session.bonus_multiplier and newly_awarded_spins > 0 :
                     game_session.bonus_multiplier = new_bonus_multiplier # Or max(game_session.bonus_multiplier, new_bonus_multiplier)

        elif game_session.bonus_active and game_session.bonus_spins_remaining <= 0:
            # Bonus ended
            game_session.bonus_active = False
            game_session.bonus_multiplier = 1.0 # Reset multiplier


        # --- Update Session Aggregates ---
        game_session.num_spins += 1
        if not is_bonus_spin:
            game_session.amount_wagered = (game_session.amount_wagered or 0) + actual_bet_this_spin # Ensure amount_wagered is not None
        game_session.amount_won = (game_session.amount_won or 0) + win_amount_sats # Ensure amount_won is not None

        # --- Update User Balance & Win Transaction ---
        if win_amount_sats > 0:
            user.balance += win_amount_sats
            win_tx = Transaction(
                user_id=user.id,
                amount=win_amount_sats,
                type='win',
                description=f'Slot win: {slot.name} - Spin ID to be linked',
                game_session_id=game_session.id
            )
            db.session.add(win_tx)
            # game_session.transactions.append(win_tx)

        # --- Create Spin Record ---
        # Ensure spin_result_grid is JSON serializable (list of lists of ints)
        new_spin = SlotSpin(
            game_session_id=game_session.id,
            spin_result=spin_result_grid, # Should be [[int, ...], ...]
            win_amount=win_amount_sats,
            bet_amount=actual_bet_this_spin,
            is_bonus_spin=is_bonus_spin,
            spin_time=datetime.now(timezone.utc),
            multiplier_used=current_spin_multiplier if is_bonus_spin else 1.0
        )
        db.session.add(new_spin)
        db.session.flush() # Flush to get new_spin.id for transaction linking

        # Link transactions to this spin if created
        if not is_bonus_spin and 'wager_tx' in locals():
            wager_tx.slot_spin_id = new_spin.id
        if win_amount_sats > 0 and 'win_tx' in locals():
            win_tx.slot_spin_id = new_spin.id

        # --- Return Results ---
        # Ensure all satoshi amounts are integers
        return {
            "spin_result": spin_result_grid,
            "win_amount_sats": int(win_amount_sats),
            "winning_lines": winning_lines, # Ensure this is serializable
            "bonus_triggered": bonus_triggered_this_spin,
            "bonus_active": game_session.bonus_active,
            "bonus_spins_remaining": game_session.bonus_spins_remaining if game_session.bonus_active else 0,
            "bonus_multiplier": game_session.bonus_multiplier if game_session.bonus_active else 1.0,
            "user_balance_sats": int(user.balance),
            "session_stats": { # Consistent with other game types potentially
                "num_spins": game_session.num_spins,
                "amount_wagered_sats": int(game_session.amount_wagered or 0),
                "amount_won_sats": int(game_session.amount_won or 0),
            }
        }
    except FileNotFoundError as e:
        # Log error appropriately
        # raise ValueError(f"Game configuration error: {e}") # Or handle more gracefully
        # For now, re-raise as ValueError for the route to catch
        # In a real app, you might want a more specific exception type.
        db.session.rollback() # Rollback any DB changes if config fails
        raise ValueError(str(e))
    except ValueError as e: # Catch specific errors like insufficient balance
        db.session.rollback()
        raise e # Re-raise it for the route to handle
    except Exception as e:
        db.session.rollback()
        # Log the exception e
        # Consider what to return or raise. A generic error for the user.
        raise RuntimeError(f"An unexpected error occurred during the spin: {str(e)}") # Use str(e) for cleaner message


def generate_spin_grid(rows, columns, db_symbols, wild_symbol_config_id, scatter_symbol_config_id, config_symbols_map):
    """
    Generates a grid of symbol internal IDs based on weighted probabilities.
    Symbols list contains SlotSymbol objects.
    """
    """
    Generates a grid of symbol IDs.
    Uses symbol IDs from `config_symbols_map` (which are the internal IDs).
    Weighting can be complex; for now, use simple random choice or weights from config if available.
    `db_symbols` (SlotSymbol ORM objects) are used to get the list of possible symbol_internal_ids for this slot.
    `config_symbols_map` is a dictionary from gameConfig.json: { <symbol_id_int>: {props...} }
    """
    if not db_symbols: # Should come from slot.symbols
        # Fallback to a simple grid if no symbols are defined for the slot in DB.
        # This indicates a setup issue.
        return [[config_symbols_map.keys()[0] if config_symbols_map else 1 for _ in range(columns)] for _ in range(rows)]

    # Get all symbol internal IDs that are actually configured for this slot via the SlotSymbol table
    # These are the `symbol_internal_id` values.
    valid_symbol_ids_for_slot = [s.symbol_internal_id for s in db_symbols]

    # Filter these further: only include symbols that also exist in the gameConfig.json's symbol list.
    # This ensures we only spin symbols that have defined properties (like multipliers, etc.)
    spinable_symbol_ids = [sid for sid in valid_symbol_ids_for_slot if sid in config_symbols_map]

    if not spinable_symbol_ids:
        # This is a critical configuration error: Slot has symbols in DB, but they don't map to gameConfig.json
        raise ValueError("No spinable symbols found. Check slot DB symbol configuration against gameConfig.json.")

    # --- Weighting ---
    # Attempt to get weights from config_symbols_map if they exist, e.g. symbol_obj.get('weight', 1.0)
    # For now, using uniform weights.
    # TODO: Implement configurable symbol weighting based on `gameConfig.json` (e.g., a 'weight' property in each symbol definition)

    weights = []
    symbols_for_choice = []

    for s_id in spinable_symbol_ids:
        symbol_config = config_symbols_map.get(s_id)
        if symbol_config:
            # Example: use a 'spawn_weight' or 'reel_weight' from config if available
            # weight = symbol_config.get('reel_weight', 1.0)
            # For now, assume equal weight for simplicity, but favor non-special symbols slightly more in a real scenario.
            # This current simple weighting does not consider reel strips or advanced slot math.
            is_wild = symbol_config.get('is_wild', False) or s_id == wild_symbol_config_id
            is_scatter = symbol_config.get('is_scatter', False) or s_id == scatter_symbol_config_id

            if is_wild:
                weights.append(symbol_config.get('weight', 0.5)) # Default example weight
            elif is_scatter:
                weights.append(symbol_config.get('weight', 0.4)) # Default example weight
            else:
                weights.append(symbol_config.get('weight', 1.0)) # Default example weight
            symbols_for_choice.append(s_id)

    total_weight = sum(weights)
    if total_weight == 0 or not symbols_for_choice: # Prevent division by zero or empty choices
         if not symbols_for_choice: # if symbols_for_choice is empty, fall back to spinable_symbol_ids with uniform weight
             if not spinable_symbol_ids: # Should have been caught earlier
                  raise ValueError("Cannot generate spin grid: No symbols available for choice and no spinable_symbol_ids.")
             symbols_for_choice = spinable_symbol_ids
             weights = [1.0] * len(symbols_for_choice)
             total_weight = float(len(symbols_for_choice))
         else: # weights were all zero, distribute uniformly
             weights = [1.0 / len(symbols_for_choice) for _ in symbols_for_choice]
    else:
        weights = [w / total_weight for w in weights]


    grid = []
    for r in range(rows):
        row_symbols = random.choices(symbols_for_choice, weights=weights, k=columns)
        grid.append(row_symbols)
    return grid


# Removed define_paylines - it will come from game_config.layout.paylines

def get_symbol_payout(symbol_id, count, config_symbols_map, is_scatter=False):
    """
    Determines the payout multiplier based on the symbol and count.
    This should ideally query a payout table (SlotPayout model).
    Using a simplified placeholder logic here.
    """
    """
    Gets the payout multiplier for a given symbol ID and count from the config.
    `config_symbols_map` is the map of symbol objects from gameConfig.json.
    If `is_scatter` is true, it looks for 'payouts'; otherwise, 'value_multipliers'.
    """
    symbol_config = config_symbols_map.get(symbol_id)
    if not symbol_config:
        return 0.0

    if is_scatter:
        # Scatter payouts are typically direct multipliers of total bet
        payout_map = symbol_config.get('payouts', {}) # e.g., {"3": 5, "4": 15, "5": 50}
    else:
        # Payline symbol multipliers are for bet_per_line
        payout_map = symbol_config.get('value_multipliers', {}) # e.g., {"3": 10, "4": 50, "5": 200}

    # `count` must be a string for dict lookup as per example gameConfig
    multiplier = payout_map.get(str(count), 0.0)

    # Ensure multiplier is float or int
    try:
        # Ensure that we handle cases where multiplier might be an empty string or None from config
        if multiplier is None or str(multiplier).strip() == "":
            return 0.0
        return float(multiplier)
    except ValueError:
        return 0.0


def calculate_win(grid, config_paylines, config_symbols_map, total_bet_sats, wild_symbol_id, scatter_symbol_id): # Removed current_spin_multiplier
    """Calculates total win amount and identifies winning lines using config.
    `config_paylines` is game_config.game.layout.paylines
    `config_symbols_map` is game_config.game.symbols (mapped by id)
    `total_bet_sats` is the total amount bet for the entire spin.
    `wild_symbol_id` is the internal ID from config.
    `scatter_symbol_id` is the internal ID from config.
    """
    total_win_sats = 0
    winning_lines_data = [] # Store detailed info about each win
    num_rows = len(grid)
    num_cols = len(grid[0]) if num_rows > 0 else 0

    # --- Payline Wins ---
    # Bet per line calculation:
    num_active_paylines = len(config_paylines) # Assuming all defined paylines are played
    if num_active_paylines == 0:
        bet_per_line_sats = 0 # Avoid division by zero; though should not happen with valid config
    else:
        # Ensure integer division, handle potential rounding if necessary (though satoshis should be precise)
        bet_per_line_sats = total_bet_sats // num_active_paylines
        # It's possible that total_bet_sats is not perfectly divisible.
        # Game design should specify how this is handled (e.g. user bets per line, or total bet must be multiple of lines)
        # For now, we assume total_bet_sats is what's wagered, and bet_per_line is derived.

    for payline_config in config_paylines:
        payline_id = payline_config.get("id", "unknown_line")
        payline_positions = payline_config.get("positions", []) # List of [row, col]

        line_symbols_on_grid = [] # Actual symbol IDs on this payline from the spin grid
        actual_positions_on_line = [] # Coordinates of these symbols

        for r, c in payline_positions:
            if 0 <= r < num_rows and 0 <= c < num_cols:
                symbol_on_grid = grid[r][c]
                line_symbols_on_grid.append(symbol_on_grid)
                actual_positions_on_line.append([r,c])
            else: # Should not happen with valid config
                line_symbols_on_grid.append(None) # Placeholder for out-of-bounds
                actual_positions_on_line.append(None)

        # Determine winning symbol and count for this line (left-to-right)
        first_symbol_on_line = line_symbols_on_grid[0]
        if first_symbol_on_line is None or first_symbol_on_line == scatter_symbol_id:
            continue # Paylines typically don't start with scatter or empty positions

        match_symbol_id = None
        consecutive_count = 0
        winning_symbol_positions = []

        # Handle if the line starts with a wild symbol
        if first_symbol_on_line == wild_symbol_id:
            # Wilds substitute for other symbols. Need to find the first non-wild to determine the matching symbol.
            # Then count initial wilds + subsequent matching symbols or wilds.
            temp_match_symbol_id = None
            wilds_at_start = 0
            for i in range(len(line_symbols_on_grid)):
                s_id = line_symbols_on_grid[i]
                if s_id == wild_symbol_id:
                    wilds_at_start += 1
                    winning_symbol_positions.append(actual_positions_on_line[i])
                elif s_id != scatter_symbol_id : # Found the symbol to match
                    temp_match_symbol_id = s_id
                    consecutive_count = wilds_at_start + 1
                    winning_symbol_positions.append(actual_positions_on_line[i])
                    match_symbol_id = temp_match_symbol_id
                    break
                else: # Scatter or None, breaks payline continuity for this potential match
                    break

            if match_symbol_id is None and wilds_at_start > 0: # Line is all wilds (or wilds then scatter/None)
                # If game rules allow all-wild lines, determine payout for wild symbol itself
                # Wild symbol must have its own entry in 'value_multipliers' in config
                symbol_config = config_symbols_map.get(wild_symbol_id)
                if symbol_config and symbol_config.get('value_multipliers'):
                    match_symbol_id = wild_symbol_id
                    consecutive_count = wilds_at_start
                else: # Wilds don't form their own win, or line too short
                    continue
        else:
            # Line starts with a regular symbol
            match_symbol_id = first_symbol_on_line
            consecutive_count = 1
            winning_symbol_positions.append(actual_positions_on_line[0])

        # Continue counting from the position after initial sequence
        # If first symbol was wild and found a match, `consecutive_count` is already set.
        # `i` should start from `consecutive_count` index in `line_symbols_on_grid`.
        if match_symbol_id: # Proceed if a potential winning line is identified
            for i in range(consecutive_count, len(line_symbols_on_grid)):
                current_symbol_on_grid = line_symbols_on_grid[i]
                if current_symbol_on_grid == match_symbol_id or current_symbol_on_grid == wild_symbol_id:
                    consecutive_count += 1
                    winning_symbol_positions.append(actual_positions_on_line[i])
                else:
                    break # Sequence broken

        # Get payout for the matched sequence
        # The minimum match count is implicitly handled by what's defined in value_multipliers (e.g. no "1" or "2")
        payout_multiplier = get_symbol_payout(match_symbol_id, consecutive_count, config_symbols_map, is_scatter=False)

        if payout_multiplier > 0:
            # Line win = bet_per_line * symbol_multiplier
            # Ensure bet_per_line_sats is used here.
            line_win_sats = int(bet_per_line_sats * payout_multiplier)

            # Apply spin multiplier if any (e.g. from free spins bonus)
            # This is now handled outside, after all raw wins are calculated.
            # line_win_sats = int(line_win_sats * current_spin_multiplier)


            if line_win_sats > 0:
                total_win_sats += line_win_sats
                winning_lines_data.append({
                    "line_id": payline_id, # From payline config
                    "symbol_id": match_symbol_id, # The symbol that formed the win (not wild, unless wild itself pays)
                    "count": consecutive_count,
                    "positions": winning_symbol_positions, # List of [r,c] coordinates
                    "win_amount_sats": line_win_sats
                })

    # --- Scatter Wins ---
    scatter_positions_on_grid = []
    scatter_count_on_grid = 0
    if scatter_symbol_id is not None: # Check if a scatter symbol is configured
        for r_idx, row in enumerate(grid):
            for c_idx, symbol_in_cell in enumerate(row):
                if symbol_in_cell == scatter_symbol_id:
                    scatter_count_on_grid += 1
                    scatter_positions_on_grid.append([r_idx, c_idx])

    # Get scatter payout based on count
    # Scatter payouts are typically multiples of the *total bet*
    scatter_payout_multiplier = get_symbol_payout(scatter_symbol_id, scatter_count_on_grid, config_symbols_map, is_scatter=True)

    if scatter_payout_multiplier > 0:
        scatter_win_sats = int(total_bet_sats * scatter_payout_multiplier)
        # scatter_win_sats = int(scatter_win_sats * current_spin_multiplier) # Apply spin multiplier - also handled outside now

        if scatter_win_sats > 0:
            total_win_sats += scatter_win_sats
            winning_lines_data.append({
                "line_id": "scatter", # Special identifier for scatter wins
                "symbol_id": scatter_symbol_id,
                "count": scatter_count_on_grid,
                "positions": scatter_positions_on_grid,
                "win_amount_sats": scatter_win_sats
            })

    return {
        "total_win_sats": total_win_sats, # Raw total, multiplier applied in main handle_spin
        "winning_lines": winning_lines_data
    }


def check_bonus_trigger(grid, scatter_symbol_id, config_bonus_features):
    """
    Checks if conditions are met to trigger a bonus round based on gameConfig.json.
    `config_bonus_features` is game_config.game.bonus_features.
    Returns a dict with 'triggered': bool, and other bonus details if triggered.
    """
    # Example for free_spins, extend for other bonus types
    free_spins_config = config_bonus_features.get('free_spins')
    if not free_spins_config or not scatter_symbol_id:
        return {'triggered': False}

    trigger_sym_id = free_spins_config.get('trigger_symbol_id')
    if trigger_sym_id != scatter_symbol_id: # Ensure config matches primary scatter_id for clarity
        # Or handle cases where a different symbol triggers bonus. For now, assume it's the main scatter.
        # Log a warning if they don't match?
        pass

    min_scatter_to_trigger = free_spins_config.get('trigger_count')
    if not min_scatter_to_trigger:
        return {'triggered': False}

    scatter_count = 0
    for row in grid:
        for symbol_id_in_cell in row:
            if symbol_id_in_cell == scatter_symbol_id: # Use the passed scatter_symbol_id from game root
                scatter_count += 1

    if scatter_count >= min_scatter_to_trigger:
        return {
            'triggered': True,
            'type': 'free_spins', # Or derive from config key
            'spins_awarded': free_spins_config.get('spins_awarded', 0),
            'multiplier': free_spins_config.get('multiplier', 1.0)
            # Add other bonus parameters if needed
        }

    return {'triggered': False}

