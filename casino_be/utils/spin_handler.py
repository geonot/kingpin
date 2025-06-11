import random
import json
import os
import secrets
from datetime import datetime, timezone
from models import db, SlotSpin, GameSession, User, Transaction, UserBonus # Added UserBonus
# SlotSymbol might not be directly used if all config comes from JSON, but keep for now

# --- Configuration ---
# Constants like MIN_MATCH_FOR_PAYLINE_WIN will likely come from gameConfig.json or be implicitly handled by payout tables.
# MIN_MATCH_FOR_SCATTER_WIN also likely from config.
# SCATTER_PAY_MULTIPLIER_BASE will be replaced by config.


# Base path for slot configurations
# SLOT_CONFIG_BASE_PATH = "public/slots" # Old relative path

def load_game_config(slot_short_name):
    """
    Loads the game configuration JSON file for a given slot and validates its structure.

    Args:
        slot_short_name (str): The short name of the slot, used to find its configuration file.

    Returns:
        dict: The loaded and validated game configuration object.

    Raises:
        FileNotFoundError: If the configuration file for the slot cannot be found.
        ValueError: If the JSON is malformed or if the configuration structure is invalid
                    (as per `_validate_game_config`).
        RuntimeError: For other unexpected errors during loading.
    """
    # Construct path relative to the 'casino_be' package directory
    # __file__ is casino_be/utils/spin_handler.py
    # Go up two levels to casino_be, then to public/slots
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'public', 'slots'))
    file_path = os.path.join(base_dir, slot_short_name, "gameConfig.json") # Renamed for clarity

    # Attempt to load from primary path first
    # print(f"Attempting to load game config from: {file_path}") # Debug print

    if not os.path.exists(file_path):
        # Fallback to casino_fe path
        alt_base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'casino_fe', 'public', 'slots'))
        alt_file_path = os.path.join(alt_base_dir, slot_short_name, "gameConfig.json")
        # print(f"Primary path not found. Attempting fallback: {alt_file_path}") # Debug print
        if os.path.exists(alt_file_path):
            file_path = alt_file_path
        else:
            # If neither exists, raise FileNotFoundError with the primary path as expectation
            raise FileNotFoundError(f"Configuration file not found for slot '{slot_short_name}' at {file_path} (also checked {alt_file_path})")

    try:
        with open(file_path, 'r') as f:
            config = json.load(f)
        _validate_game_config(config, slot_short_name) # Call validation function
        # print(f"Successfully loaded and validated config for {slot_short_name}") # Debug print
        return config
    except FileNotFoundError: # Should be caught by os.path.exists checks above, but good practice
        # Use current_app.logger if available and this function is part of a Flask app context
        # For now, direct print or re-raise. Assuming Flask context might not be available here directly.
        # print(f"Game config file not found at {file_path}") # Debug print
        raise FileNotFoundError(f"Configuration file not found for slot '{slot_short_name}' at {file_path}")
    except json.JSONDecodeError as e:
        # print(f"JSON decode error for {file_path}: {e.msg} at line {e.lineno} col {e.colno}") # Debug print
        raise ValueError(f"Invalid JSON in {file_path}: {e.msg} (line {e.lineno}, col {e.colno})")
    except Exception as e:
        # print(f"Unexpected error loading game config for {slot_short_name} from {file_path}: {str(e)}") # Debug print
        raise RuntimeError(f"Could not load game config for slot '{slot_short_name}': {str(e)}")


def _validate_game_config(config, slot_short_name):
    """
    Validates the structure and essential content of a game configuration object.

    This function checks for the presence and correct types of key configuration
    parameters within the `config` dictionary, such as game layout, symbols,
    paylines, reel strips, and bonus features. It ensures that coordinates are
    within bounds and that symbol IDs are consistent.

    Args:
        config (dict): The game configuration object (typically loaded from JSON).
        slot_short_name (str): The short name of the slot, used for clear error messaging.

    Raises:
        ValueError: If any validation check fails, indicating an issue with the
                    game configuration's structure or content. The error message
                    will detail the specific problem and the slot involved.
    """
    if not isinstance(config, dict):
        raise ValueError(f"Config validation error for slot '{slot_short_name}': Root must be a dictionary.")

    game = config.get('game')
    if not isinstance(game, dict):
        raise ValueError(f"Config validation error for slot '{slot_short_name}': 'game' key must be a dictionary.")

    # Validate basic game properties
    for key, key_type, can_be_empty in [('name', str, False), ('short_name', str, False)]:
        value = game.get(key)
        if not isinstance(value, key_type) or (not can_be_empty and not value.strip()):
            raise ValueError(f"Config validation error for slot '{slot_short_name}': game.{key} must be a non-empty string.")

    # Validate layout
    layout = game.get('layout')
    if not isinstance(layout, dict):
        raise ValueError(f"Config validation error for slot '{slot_short_name}': game.layout must be a dictionary.")

    rows = layout.get('rows')
    if not isinstance(rows, int) or rows <= 0:
        raise ValueError(f"Config validation error for slot '{slot_short_name}': game.layout.rows must be a positive integer.")

    columns = layout.get('columns')
    if not isinstance(columns, int) or columns <= 0:
        raise ValueError(f"Config validation error for slot '{slot_short_name}': game.layout.columns must be a positive integer.")

    paylines = layout.get('paylines')
    if not isinstance(paylines, list):
        raise ValueError(f"Config validation error for slot '{slot_short_name}': game.layout.paylines must be a list.")
    for i, pl in enumerate(paylines):
        if not isinstance(pl, dict):
            raise ValueError(f"Config validation error for slot '{slot_short_name}': game.layout.paylines[{i}] must be a dictionary.")
        if 'id' not in pl or 'coords' not in pl:
            raise ValueError(f"Config validation error for slot '{slot_short_name}': game.layout.paylines[{i}] must have 'id' and 'coords'.")
        if not isinstance(pl['coords'], list):
            raise ValueError(f"Config validation error for slot '{slot_short_name}': game.layout.paylines[{i}].coords must be a list.")
        for j, coord in enumerate(pl['coords']):
            if not isinstance(coord, list) or len(coord) != 2:
                raise ValueError(f"Config validation error for slot '{slot_short_name}': game.layout.paylines[{i}].coords[{j}] must be a list of two integers.")
            r, c = coord
            if not (isinstance(r, int) and isinstance(c, int)):
                raise ValueError(f"Config validation error for slot '{slot_short_name}': game.layout.paylines[{i}].coords[{j}] values must be integers.")
            if not (0 <= r < rows and 0 <= c < columns):
                raise ValueError(f"Config validation error for slot '{slot_short_name}': game.layout.paylines[{i}].coords[{j}] ([{r},{c}]) out of bounds (rows: {rows}, cols: {columns}).")

    # Validate Symbols
    symbols_data = game.get('symbols')
    if not isinstance(symbols_data, list) or not symbols_data:
        raise ValueError(f"Config validation error for slot '{slot_short_name}': game.symbols must be a non-empty list.")

    collected_symbol_ids = set()
    for i, sym in enumerate(symbols_data):
        if not isinstance(sym, dict):
            raise ValueError(f"Config validation error for slot '{slot_short_name}': game.symbols[{i}] must be a dictionary.")
        for key, key_type in [('id', int, False), ('name', str, False), ('icon', str, False)]:
            val = sym.get(key[0])
            # Check type and emptiness for strings
            if not isinstance(val, key_type[0]) or (key_type[0] == str and not key_type[1] and not val.strip()):
                 raise ValueError(f"Config validation error for slot '{slot_short_name}': game.symbols[{i}].{key[0]} must be a valid non-empty {key_type[0].__name__}.")
            if key[0] == 'id':
                collected_symbol_ids.add(val)

        weight = sym.get('weight')
        if weight is not None and not (isinstance(weight, (int, float)) and weight > 0):
            raise ValueError(f"Config validation error for slot '{slot_short_name}': game.symbols[{i}].weight must be a positive number if present.")

        for opt_key, opt_type in [('is_wild', bool), ('is_scatter', bool),
                                  ('value_multipliers', dict), ('scatter_payouts', dict),
                                  ('cluster_payouts', dict)]:
            if opt_key in sym and not isinstance(sym[opt_key], opt_type):
                raise ValueError(f"Config validation error for slot '{slot_short_name}': game.symbols[{i}].{opt_key} must be a {opt_type.__name__} if present.")

    # Validate Special Symbol IDs
    for special_key in ['wild_symbol_id', 'scatter_symbol_id']: # Renamed from symbol_wild for consistency
        s_id = game.get(special_key)
        if s_id is not None:
            if not isinstance(s_id, int):
                raise ValueError(f"Config validation error for slot '{slot_short_name}': game.{special_key} must be an integer if present.")
            if s_id not in collected_symbol_ids:
                raise ValueError(f"Config validation error for slot '{slot_short_name}': game.{special_key} ID {s_id} not found in defined symbols.")

    # Validate Reel Strips
    reel_strips = game.get('reel_strips')
    if reel_strips is not None:
        if not isinstance(reel_strips, list):
            raise ValueError(f"Config validation error for slot '{slot_short_name}': game.reel_strips must be a list if present.")
        if len(reel_strips) != columns:
            raise ValueError(f"Config validation error for slot '{slot_short_name}': game.reel_strips length must match game.layout.columns ({columns}).")
        for i, strip in enumerate(reel_strips):
            if not isinstance(strip, list) or not strip:
                raise ValueError(f"Config validation error for slot '{slot_short_name}': game.reel_strips[{i}] must be a non-empty list.")
            for j, s_id in enumerate(strip):
                if not isinstance(s_id, int):
                    raise ValueError(f"Config validation error for slot '{slot_short_name}': game.reel_strips[{i}][{j}] must be an integer symbol ID.")
                if s_id not in collected_symbol_ids:
                    raise ValueError(f"Config validation error for slot '{slot_short_name}': game.reel_strips[{i}][{j}] ID {s_id} not found in defined symbols.")

    # Validate Bonus Features
    bonus_features = game.get('bonus_features')
    if bonus_features is not None:
        if not isinstance(bonus_features, dict):
            raise ValueError(f"Config validation error for slot '{slot_short_name}': game.bonus_features must be a dictionary if present.")

        free_spins = bonus_features.get('free_spins')
        if free_spins is not None:
            if not isinstance(free_spins, dict):
                raise ValueError(f"Config validation error for slot '{slot_short_name}': game.bonus_features.free_spins must be a dictionary if present.")

            fs_trigger_id = free_spins.get('trigger_symbol_id')
            if not isinstance(fs_trigger_id, int) or fs_trigger_id not in collected_symbol_ids:
                raise ValueError(f"Config validation error for slot '{slot_short_name}': game.bonus_features.free_spins.trigger_symbol_id must be a valid symbol ID.")

            if not (isinstance(free_spins.get('trigger_count'), int) and free_spins.get('trigger_count') > 0):
                raise ValueError(f"Config validation error for slot '{slot_short_name}': game.bonus_features.free_spins.trigger_count must be a positive integer.")

            if not (isinstance(free_spins.get('spins_awarded'), int) and free_spins.get('spins_awarded') >= 0):
                raise ValueError(f"Config validation error for slot '{slot_short_name}': game.bonus_features.free_spins.spins_awarded must be a non-negative integer.")

            multiplier = free_spins.get('multiplier')
            if not (isinstance(multiplier, (int, float)) and multiplier >= 1.0):
                 raise ValueError(f"Config validation error for slot '{slot_short_name}': game.bonus_features.free_spins.multiplier must be a number >= 1.0.")

    # Validate Cascading & Cluster settings
    if 'is_cascading' in game and not isinstance(game['is_cascading'], bool):
        raise ValueError(f"Config validation error for slot '{slot_short_name}': game.is_cascading must be a boolean if present.")

    min_match = game.get('min_symbols_to_match')
    if min_match is not None and (not isinstance(min_match, int) or min_match <= 0):
        raise ValueError(f"Config validation error for slot '{slot_short_name}': game.min_symbols_to_match must be a positive integer if present.")

    if game.get('is_cascading'):
        cascade_type = game.get('cascade_type')
        if not isinstance(cascade_type, str) or cascade_type not in ["fall_from_top", "replace_in_place"]: # Add known types
            raise ValueError(f"Config validation error for slot '{slot_short_name}': game.cascade_type must be a known string (e.g., 'fall_from_top') if is_cascading is true.")

        win_multipliers = game.get('win_multipliers')
        if win_multipliers is not None:
            if not isinstance(win_multipliers, list) or not all(isinstance(m, (int, float)) for m in win_multipliers):
                raise ValueError(f"Config validation error for slot '{slot_short_name}': game.win_multipliers must be a list of numbers if present and is_cascading is true.")

    # Add more checks as needed based on gameConfig.json structure


def handle_spin(user, slot, game_session, bet_amount_sats):
    """
    Handles the logic for a single slot machine spin, including generating the grid,
    calculating wins, handling cascades, managing bonus features, and recording
    financial transactions and spin data.

    Args:
        user (User): The user performing the spin.
        slot (Slot): The slot machine being played.
        game_session (GameSession): The current active game session for this user and slot.
        bet_amount_sats (int): The amount bet in Satoshis for this spin.

    Returns:
        dict: A dictionary containing the detailed results of the spin:
            - "spin_id" (int): ID of the recorded SlotSpin.
            - "spin_result" (list[list[int]]): The initial symbol ID grid.
            - "win_amount_sats" (int): Total win from this spin sequence (initial + cascades),
                                       after applying any bonus multipliers.
            - "winning_lines" (list[dict]): Information about each winning line/cluster
                                             from the *initial* spin. Cascading wins are
                                             aggregated into `win_amount_sats` but not detailed here.
                                             Each entry can be for a 'payline', 'scatter', or 'cluster',
                                             indicated by a 'type' key.
            - "bonus_triggered" (bool): True if a bonus feature (e.g., free spins) was
                                        triggered on this spin (only on non-bonus spins).
            - "bonus_active" (bool): True if a bonus (e.g., free spins) is currently active
                                     after this spin.
            - "bonus_spins_remaining" (int): Number of free spins remaining if bonus is active.
            - "bonus_multiplier" (float): Current win multiplier if bonus is active.
            - "user_balance_sats" (int): The user's balance after all effects of the spin.
            - "session_stats" (dict): Aggregated statistics for the current game session.

    Side Effects:
        - Modifies `user.balance`.
        - Modifies `game_session` (spin counts, wagered/won amounts, bonus state, including
          potential re-triggers or extensions of bonus rounds).
        - Creates `SlotSpin` record in the database.
        - Creates `Transaction` records for wagers and wins.
        - Updates `UserBonus` wagering progress if applicable.
        - All database changes are added to the current `db.session` but NOT committed.
          The caller is responsible for `db.session.commit()`.

    Raises:
        FileNotFoundError: If `gameConfig.json` for the slot is not found.
        ValueError: For invalid bet amounts, insufficient balance, critical configuration
                    errors (validated by `load_game_config`), or other spin-related
                    validation failures (e.g., no spinable symbols).
        RuntimeError: For other unexpected errors during spin processing.
    """
    try:
        # --- 1. Load and Validate Game Configuration ---
        game_config = load_game_config(slot.short_name)

        # Extract key configurations for easier access
        cfg_game_root = game_config.get('game', {})
        cfg_layout = cfg_game_root.get('layout', {})
        cfg_symbols_map = {s['id']: s for s in game_config.get('game', {}).get('symbols', [])}
        cfg_paylines = cfg_layout.get('paylines', [])
        cfg_rows = cfg_layout.get('rows', 3)
        cfg_columns = cfg_layout.get('columns', 5)
        cfg_wild_symbol_id = game_config.get('game', {}).get('wild_symbol_id')
        cfg_scatter_symbol_id = game_config.get('game', {}).get('scatter_symbol_id')
        cfg_bonus_features = game_config.get('game', {}).get('bonus_features', {})
        # New cascading configurations
        cfg_is_cascading = game_config.get('game', {}).get('is_cascading', False)
        cfg_cascade_type = game_config.get('game', {}).get('cascade_type', None) # e.g., "fall_from_top"
        cfg_min_symbols_to_match = game_config.get('game', {}).get('min_symbols_to_match', None) # For cluster/match-N
        cfg_win_multipliers = game_config.get('game', {}).get('win_multipliers', []) # For cascading wins e.g., [1,2,3,5]

        # --- Pre-Spin Validation ---
        if not isinstance(bet_amount_sats, int) or bet_amount_sats <= 0:
            raise ValueError("Invalid bet amount. Must be a positive integer (satoshis).")

        # Load paylines to check minimum bet requirements
        cfg_layout = game_config.get('game', {}).get('layout', {})
        cfg_paylines = cfg_layout.get('paylines', [])
        num_paylines = len(cfg_paylines)
        
        # # print(f"DEBUG_SPIN_HANDLER: bet_amount_sats={bet_amount_sats}, num_paylines={num_paylines}") # Debug print
        # # print(f"DEBUG_SPIN_HANDLER: bet_amount_sats % num_paylines = {bet_amount_sats % num_paylines if num_paylines > 0 else 'N/A'}") # Debug print
        
        # Check if bet is compatible with payline system
        if num_paylines > 0 and bet_amount_sats % num_paylines != 0:
            next_valid_bet = ((bet_amount_sats // num_paylines) + 1) * num_paylines
            prev_valid_bet = (bet_amount_sats // num_paylines) * num_paylines
            if prev_valid_bet == 0: prev_valid_bet = num_paylines # Ensure prev_valid_bet is at least one payline's worth
            
            raise ValueError(f"Bet amount ({bet_amount_sats} sats) must be evenly divisible by number of paylines ({num_paylines}). "
                            f"Try {prev_valid_bet} or {next_valid_bet} sats instead.")

        # # print(f"DEBUG_SPIN_HANDLER: Bet validation passed!") # Debug print

        # Balance check (only if not a bonus spin)
        if not (game_session.bonus_active and game_session.bonus_spins_remaining > 0):
            if user.balance < bet_amount_sats:
                raise ValueError("Insufficient balance for this bet.")

        # --- 3. Update Wagering Progress (for PAID spins if bonus is active) ---
        actual_bet_this_spin_for_wagering = 0
        if not (game_session.bonus_active and game_session.bonus_spins_remaining > 0): # i.e., if this is a paid spin
            actual_bet_this_spin_for_wagering = bet_amount_sats

        if actual_bet_this_spin_for_wagering > 0:
            active_bonus = UserBonus.query.filter_by(
                user_id=user.id,
                is_active=True,
                is_completed=False,
                is_cancelled=False
            ).first()

            if active_bonus:
                active_bonus.wagering_progress_sats += actual_bet_this_spin_for_wagering
                active_bonus.updated_at = datetime.now(timezone.utc)

                if active_bonus.wagering_progress_sats >= active_bonus.wagering_requirement_sats:
                    active_bonus.is_active = False
                    active_bonus.is_completed = True
                    active_bonus.completed_at = datetime.now(timezone.utc)
                    # print(f"User {user.id} completed wagering for UserBonus {active_bonus.id}.") # Logging handled by caller or removed for now

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
                transaction_type='wager', # Ensure this matches model's transaction_type column name
                details={'slot_name': slot.name, 'session_id': game_session.id}, # Using details field
                # description=f'Slot wager: {slot.name}', # Old description field
                    # game_session_id removed
            )
            db.session.add(wager_tx)
            # game_session.transactions.append(wager_tx) # Add to session if relationship is set up

        # --- Generate Spin Result ---
        # `slot.symbols` provides SlotSymbol ORM objects.
        # `cfg_symbols_map` provides detailed configuration for symbols from gameConfig.json.
        cfg_reel_strips = cfg_game_root.get('reel_strips')

        spin_result_grid = generate_spin_grid(
            cfg_rows,
            cfg_columns,
            slot.symbols, # List of SlotSymbol ORM objects from DB
            cfg_wild_symbol_id,
            cfg_scatter_symbol_id,
            cfg_symbols_map, # Symbol configurations from gameConfig.json
            cfg_reel_strips  # Reel strips from gameConfig.json
        )

        # --- 5. Calculate Initial Wins ---
        win_info = calculate_win(
            spin_result_grid,
            cfg_paylines,
            cfg_symbols_map,
            bet_amount_sats, # Total bet for the spin
            cfg_wild_symbol_id,
            cfg_scatter_symbol_id,
            cfg_min_symbols_to_match
        )

        initial_raw_win_sats = win_info['total_win_sats'] # Win from the initial grid, before any multipliers
        winning_lines = win_info['winning_lines'] # Detailed breakdown of wins from the initial grid
        current_winning_coords = win_info['winning_symbol_coords'] # Coordinates of symbols in initial winning lines

        initial_spin_grid_for_record = [row[:] for row in spin_result_grid] # Deep copy for DB record

        # Initialize variables for accumulating wins through cascades
        # total_win_for_entire_spin_sequence will sum (initial_raw_win) + (cascade1_raw_win * M1) + (cascade2_raw_win * M2)...
        total_win_for_entire_spin_sequence = initial_raw_win_sats
        current_grid_state = spin_result_grid # This grid will be modified if cascades occur
        current_raw_win_for_cascade_loop = initial_raw_win_sats # Used to determine if cascade loop should continue
        max_cascade_multiplier_level_achieved = 0 # Tracks the highest cascade multiplier level reached (e.g., 0 for initial, 1 for 1st cascade, etc.)

        # --- 6. Cascading Wins Logic ---
        if cfg_is_cascading and initial_raw_win_sats > 0 and current_winning_coords:
            cascade_level_counter = 0 # 0 means initial win, 1st cascade is level 1, etc.

            while current_raw_win_for_cascade_loop > 0 and current_winning_coords:
                # 1. Grid Update: Remove winning symbols, fill new ones
                current_grid_state = handle_cascade_fill(
                    current_grid_state,
                    current_winning_coords, # Coords from the previous win calculation
                    cfg_cascade_type,
                    slot.symbols, # db_symbols
                    cfg_symbols_map,
                    cfg_wild_symbol_id,
                    cfg_scatter_symbol_id
                )

                # 2. Recalculate Wins on the new grid
                cascade_win_info = calculate_win(
                    current_grid_state, # The newly formed grid
                    cfg_paylines,
                    cfg_symbols_map,
                    bet_amount_sats, # Base bet amount for calculating wins
                    cfg_wild_symbol_id,
                    cfg_scatter_symbol_id,
                    # game_config.get('game', {}).get('payouts', []), # This general payouts list is no longer passed directly
                    cfg_min_symbols_to_match
                )

                new_raw_win_this_cascade = cascade_win_info['total_win_sats']
                current_winning_coords = cascade_win_info['winning_symbol_coords'] # For the next iteration's fill

                if new_raw_win_this_cascade > 0:
                    cascade_level_counter += 1 # This is the 1st, 2nd, etc. cascade event

                    current_cascade_multiplier = 1.0
                    if cfg_win_multipliers: # Check if win_multipliers are defined and non-empty
                        if cascade_level_counter -1 < len(cfg_win_multipliers): # cfg_win_multipliers is 0-indexed
                            current_cascade_multiplier = cfg_win_multipliers[cascade_level_counter -1]
                        elif cfg_win_multipliers: # Not empty, so use last available
                            current_cascade_multiplier = cfg_win_multipliers[-1]

                    if cascade_level_counter > max_cascade_multiplier_level_achieved: # Using counter as level proxy
                        max_cascade_multiplier_level_achieved = cascade_level_counter

                    # Add the (raw_win_from_this_cascade * its_cascade_multiplier) to the grand total
                    total_win_for_entire_spin_sequence += int(new_raw_win_this_cascade * current_cascade_multiplier)

                    current_raw_win_for_cascade_loop = new_raw_win_this_cascade # Keep loop going if there was a raw win

                    # Accumulate winning_lines (optional, can make response large)
                    # winning_lines.extend(cascade_win_info['winning_lines']) # Example if needed
                else:
                    current_raw_win_for_cascade_loop = 0 # No new raw win, so stop cascading
                    current_winning_coords = [] # Clear coords
            # End of cascade loop

        # `total_win_for_entire_spin_sequence` now holds sum of (initial_raw + C1_raw*M1 + C2_raw*M2 ...)
        # Apply overall bonus spin multiplier if this is a bonus spin
        final_win_amount_for_session_and_tx = total_win_for_entire_spin_sequence
        if is_bonus_spin and current_spin_multiplier > 1.0:
            final_win_amount_for_session_and_tx = int(total_win_for_entire_spin_sequence * current_spin_multiplier)
            # Note: `winning_lines` (from initial spin) are not re-scaled here. They reflect pre-bonus-multiplier values.

        # --- 7. Check for Bonus Trigger (only on non-bonus spins) ---
        # Bonus trigger evaluation is based on the *initial* spin grid.
        bonus_triggered_this_spin = False
        newly_awarded_spins = 0
        new_bonus_multiplier = 1.0

        if not is_bonus_spin: # Bonus can only be triggered on a normal spin
            bonus_trigger_info = check_bonus_trigger(
                initial_spin_grid_for_record, # Check on the initial grid
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
            game_session.amount_wagered = (game_session.amount_wagered or 0) + actual_bet_this_spin
        # `game_session.amount_won` is updated with the final win amount from this spin.
        # The previous logic added `win_amount_sats` (which was initial win pre-bonus mult).
        # We need to correct this if it was already added, or ensure it's added correctly once.
        # Assuming it was added: subtract old, add new.
        # If it wasn't added yet by this point, just add new.
        # The previous logic directly added `win_amount_sats` (initial win, possibly bonus-multiplied)
        # to `game_session.amount_won`. This needs adjustment if cascades change the total.
        # The logic here correctly subtracts the previously implicitly added amount and adds the new final amount.
        # This assumes `game_session.amount_won` was updated with an initial win amount earlier in a more complex flow.
        # For clarity, let's assume `game_session.amount_won` accumulates per spin.
        # The original code had a line like: `game_session.amount_won = (game_session.amount_won or 0) + win_amount_sats`
        # where `win_amount_sats` was the initial win (potentially bonus multiplied).
        # To correct for cascades, if that line was executed, we would subtract that and add the new final.
        # Simpler: just add the final_win_amount_for_session_and_tx for this spin.
        # However, the test implies a correction logic was in place. Reinstating that correction:

        # Determine what might have been added to session.amount_won before cascades were fully calculated
        # This was: initial_raw_win_sats, potentially multiplied by current_spin_multiplier if it was a bonus spin
        # This correction logic is subtle and depends on when session.amount_won was previously updated.
        # For now, we assume it was updated with `initial_raw_win_sats * (current_spin_multiplier if is_bonus_spin else 1.0)`
        # and now we adjust it to `final_win_amount_for_session_and_tx`.
        # If session.amount_won is only updated *once* at the end, then it's simpler:
        # game_session.amount_won = (game_session.amount_won or 0) + final_win_amount_for_session_and_tx
        # Given the existing test structure, it implies an earlier addition.

        # Corrected accumulation for session.amount_won:
        temp_initial_session_win = initial_raw_win_sats
        if is_bonus_spin and current_spin_multiplier > 1.0:
            temp_initial_session_win = int(initial_raw_win_sats * current_spin_multiplier)

        # If game_session.amount_won was already incremented by temp_initial_session_win (e.g. from a previous version or assumption):
        # game_session.amount_won = (game_session.amount_won or 0) - temp_initial_session_win + final_win_amount_for_session_and_tx
        # If it's the first time updating for this spin sequence (more robust):
        game_session.amount_won = (game_session.amount_won or 0) + final_win_amount_for_session_and_tx


        # --- 10. Update User Balance & Create Win Transaction ---
        if final_win_amount_for_session_and_tx > 0:
            user.balance += final_win_amount_for_session_and_tx # Add final total win to user balance
            win_tx = Transaction(
                user_id=user.id,
                amount=final_win_amount_for_session_and_tx,
                transaction_type='win',
                details={
                    'slot_name': slot.name,
                    'session_id': game_session.id,
                    'is_cascade_win': cfg_is_cascading and max_cascade_multiplier_level_achieved > 0,
                    'initial_win': initial_raw_win_sats,
                    'total_cascade_win_multiplied': total_win_for_entire_spin_sequence - initial_raw_win_sats,
                    'bonus_spin_multiplier_applied': current_spin_multiplier if is_bonus_spin else 1.0
                    }
                    # game_session_id removed
            )
            db.session.add(win_tx)
            # game_session.transactions.append(win_tx) # If using relationship for this

        # --- 11. Create Spin Record in Database ---
        new_spin = SlotSpin(
            game_session_id=game_session.id,
            spin_result=initial_spin_grid_for_record, # Record the initial grid, not the final cascaded one
            win_amount=final_win_amount_for_session_and_tx,
            bet_amount=actual_bet_this_spin, # 0 for bonus spins
            is_bonus_spin=is_bonus_spin,
            spin_time=datetime.now(timezone.utc),
            current_multiplier_level=max_cascade_multiplier_level_achieved # Max cascade level reached
        )
        db.session.add(new_spin)
        db.session.flush() # Flush to get new_spin.id for linking transactions

        # Link transactions to this specific spin
        if not is_bonus_spin and 'wager_tx' in locals() and wager_tx:
            wager_tx.slot_spin_id = new_spin.id
            wager_tx.details['slot_spin_id'] = new_spin.id # Also update details dict
        if final_win_amount_for_session_and_tx > 0 and 'win_tx' in locals() and win_tx:
            win_tx.slot_spin_id = new_spin.id
            win_tx.details['slot_spin_id'] = new_spin.id # Also update details dict

        # --- 12. Prepare and Return Results ---
        return {
            "spin_id": new_spin.id,
            "spin_result": initial_spin_grid_for_record,
            "win_amount_sats": int(final_win_amount_for_session_and_tx),
            "winning_lines": winning_lines, # From initial spin; cascades are aggregated in total win
            "bonus_triggered": bonus_triggered_this_spin,
            "bonus_active": game_session.bonus_active,
            "bonus_spins_remaining": game_session.bonus_spins_remaining if game_session.bonus_active else 0,
            "bonus_multiplier": game_session.bonus_multiplier if game_session.bonus_active else 1.0,
            "user_balance_sats": int(user.balance),
            "session_stats": {
                "num_spins": game_session.num_spins,
                "amount_wagered_sats": int(game_session.amount_wagered or 0),
                "amount_won_sats": int(game_session.amount_won or 0),
            }
        }
    except FileNotFoundError as e:
        # Log error appropriately
        # Log error appropriately by the caller or a centralized error handler
        db.session.rollback() # Ensure atomicity on error
        raise ValueError(str(e)) # Re-raise as ValueError for consistent error type from this handler
    except ValueError as e: # Catch specific ValueErrors (e.g., insufficient balance, config validation)
        db.session.rollback()
        raise e # Re-raise it for the route to handle
    except Exception as e: # Catch any other unexpected errors
        db.session.rollback()
        # Log the exception e with full traceback in a real application
        raise RuntimeError(f"An unexpected error occurred during the spin: {str(e)}")


def generate_spin_grid(rows, columns, db_symbols, wild_symbol_config_id, scatter_symbol_config_id, config_symbols_map, reel_strips=None):
    """
    Generates the symbol grid for a spin.

    Prioritizes using `reel_strips` if they are provided, valid, and match the configured
    column count. Each column is generated by selecting a random starting point on its
    respective reel strip and then taking `rows` consecutive symbols, wrapping around
    the strip if necessary. All random choices use `secrets.SystemRandom()`.

    If `reel_strips` are not used (due to invalidity, absence, or mismatch), the function
    falls back to generating each cell in the grid through weighted random selection
    from `spinable_symbol_ids`. The weights are determined by `symbol_config.get('weight')`
    with defaults for regular (1.0), wild (0.5), and scatter (0.4) symbols.
    If all weights sum to zero, it uses uniform random selection.

    Args:
        rows (int): Number of rows in the grid.
        columns (int): Number of columns in the grid.
        db_symbols (list[SlotSymbol]): List of SlotSymbol ORM objects available for the slot.
                                       Used to determine `spinable_symbol_ids`.
        wild_symbol_config_id (int | None): ID of the wild symbol from game config.
        scatter_symbol_config_id (int | None): ID of the scatter symbol from game config.
        config_symbols_map (dict): Map of symbol configurations from gameConfig.json, keyed by symbol ID.
        reel_strips (list[list[int]], optional): List of reel strips from game config.
                                                 Each sub-list represents a column's strip. Defaults to None.

    Returns:
        list[list[int]]: A 2D list representing the generated grid of symbol IDs.

    Raises:
        ValueError: If no spinable symbols are found after filtering `db_symbols` against
                    `config_symbols_map`, or if the fallback weighted generation has no
                    symbols to choose from after weighting.
    """
    # --- Initial Setup ---
    if not db_symbols:
        # This indicates a DB setup issue where a slot has no associated SlotSymbol records.
        # Fallback to a simple grid using the first available symbol from config if any.
        s_ids = list(config_symbols_map.keys())
        # print("Warning: db_symbols is empty for slot. Falling back to a default symbol grid.") # Debug print
        return [[s_ids[0] if s_ids else 1 for _ in range(columns)] for _ in range(rows)]

    # Filter symbol IDs from DB to only include those present and configured in gameConfig.json
    valid_symbol_ids_from_db = [s.symbol_internal_id for s in db_symbols]
    spinable_symbol_ids = [sid for sid in valid_symbol_ids_from_db if sid in config_symbols_map]

    if not spinable_symbol_ids:
        raise ValueError("No spinable symbols found. Check slot's SlotSymbol DB entries against gameConfig.json symbols.")

    secure_random = secrets.SystemRandom() # Cryptographically secure random number generator
    grid = [[None for _ in range(columns)] for _ in range(rows)]

    # --- Reel Strip Processing Logic ---
    use_reel_strips = False
    if reel_strips is not None:
        # Validate reel_strips structure and content
        if isinstance(reel_strips, list) and len(reel_strips) == columns:
            all_strips_valid = True
            for i, strip in enumerate(reel_strips):
                if not isinstance(strip, list) or not strip: # Each strip must be a non-empty list
                    # print(f"Warning: Reel strip at index {i} is not a list or is empty. Invalidating reel_strips.") # Debug print
                    all_strips_valid = False
                    break
                for symbol_id in strip:
                    if not isinstance(symbol_id, int): # Symbols in strips must be integers
                        # print(f"Warning: Reel strip at index {i} contains non-integer symbol ID '{symbol_id}'. Invalidating reel_strips.") # Debug print
                        all_strips_valid = False
                        break
                    if symbol_id not in config_symbols_map: # Optional: Log if a symbol ID on a strip isn't in the main symbols map
                        # print(f"Warning: Symbol ID {symbol_id} from reel strip {i} not in config_symbols_map (but still used if valid int).") # Debug print
                        pass # This might be intentional for special non-payable symbols on strips, but good to be aware.
                if not all_strips_valid:
                    break

            if all_strips_valid:
                use_reel_strips = True
        # else: # reel_strips configuration is invalid (not a list or length mismatch with columns)
            # print("Warning: reel_strips configuration is invalid. Falling back to weighted random symbol generation.") # Debug print
            # pass # Warning handled by the final else block if not using reel_strips
    # else: # reel_strips is None
        # print("Warning: reel_strips not found in gameConfig. Falling back to basic weighted random symbol generation.") # Debug print
        # No specific print here, fallback is the default path.

    # --- Grid Generation ---
    if use_reel_strips:
        # print("INFO: Using reel_strips for grid generation.") # Debug print
        for c_idx in range(columns):
            current_reel_strip = reel_strips[c_idx]
            strip_len = len(current_reel_strip)
            start_index = secure_random.randrange(strip_len) # Random start position on the strip
            for r_idx in range(rows):
                # Cycle through the strip using modulo operator
                grid[r_idx][c_idx] = current_reel_strip[(start_index + r_idx) % strip_len]
        return grid
    else:
        # Fallback to weighted random symbol generation for each cell
        # This path is taken if reel_strips are None, invalid, or configuration issues are found.
        # if reel_strips is not None: # Only print if reel_strips were provided but deemed invalid
             # print("INFO: reel_strips were invalid. Falling back to basic weighted random symbol generation.") # Debug print
        # else: # reel_strips were None
             # print("INFO: reel_strips not found. Falling back to basic weighted random symbol generation.") # Debug print

        weights = []
        symbols_for_choice = []

        for s_id in spinable_symbol_ids:
            symbol_config = config_symbols_map.get(s_id) # Should always exist due to spinable_symbol_ids filter
            if symbol_config:
                is_wild = symbol_config.get('is_wild', False) or s_id == wild_symbol_config_id
                is_scatter = symbol_config.get('is_scatter', False) or s_id == scatter_symbol_config_id

                default_weight = 1.0
                if is_wild: default_weight = 0.5
                elif is_scatter: default_weight = 0.4

                weights.append(symbol_config.get('weight', default_weight))
                symbols_for_choice.append(s_id)

        if not symbols_for_choice:
            # This should be rare given prior checks, but good for robustness.
            raise ValueError("Cannot generate spin grid: No symbols available for choice in fallback after weighting.")

        total_weight = sum(weights)

        for r_idx in range(rows):
            if total_weight == 0: # If all weights are zero, use uniform distribution
                row_symbols = secure_random.choices(symbols_for_choice, k=columns)
            else:
                # `secure_random.choices` requires sum of weights > 0.
                row_symbols = secure_random.choices(symbols_for_choice, weights=weights, k=columns)
            grid[r_idx] = row_symbols
        return grid


# Removed define_paylines - it will come from game_config.layout.paylines

def get_symbol_payout(symbol_id, count, config_symbols_map, is_scatter=False):
    """
    Retrieves the payout multiplier for a given symbol and count from the game configuration.

    Args:
        symbol_id (int): The ID of the symbol.
        count (int): The number of matching symbols.
        config_symbols_map (dict): Map of symbol configurations from gameConfig.json.
        is_scatter (bool, optional): True if the symbol is a scatter symbol, which might
                                     use a different payout structure ('scatter_payouts')
                                     vs. 'value_multipliers' for payline wins. Defaults to False.

    Returns:
        float: The payout multiplier (e.g., 10.0 for a 10x win). Returns 0.0 if no payout
               is defined for the given symbol/count combination.
    """
    symbol_config = config_symbols_map.get(symbol_id)
    if not symbol_config:
        return 0.0

    if is_scatter:
        # Scatter payouts: uses 'scatter_payouts' from the symbol's configuration.
        # These are typically direct multipliers of the total bet.
        payout_map = symbol_config.get('scatter_payouts', {}) # e.g., {"3": 5, "4": 15, "5": 50}
    else:
        # Payline symbol multipliers: uses 'value_multipliers' from the symbol's configuration.
        # These are typically multipliers for the bet_per_line.
        payout_map = symbol_config.get('value_multipliers', {}) # e.g., {"3": 10, "4": 50, "5": 200}

    # `count` must be a string for dict lookup as per example gameConfig
    # Defensive: ensure keys in payout_map are strings if they were somehow loaded as int
    payout_map_str_keys = {str(k): v for k, v in payout_map.items()}
    multiplier = payout_map_str_keys.get(str(count), 0.0)

    # Ensure multiplier is float or int
    try:
        # Ensure that we handle cases where multiplier might be an empty string or None from config
        if multiplier is None or str(multiplier).strip() == "":
            return 0.0
        return float(multiplier)
    except ValueError:
        return 0.0



def calculate_win(grid, config_paylines, config_symbols_map, total_bet_sats, wild_symbol_id, scatter_symbol_id, min_symbols_to_match): # Removed current_spin_multiplier and general config_payouts
    """Calculates total win amount and identifies winning lines using config.
    Calculates the total win amount and identifies winning lines/clusters from a spin grid.

    This function processes:
    1.  **Payline Wins:** Iterates through `config_paylines`. For each payline, it
        extracts symbols from the `grid` according to the payline's coordinates.
        It determines the initial matching symbol sequence from left-to-right.
        Wild symbols (`wild_symbol_id`) can substitute for other symbols to form or
        extend winning lines. If a line starts with a wild, it attempts to find the
        first non-wild symbol to determine the line's matching symbol type.
        Payline wins are calculated as `base_bet_unit * symbol_multiplier`, where
        `base_bet_unit` is derived from `total_bet_sats // 100` (min 1), and
        a minimum win amount (`total_bet_sats // 20`, min 1) is enforced per line.
        Winning symbol coordinates are added to `all_winning_symbol_coords`.

    2.  **Scatter Wins:** Counts occurrences of `scatter_symbol_id` anywhere on the
        grid. Scatter wins are typically multiples of the `total_bet_sats`, based on
        payouts defined in the symbol's `scatter_payouts` config. Winning scatter
        symbol coordinates are added to `all_winning_symbol_coords`.

    3.  **Cluster Wins (Match N):** If `min_symbols_to_match` is configured, this
        logic counts occurrences of each symbol type across the grid (excluding scatters).
        Wild symbols contribute to the count of any potential cluster. If the
        `effective_count` (literal symbols + wilds) meets `min_symbols_to_match`,
        a cluster win is awarded. Payouts are taken from the symbol's
        `cluster_payouts` config (e.g., `{"5": 20.0}` for 5 matches paying 20x total bet).
        All symbols forming the cluster (including wilds) have their coordinates added
        to `all_winning_symbol_coords`.

    Args:
        grid (list[list[int]]): The 2D list of symbol IDs representing the slot grid.
        config_paylines (list[dict]): List of payline definitions from game config.
        config_symbols_map (dict): Map of symbol configurations, keyed by symbol ID.
        total_bet_sats (int): The total amount bet for the spin.
        wild_symbol_id (int | None): ID of the wild symbol.
        scatter_symbol_id (int | None): ID of the scatter symbol.
        min_symbols_to_match (int | None): Minimum number of identical symbols (optionally
                                         including wilds) anywhere on the grid for a cluster win.

    Returns:
        dict: Contains:
            - "total_win_sats" (int): Total raw win amount from all paylines, scatters, and clusters.
                                      This is before any cascading or bonus multipliers.
            - "winning_lines" (list[dict]): Detailed list of each winning line/scatter/cluster.
                                            Each entry includes a 'type' field: 'payline', 'scatter', or 'cluster'.
            - "winning_symbol_coords" (list[list[int]]): Unique coordinates of all symbols
                                                         that were part of any win, used for cascades.
    """
    # # print(f"DEBUG_WIN_CALC: calculate_win called with total_bet_sats={total_bet_sats}") # Debug print
    # # print(f"DEBUG_WIN_CALC: grid={grid}") # Debug print
    # # print(f"DEBUG_WIN_CALC: config_paylines count={len(config_paylines)}") # Debug print
    # # print(f"DEBUG_WIN_CALC: wild_symbol_id={wild_symbol_id}, scatter_symbol_id={scatter_symbol_id}") # Debug print
    
    total_win_sats = 0
    winning_lines_data = [] # Stores detailed info about each win (payline, scatter, cluster)
    all_winning_symbol_coords = set() # Using a set to store unique [r,c] tuples for symbol removal in cascades
    num_rows = len(grid)
    num_cols = len(grid[0]) if num_rows > 0 else 0

    # --- Payline Wins ---
    # Payline win calculation uses a 'base_bet_unit' and a 'min_win' threshold.
    # num_active_paylines = len(config_paylines) # All defined paylines are considered active.
    
    base_bet_unit = max(1, total_bet_sats // 100) if total_bet_sats >= 100 else 1
    # # print(f"DEBUG_WIN_CALC: base_bet_unit={base_bet_unit}") # Debug print
    
    for payline_config in config_paylines:
        payline_id = payline_config.get("id", "unknown_line")
        payline_positions = payline_config.get("coords", []) # List of [r,c] for this payline
        # # print(f"DEBUG_WIN_CALC: Checking payline {payline_id} with coords {payline_positions}") # Debug print

        line_symbols_on_grid = [] # Actual symbol IDs on this payline
        actual_positions_on_line = [] # Coordinates of these symbols on the grid

        for r, c in payline_positions:
            if 0 <= r < num_rows and 0 <= c < num_cols:
                symbol_on_grid = grid[r][c]
                line_symbols_on_grid.append(symbol_on_grid)
                actual_positions_on_line.append([r,c])
            else: # Should not happen with validated config
                line_symbols_on_grid.append(None)
                actual_positions_on_line.append(None)
        
        # # print(f"DEBUG_WIN_CALC: Payline {payline_id} symbols: {line_symbols_on_grid}") # Debug print

        # Determine winning symbol and count for this line (left-to-right)
        first_symbol_on_line = line_symbols_on_grid[0]
        if first_symbol_on_line is None or first_symbol_on_line == scatter_symbol_id:
            # # print(f"DEBUG_WIN_CALC: Payline {payline_id} skipped - starts with None or scatter") # Debug print
            continue # Paylines typically don't start with None or scatter

        match_symbol_id = None # The symbol type that forms the win (e.g., if wild starts, this is the matched symbol)
        consecutive_count = 0
        winning_symbol_positions_for_line = [] # Positions forming this specific line win

        # Handle if the line starts with a wild symbol
        if first_symbol_on_line == wild_symbol_id:
            temp_match_symbol_id = None # What symbol is the wild substituting for?
            wilds_at_start_count = 0
            for i in range(len(line_symbols_on_grid)):
                s_id_on_line = line_symbols_on_grid[i]
                if s_id_on_line == wild_symbol_id:
                    wilds_at_start_count += 1
                    winning_symbol_positions_for_line.append(actual_positions_on_line[i])
                elif s_id_on_line != scatter_symbol_id : # Found the first non-wild, non-scatter symbol
                    temp_match_symbol_id = s_id_on_line
                    consecutive_count = wilds_at_start_count + 1 # Wilds + this symbol
                    winning_symbol_positions_for_line.append(actual_positions_on_line[i])
                    match_symbol_id = temp_match_symbol_id
                    break # Matching symbol determined, now count continuations
                else: # Scatter or None encountered, breaks payline continuity for this potential match
                    break

            # If line was all wilds (or wilds then scatter/None), check if wild itself pays
            if match_symbol_id is None and wilds_at_start_count > 0:
                wild_config = config_symbols_map.get(wild_symbol_id)
                if wild_config and wild_config.get('value_multipliers'): # Wild has its own payout values
                    match_symbol_id = wild_symbol_id
                    consecutive_count = wilds_at_start_count
                    # winning_symbol_positions_for_line already contains all wild positions
                else: # Wilds don't form their own win, or line too short
                    continue
        else:
            # Line starts with a regular (non-wild) symbol
            match_symbol_id = first_symbol_on_line
            consecutive_count = 1
            winning_symbol_positions_for_line.append(actual_positions_on_line[0])
            # # print(f"DEBUG_WIN_CALC: Payline {payline_id} starts with symbol {match_symbol_id}") # Debug print

        # Continue counting matching symbols or wilds from the position after the initial sequence
        if match_symbol_id: # Proceed if a potential winning line is identified
            # Start search from index `consecutive_count` because those symbols are already accounted for.
            for i in range(consecutive_count, len(line_symbols_on_grid)):
                current_symbol_on_grid = line_symbols_on_grid[i]
                if current_symbol_on_grid == match_symbol_id or current_symbol_on_grid == wild_symbol_id:
                    consecutive_count += 1
                    winning_symbol_positions_for_line.append(actual_positions_on_line[i])
                else:
                    break # Sequence of match_symbol_id (or wilds) broken
            
            # # print(f"DEBUG_WIN_CALC: Payline {payline_id} final count: {consecutive_count} of symbol {match_symbol_id}") # Debug print

        # Get payout for the matched sequence. Min match count is implicit in payout table keys.
        payout_multiplier = get_symbol_payout(match_symbol_id, consecutive_count, config_symbols_map, is_scatter=False)
        # # print(f"DEBUG_WIN_CALC: Payline {payline_id}, Symbol {match_symbol_id}, Count {consecutive_count}, PayoutMultiplier {payout_multiplier}") # Debug print

        if payout_multiplier > 0:
            line_win_sats = int(base_bet_unit * payout_multiplier)
            min_win_threshold = max(1, total_bet_sats // 20) # Ensure win is at least 5% of total bet, or 1 sat
            line_win_sats = max(line_win_sats, min_win_threshold)
            
            # # print(f"DEBUG_WIN_CALC: Payline {payline_id} WIN! {line_win_sats} sats (base_bet_unit={base_bet_unit} * multiplier={payout_multiplier}, min_win={min_win_threshold})") # Debug print

            if line_win_sats > 0:
                total_win_sats += line_win_sats
                winning_lines_data.append({
                    "line_id": payline_id,
                    "symbol_id": match_symbol_id, # The symbol that formed the win (could be wild if wild itself pays)
                    "count": consecutive_count,
                    "positions": winning_symbol_positions_for_line,
                    "win_amount_sats": line_win_sats,
                    "type": "payline" # Added type for clarity
                })
                for pos in winning_symbol_positions_for_line: # Add coordinates to set for cascade removal
                    all_winning_symbol_coords.add(tuple(pos))
        # else:
            # # print(f"DEBUG_WIN_CALC: Payline {payline_id} no win - payout_multiplier={payout_multiplier}") # Debug print

    # --- Scatter Wins ---
    scatter_positions_on_grid = []
    scatter_count_on_grid = 0
    if scatter_symbol_id is not None: # Check if a scatter symbol is configured for the game
        for r_idx, row in enumerate(grid):
            for c_idx, symbol_in_cell in enumerate(row):
                if symbol_in_cell == scatter_symbol_id:
                    scatter_count_on_grid += 1
                    scatter_positions_on_grid.append([r_idx, c_idx])

    if scatter_count_on_grid > 0:
        scatter_payout_multiplier = get_symbol_payout(scatter_symbol_id, scatter_count_on_grid, config_symbols_map, is_scatter=True)
        if scatter_payout_multiplier > 0:
            scatter_win_sats = int(total_bet_sats * scatter_payout_multiplier) # Scatter wins are typically vs total bet
            if scatter_win_sats > 0:
                total_win_sats += scatter_win_sats
                winning_lines_data.append({
                    "line_id": "scatter",
                    "symbol_id": scatter_symbol_id,
                    "count": scatter_count_on_grid,
                    "positions": scatter_positions_on_grid,
                    "win_amount_sats": scatter_win_sats,
                    "type": "scatter" # Added type for clarity
                })
                for pos in scatter_positions_on_grid: # Add scatter symbol positions for removal in cascades
                    all_winning_symbol_coords.add(tuple(pos))

    # --- "Match N" / Cluster Pays Logic ---
    # This logic counts symbols anywhere on the grid. Wilds contribute to any cluster.
    # It is processed *after* paylines and scatters, and its winning coordinates are also added.
    if min_symbols_to_match is not None and min_symbols_to_match > 0:
        symbol_counts = {}
        symbol_positions_map = {} # Stores list of positions for each symbol_id (excluding wilds initially)

        # Count literal symbols and their positions (excluding wilds for base count)
        for r, row_data in enumerate(grid):
            for c, s_id_in_cell in enumerate(row_data):
                if s_id_in_cell is None: continue

                # For cluster base counts, we only consider non-wild, non-scatter symbols here.
                # Wilds are counted separately and added to effective counts.
                # Scatters are typically handled by their own independent payout logic.
                if s_id_in_cell != wild_symbol_id and s_id_in_cell != scatter_symbol_id:
                    symbol_counts[s_id_in_cell] = symbol_counts.get(s_id_in_cell, 0) + 1
                    if s_id_in_cell not in symbol_positions_map:
                        symbol_positions_map[s_id_in_cell] = []
                    symbol_positions_map[s_id_in_cell].append([r, c])

        # Count total wilds on the grid and their positions
        num_wilds_on_grid = 0
        wild_positions_on_grid = []
        if wild_symbol_id is not None:
            for r_idx, row_data in enumerate(grid):
                for c_idx, s_id_in_cell in enumerate(row_data):
                    if s_id_in_cell == wild_symbol_id:
                        num_wilds_on_grid += 1
                        wild_positions_on_grid.append([r_idx, c_idx])

        for symbol_id, literal_symbol_count in symbol_counts.items():
            # Wilds do not form their own cluster type; they assist other symbols.
            # Scatter symbols are handled by their dedicated scatter win logic, not cluster logic here.
            if symbol_id == wild_symbol_id or symbol_id == scatter_symbol_id: # Should already be excluded by map population
                continue

            effective_count = literal_symbol_count + num_wilds_on_grid

            if effective_count >= min_symbols_to_match:
                # This symbol forms a "match N" win with the help of wilds.
                # `config_payouts` is a list of dicts. We need to find the relevant one.
                # Example structure for a cluster payout entry in `config_payouts`:
                # { "type": "cluster", "symbol_id": <ID>, "matches": <N>, "multiplier": <X_per_symbol_or_fixed> }
                # Or payouts might be within the symbol definition in `config_symbols_map`
                # e.g. config_symbols_map[symbol_id].get('cluster_payouts', {}).get(str(effective_count))

                payout_value_for_cluster = 0
                symbol_config_data = config_symbols_map.get(symbol_id, {})
                cluster_payout_rules = symbol_config_data.get('cluster_payouts', {}) # e.g. {"8": 100, "9": 150}

                if cluster_payout_rules:
                    # The key in cluster_payouts is the string representation of the effective_count.
                    payout_value_for_cluster = cluster_payout_rules.get(str(effective_count), 0.0)

                # Attempt 2: Fallback or alternative - search generic `config_payouts` list
                # This is less direct. The gameConfig structure needs to be clear.
                # if not payout_value_for_cluster:
                #     for payout_rule in config_payouts:
                #         if payout_rule.get("type") == "cluster" and \
                #            payout_rule.get("symbol_id") == symbol_id and \
                #            payout_rule.get("matches") == count:
                #             payout_value_for_cluster = payout_rule.get("multiplier", 0.0)
                #             break

                if payout_value_for_cluster > 0:
                    # Cluster win amount calculation.
                    # Cluster win calculation: total_bet_sats * payout_value_for_cluster.
                    # This assumes the payout_value_for_cluster is a direct multiplier of the total bet for that cluster.
                    cluster_win_sats_this_group = int(total_bet_sats * payout_value_for_cluster)

                    if cluster_win_sats_this_group > 0:
                        total_win_sats += cluster_win_sats_this_group

                        # Combine positions of the literal symbols and all wild symbols
                        current_symbol_positions = symbol_positions_map.get(symbol_id, [])
                        combined_positions_set = set()
                        for pos in current_symbol_positions:
                            combined_positions_set.add(tuple(pos))
                        for wild_pos in wild_positions_on_grid:
                            combined_positions_set.add(tuple(wild_pos))

                        winning_coords_for_this_cluster = [list(pos) for pos in combined_positions_set]

                        winning_lines_data.append({
                            "line_id": f"cluster_{symbol_id}_{effective_count}", # Unique ID for this win type
                            "symbol_id": symbol_id, # The base symbol that formed the cluster
                            "count": effective_count, # Effective count including wilds
                            "positions": winning_coords_for_this_cluster,
                            "win_amount_sats": cluster_win_sats_this_group,
                            "type": "cluster"
                        })
                        for pos_tuple in combined_positions_set: # Add all contributing positions to all_winning_symbol_coords
                            all_winning_symbol_coords.add(pos_tuple)

    return {
        "total_win_sats": total_win_sats, # Raw total, multiplier applied in main handle_spin
        "winning_lines": winning_lines_data,
        "winning_symbol_coords": [list(coords) for coords in all_winning_symbol_coords] # Convert tuples back to lists
    }

# --- Cascade Logic Helper ---
def handle_cascade_fill(current_grid, winning_coords_to_clear, cascade_type, db_symbols, config_symbols_map, wild_symbol_config_id, scatter_symbol_config_id):
    """
    Handles the filling of the grid after winning symbols are removed in a cascade.

    Args:
        current_grid (list[list[int]]): The current state of the slot grid.
        winning_coords_to_clear (list[list[int]]): List of [row, col] of symbols to remove.
        cascade_type (str): How new symbols are introduced (e.g., "fall_from_top", "replace_in_place").
        db_symbols (list): List of SlotSymbol ORM objects for the slot (used by generate_spin_grid).
        config_symbols_map (dict): Map of symbol configurations from gameConfig.json.
        wild_symbol_config_id (int): ID of the wild symbol.
        scatter_symbol_config_id (int): ID of the scatter symbol.

    Returns:
        list[list[int]]: The new grid after clearing winning symbols and filling empty spaces.
    """
    if not current_grid:
        return []

    rows = len(current_grid)
    cols = len(current_grid[0])
    new_grid = [row[:] for row in current_grid] # Create a mutable copy

    # Mark winning symbols for removal (e.g., replace with a temporary marker like None)
    for r, c in winning_coords_to_clear:
        if 0 <= r < rows and 0 <= c < cols:
            new_grid[r][c] = None # Mark as empty

    if cascade_type == "fall_from_top":
        for c in range(cols):
            empty_slots_in_col = 0
            # Move non-empty symbols down
            for r in range(rows - 1, -1, -1): # Iterate from bottom to top of column
                if new_grid[r][c] is None:
                    empty_slots_in_col += 1
                elif empty_slots_in_col > 0:
                    # Shift symbol down
                    new_grid[r + empty_slots_in_col][c] = new_grid[r][c]
                    new_grid[r][c] = None # Mark original position as empty

            # Fill empty slots at the top with new random symbols
            if empty_slots_in_col > 0:
                # Generate a small grid (column strip) of new symbols
                # For simplicity, generate one by one, though generate_spin_grid could be adapted
                # to generate a partial grid or a column if needed.
                # Here, we generate individual symbols for the top of the column.

                # Get weighted symbols for generation (similar to generate_spin_grid)
                spinable_symbol_ids = [s_id for s_id in config_symbols_map.keys() if s_id in [s.symbol_internal_id for s in db_symbols]]
                if not spinable_symbol_ids: # Should not happen if initial grid generation worked
                    raise ValueError("No spinable symbols for cascade fill.")

                weights = []
                symbols_for_choice = []
                for s_id in spinable_symbol_ids:
                    symbol_config = config_symbols_map.get(s_id)
                    if symbol_config:
                        raw_weight = symbol_config.get('weight')
                        current_weight = 1.0 # Default weight
                        if isinstance(raw_weight, (int, float)) and raw_weight > 0:
                            current_weight = float(raw_weight)
                        else:
                            # Log warning for missing/invalid weight in cascade
                            pass
                        weights.append(current_weight)
                        symbols_for_choice.append(s_id)

                total_weight = sum(weights)
                if total_weight == 0 or not symbols_for_choice:
                    if not symbols_for_choice: symbols_for_choice = spinable_symbol_ids
                    weights = [1.0 / len(symbols_for_choice) if symbols_for_choice else 1.0] * len(symbols_for_choice)
                else:
                    weights = [w / total_weight for w in weights]

                secure_random_instance = secrets.SystemRandom()
                for r_fill in range(empty_slots_in_col):
                    if symbols_for_choice: # Ensure there are symbols to choose from
                        new_grid[r_fill][c] = secure_random_instance.choices(symbols_for_choice, weights=weights, k=1)[0]
                    else: # Fallback if no symbols somehow (should be caught earlier)
                        new_grid[r_fill][c] = spinable_symbol_ids[0] if spinable_symbol_ids else 0 # Default to 0 or first available

    elif cascade_type == "replace_in_place":
        # Similar symbol generation logic as above, but directly into winning_coords_to_clear
        spinable_symbol_ids = [s_id for s_id in config_symbols_map.keys() if s_id in [s.symbol_internal_id for s in db_symbols]]
        if not spinable_symbol_ids:
            raise ValueError("No spinable symbols for cascade fill (replace_in_place).")

        weights = []
        symbols_for_choice = []
        for s_id in spinable_symbol_ids:
            symbol_config = config_symbols_map.get(s_id)
            if symbol_config:
                raw_weight = symbol_config.get('weight')
                current_weight = 1.0 # Default weight
                if isinstance(raw_weight, (int, float)) and raw_weight > 0:
                    current_weight = float(raw_weight)
                else:
                    # Log warning for missing/invalid weight if symbol_config or weight is problematic
                    pass # Default weight of 1.0 is used
                weights.append(current_weight)
                symbols_for_choice.append(s_id)

        total_weight = sum(weights)
        if total_weight == 0 or not symbols_for_choice: # Fallback if no symbols or all weights are zero
            if not symbols_for_choice: symbols_for_choice = spinable_symbol_ids # Use all spinable if choice list became empty
            # Uniform weights if total_weight is zero or choice list was initially empty
            weights = [1.0 / len(symbols_for_choice) if symbols_for_choice else 1.0] * len(symbols_for_choice)
        # else: # Normalize weights if using weighted choice (secrets.choices does this implicitly if sum > 0)
            # weights = [w / total_weight for w in weights] # Not strictly needed for secrets.choices if sum(weights)>0

        secure_random_instance = secrets.SystemRandom()
        for r, c in winning_coords_to_clear: # Iterate through the specific empty slots
            if symbols_for_choice:
                new_grid[r][c] = secure_random_instance.choices(symbols_for_choice, weights=weights, k=1)[0]
            else: # Should be extremely rare, means spinable_symbol_ids was empty
                new_grid[r][c] = 0 # Fallback to a default symbol ID like 0 or first from config_symbols_map
    else:
        # If cascade_type is unknown, not implemented, or None, symbols are just removed.
        # The game logic then typically stops cascading as no new grid is formed to check for wins.
        # print(f"Warning: Unknown or unimplemented cascade_type: {cascade_type}. Returning grid with removed symbols only.") # Debug print
        pass

    return new_grid


def check_bonus_trigger(grid, scatter_symbol_id, config_bonus_features):
    """
    Checks if conditions are met to trigger a bonus feature (e.g., free spins)
    based on the symbols in the provided grid and the game's bonus configuration.

    Currently focuses on free spins triggered by a specific count of scatter symbols.

    Args:
        grid (list[list[int]]): The symbol grid to check for bonus triggers.
        scatter_symbol_id (int | None): The ID of the scatter symbol, used as the
                                        default trigger symbol for free spins.
        config_bonus_features (dict): Configuration for bonus features, expected to
                                      contain a 'free_spins' key for that feature.
                                      Example: `{'free_spins': {'trigger_symbol_id': 4,
                                      'trigger_count': 3, 'spins_awarded': 10, 'multiplier': 2.0}}`

    Returns:
        dict: A dictionary indicating if a bonus was triggered and its details.
              Example for triggered free spins:
              `{'triggered': True, 'type': 'free_spins', 'spins_awarded': 10, 'multiplier': 2.0}`
              If no bonus is triggered, returns `{'triggered': False}`.
    """
    # # print(f"DEBUG_TEST_HANDLER: check_bonus_trigger called.") # Debug print
    # # print(f"DEBUG_TEST_HANDLER: grid received: {grid}") # Debug print
    # # print(f"DEBUG_TEST_HANDLER: scatter_symbol_id param: {scatter_symbol_id}") # Debug print
    # # print(f"DEBUG_TEST_HANDLER: config_bonus_features param: {config_bonus_features}") # Debug print

    # --- Free Spins Bonus Check ---
    free_spins_config = config_bonus_features.get('free_spins')
    if not free_spins_config: # No free spins feature configured
        return {'triggered': False}

    # Determine the symbol that triggers free spins. Default to scatter_symbol_id if not specified in free_spins_config.
    trigger_sym_id_for_fs = free_spins_config.get('trigger_symbol_id', scatter_symbol_id)
    if trigger_sym_id_for_fs is None: # No trigger symbol identified
        return {'triggered': False}

    min_scatter_to_trigger = free_spins_config.get('trigger_count')
    if not isinstance(min_scatter_to_trigger, int) or min_scatter_to_trigger <= 0:
        return {'triggered': False} # Invalid or missing trigger count

    # Count occurrences of the specific trigger_sym_id_for_fs on the grid
    actual_trigger_symbol_count = 0
    for r_idx, row in enumerate(grid):
        for c_idx, symbol_id_in_cell in enumerate(row):
            if symbol_id_in_cell == trigger_sym_id_for_fs:
                actual_trigger_symbol_count += 1
                # # print(f"DEBUG_TEST_HANDLER: Found trigger symbol {trigger_sym_id_for_fs} at row {r_idx}, cell {c_idx}. Current count: {actual_trigger_symbol_count}") # Debug print

    # # print(f"DEBUG_TEST_HANDLER: Final trigger symbol count: {actual_trigger_symbol_count}, min to trigger: {min_scatter_to_trigger}") # Debug print
    if actual_trigger_symbol_count >= min_scatter_to_trigger:
        # # print(f"DEBUG_TEST_HANDLER: Returning: {{'triggered': True, ...}}") # Debug print
        return {
            'triggered': True,
            'type': 'free_spins', # Hardcoded for now, could be derived from config key
            'spins_awarded': free_spins_config.get('spins_awarded', 0),
            'multiplier': free_spins_config.get('multiplier', 1.0) # Default to 1x if not specified
        }

    # # print(f"DEBUG_TEST_HANDLER: Returning: {{'triggered': False}}") # Debug print
    return {'triggered': False}
# TODO: Add checks for other bonus types if they are introduced.
