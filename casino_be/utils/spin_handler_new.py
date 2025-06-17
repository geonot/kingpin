import json
import os
import secrets
from datetime import datetime, timezone
from flask import current_app
from casino_be.models import db, SlotSpin, GameSession, User, Transaction, UserBonus

def load_game_config(slot_short_name):
    """
    Loads the game configuration JSON file for a given slot and validates its structure.
    It first tries a path relative to the 'casino_be/public/slots' directory,
    then falls back to a path relative to 'casino_fe/public/slots' for flexibility
    in development or deployment setups.

    Args:
        slot_short_name (str): The short name of the slot, used to find its configuration file.

    Returns:
        dict: The loaded and validated game configuration object.

    Raises:
        FileNotFoundError: If the configuration file for the slot cannot be found in any expected location.
        ValueError: If the JSON is malformed or if the configuration structure is invalid
                    (as per `_validate_game_config`).
        RuntimeError: For other unexpected errors during loading.
    """
    # Construct primary path relative to the 'casino_be' package directory
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'public', 'slots'))
    file_path = os.path.join(base_dir, slot_short_name, "gameConfig.json")

    if not os.path.exists(file_path):
        # Fallback path for alternative project structures (e.g., during development)
        alt_base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'casino_fe', 'public', 'slots'))
        alt_file_path = os.path.join(alt_base_dir, slot_short_name, "gameConfig.json")
        current_app.logger.info(f"Configuration for '{slot_short_name}' not found at primary path '{file_path}', trying fallback: {alt_file_path}")
        if os.path.exists(alt_file_path):
            file_path = alt_file_path
        else:
            current_app.logger.error(f"Configuration file critical error: Not found for slot '{slot_short_name}' at primary '{file_path}' or fallback '{alt_file_path}'")
            raise FileNotFoundError(f"Configuration file not found for slot '{slot_short_name}' at {file_path} (also checked {alt_file_path})")

    try:
        with open(file_path, 'r') as f:
            config = json.load(f)
        _validate_game_config(config, slot_short_name)
        current_app.logger.info(f"Successfully loaded and validated config for '{slot_short_name}' from {file_path}")
        return config
    except FileNotFoundError:
        current_app.logger.error(f"Game config file not found at {file_path} for slot '{slot_short_name}' (re-throw after path resolution)")
        raise
    except json.JSONDecodeError as e:
        current_app.logger.error(f"JSON decode error for {file_path} (slot '{slot_short_name}'): {e.msg} at line {e.lineno} col {e.colno}")
        raise ValueError(f"Invalid JSON in {file_path}: {e.msg} (line {e.lineno}, col {e.colno})")
    except ValueError as e:
        current_app.logger.error(f"Configuration validation error for slot '{slot_short_name}': {str(e)}")
        raise
    except Exception as e:
        current_app.logger.error(f"Unexpected error loading game config for '{slot_short_name}' from {file_path}: {type(e).__name__} - {str(e)}")
        raise RuntimeError(f"Could not load game config for slot '{slot_short_name}': {str(e)}")


def _validate_game_config(config, slot_short_name):
    """
    Validates the structure and essential content of a game configuration object.
    Ensures critical keys and data types are present for game operation.

    Args:
        config (dict): The game configuration object (typically loaded from JSON).
        slot_short_name (str): The short name of the slot, used for clear error messaging.

    Raises:
        ValueError: If any validation check fails.
    """
    if not isinstance(config, dict):
        raise ValueError(f"Config validation error for slot '{slot_short_name}': Root must be a dictionary.")
    game = config.get('game')
    if not isinstance(game, dict):
        raise ValueError(f"Config validation error for slot '{slot_short_name}': 'game' key must be a dictionary.")

    # Essential game properties
    for key, key_type, can_be_empty in [('name', str, False), ('short_name', str, False)]:
        value = game.get(key)
        if not isinstance(value, key_type) or (not can_be_empty and not str(value).strip()):
            raise ValueError(f"Config validation error for slot '{slot_short_name}': game.{key} must be a non-empty {key_type.__name__}.")

    layout = game.get('layout')
    if not isinstance(layout, dict): 
        raise ValueError(f"Config validation error for slot '{slot_short_name}': game.layout must be a dictionary.")
    rows = layout.get('rows')
    if not isinstance(rows, int) or rows <= 0: 
        raise ValueError(f"Config validation error for slot '{slot_short_name}': game.layout.rows must be a positive integer.")
    columns = layout.get('columns')
    if not isinstance(columns, int) or columns <= 0: 
        raise ValueError(f"Config validation error for slot '{slot_short_name}': game.layout.columns must be a positive integer.")

    # Additional validation can be added here
    
    
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

    Raises:
        FileNotFoundError: If the `gameConfig.json` for the slot is not found.
        ValueError: If the bet amount is invalid, user has insufficient balance for a paid spin,
                    or if there's a critical configuration error.
        RuntimeError: For other unexpected errors during spin processing.
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
        cfg_is_cascading = game_config.get('game', {}).get('is_cascading', False)
        cfg_cascade_type = game_config.get('game', {}).get('cascade_type', None)
        cfg_min_symbols_to_match = game_config.get('game', {}).get('min_symbols_to_match', None)
        cfg_win_multipliers = game_config.get('game', {}).get('win_multipliers', [])
        cfg_reel_strips = game_config.get('game', {}).get('reel_strips')

        # --- Pre-Spin Validation ---
        if not isinstance(bet_amount_sats, int) or bet_amount_sats <= 0:
            raise ValueError("Invalid bet amount. Must be a positive integer (satoshis).")

        # Check if bet is compatible with payline system
        num_paylines = len(cfg_paylines)
        if num_paylines > 0 and bet_amount_sats % num_paylines != 0:
            next_valid_bet = ((bet_amount_sats // num_paylines) + 1) * num_paylines
            prev_valid_bet = (bet_amount_sats // num_paylines) * num_paylines
            if prev_valid_bet == 0:
                prev_valid_bet = num_paylines
            
            raise ValueError(f"Bet amount ({bet_amount_sats} sats) must be evenly divisible by number of paylines ({num_paylines}). "
                            f"Try {prev_valid_bet} or {next_valid_bet} sats instead.")

        # --- Update Wagering Progress if Active Bonus (for PAID spins) ---
        actual_bet_this_spin_for_wagering = 0
        if not (game_session.bonus_active and game_session.bonus_spins_remaining > 0):
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

        # --- Determine Spin Type and Deduct Bet ---
        is_bonus_spin = False
        current_spin_multiplier = 1.0

        if game_session.bonus_active and game_session.bonus_spins_remaining > 0:
            is_bonus_spin = True
            current_spin_multiplier = game_session.bonus_multiplier
            game_session.bonus_spins_remaining -= 1
            actual_bet_this_spin = 0
        else:
            # CRITICAL: Re-check balance atomically to prevent race conditions
            db.session.refresh(user)
            
            if user.balance < bet_amount_sats:
                raise ValueError("Insufficient balance - balance changed during processing")
            
            # Atomic balance deduction
            user.balance -= bet_amount_sats
            actual_bet_this_spin = bet_amount_sats
            
            # Create Wager Transaction
            wager_tx = Transaction(
                user_id=user.id,
                amount=-bet_amount_sats,
                transaction_type='wager',
                details={'slot_name': slot.name, 'session_id': game_session.id}
            )
            db.session.add(wager_tx)

        # --- Generate Spin Result ---
        spin_result_grid = generate_spin_grid(
            cfg_rows,
            cfg_columns,
            slot.symbols,
            cfg_wild_symbol_id,
            cfg_scatter_symbol_id,
            cfg_symbols_map,
            cfg_reel_strips
        )

        # --- Calculate Wins ---
        win_info = calculate_win(
            spin_result_grid,
            cfg_paylines,
            cfg_symbols_map,
            bet_amount_sats,
            cfg_wild_symbol_id,
            cfg_scatter_symbol_id,
            cfg_min_symbols_to_match
        )

        initial_raw_win_sats = win_info['total_win_sats']
        winning_lines = win_info['winning_lines']
        
        # Store initial grid for SlotSpin record
        initial_spin_grid_for_record = [row[:] for row in spin_result_grid]
        
        # Initialize total win
        total_win_for_entire_spin_sequence = initial_raw_win_sats
        max_cascade_multiplier_level_achieved = 0

        # --- Cascading Wins Logic ---
        if cfg_is_cascading and initial_raw_win_sats > 0:
            current_grid_state = spin_result_grid
            current_winning_coords = win_info['winning_symbol_coords']
            cascade_level_counter = 0

            while current_winning_coords:
                current_grid_state = handle_cascade_fill(
                    current_grid_state,
                    current_winning_coords,
                    cfg_cascade_type,
                    slot.symbols,
                    cfg_symbols_map,
                    cfg_wild_symbol_id,
                    cfg_scatter_symbol_id
                )

                cascade_win_info = calculate_win(
                    current_grid_state,
                    cfg_paylines,
                    cfg_symbols_map,
                    bet_amount_sats,
                    cfg_wild_symbol_id,
                    cfg_scatter_symbol_id,
                    cfg_min_symbols_to_match
                )

                new_raw_win_this_cascade = cascade_win_info['total_win_sats']
                current_winning_coords = cascade_win_info['winning_symbol_coords']

                if new_raw_win_this_cascade > 0:
                    cascade_level_counter += 1
                    cascade_multiplier = 1.0
                    
                    if cfg_win_multipliers:
                        if cascade_level_counter - 1 < len(cfg_win_multipliers):
                            cascade_multiplier = cfg_win_multipliers[cascade_level_counter - 1]
                        elif cfg_win_multipliers:
                            cascade_multiplier = cfg_win_multipliers[-1]

                    if cascade_level_counter > max_cascade_multiplier_level_achieved:
                        max_cascade_multiplier_level_achieved = cascade_level_counter

                    total_win_for_entire_spin_sequence += int(new_raw_win_this_cascade * cascade_multiplier)
                else:
                    current_winning_coords = []

        # Apply bonus spin multiplier if applicable
        final_win_amount_for_session_and_tx = total_win_for_entire_spin_sequence
        if is_bonus_spin and current_spin_multiplier > 1.0:
            final_win_amount_for_session_and_tx = int(total_win_for_entire_spin_sequence * current_spin_multiplier)

        # --- Check for Bonus Trigger (on non-bonus spins) ---
        bonus_triggered_this_spin = False
        if not is_bonus_spin:
            bonus_trigger_info = check_bonus_trigger(
                initial_spin_grid_for_record,
                cfg_scatter_symbol_id,
                cfg_bonus_features
            )
            if bonus_trigger_info['triggered']:
                bonus_triggered_this_spin = True
                newly_awarded_spins = bonus_trigger_info.get('spins_awarded', 0)
                new_bonus_multiplier = bonus_trigger_info.get('multiplier', 1.0)

                if not game_session.bonus_active:
                    game_session.bonus_active = True
                    game_session.bonus_spins_remaining = newly_awarded_spins
                    game_session.bonus_multiplier = new_bonus_multiplier
                else:
                    game_session.bonus_spins_remaining += newly_awarded_spins

        # End bonus if no spins remaining
        if game_session.bonus_active and game_session.bonus_spins_remaining <= 0:
            game_session.bonus_active = False
            game_session.bonus_multiplier = 1.0

        # --- Update Session Aggregates ---
        game_session.num_spins += 1
        if not is_bonus_spin:
            game_session.amount_wagered = (game_session.amount_wagered or 0) + actual_bet_this_spin
        game_session.amount_won = (game_session.amount_won or 0) + final_win_amount_for_session_and_tx

        # --- Create Win Transaction and Update Balance ---
        if final_win_amount_for_session_and_tx > 0:
            user.balance += final_win_amount_for_session_and_tx
            win_tx = Transaction(
                user_id=user.id,
                amount=final_win_amount_for_session_and_tx,
                transaction_type='win',
                details={
                    'slot_name': slot.name,
                    'session_id': game_session.id,
                    'is_cascade_win': cfg_is_cascading and max_cascade_multiplier_level_achieved > 0
                }
            )
            db.session.add(win_tx)

        # --- Create Spin Record ---
        new_spin = SlotSpin(
            game_session_id=game_session.id,
            spin_result=initial_spin_grid_for_record,
            win_amount=final_win_amount_for_session_and_tx,
            bet_amount=actual_bet_this_spin,
            is_bonus_spin=is_bonus_spin,
            spin_time=datetime.now(timezone.utc),
            current_multiplier_level=max_cascade_multiplier_level_achieved
        )
        db.session.add(new_spin)

        return {
            "spin_result": initial_spin_grid_for_record,
            "win_amount_sats": int(final_win_amount_for_session_and_tx),
            "winning_lines": winning_lines,
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
        current_app.logger.error(f"Configuration file not found: {str(e)}")
        db.session.rollback()
        raise ValueError(str(e))
    except ValueError as e:
        current_app.logger.warning(f"Validation error during spin: {str(e)}")
        db.session.rollback()
        raise e
    except Exception as e:
        current_app.logger.error(f"Unexpected error during spin: {type(e).__name__} - {str(e)}")
        db.session.rollback()
        raise RuntimeError(f"An unexpected error occurred during the spin: {str(e)}")


def generate_spin_grid(rows, columns, db_symbols, wild_symbol_config_id, scatter_symbol_config_id, config_symbols_map, reel_strips=None):
    """
    Generates the symbol grid for a spin.
    """
    if not db_symbols:
        s_ids = list(config_symbols_map.keys())
        current_app.logger.warning("db_symbols is empty in generate_spin_grid. Falling back to default symbol grid.")
        return [[int(s_ids[0]) if s_ids else 1 for _ in range(columns)] for _ in range(rows)]

    secure_random = secrets.SystemRandom()
    grid = [[None for _ in range(columns)] for _ in range(rows)]

    # Use reel strips if available and valid
    if reel_strips and isinstance(reel_strips, list) and len(reel_strips) == columns:
        current_app.logger.info("Using reel_strips for grid generation.")
        for c_idx in range(columns):
            current_reel_strip = reel_strips[c_idx]
            strip_len = len(current_reel_strip)
            if strip_len == 0:
                raise ValueError(f"Reel strip {c_idx} is empty.")
            start_index = secure_random.randrange(strip_len)
            for r_idx in range(rows):
                grid[r_idx][c_idx] = current_reel_strip[(start_index + r_idx) % strip_len]
        return grid
    else:
        # Use weighted random generation
        current_app.logger.info("Using weighted random symbol generation for grid.")
        for r_idx in range(rows):
            grid[r_idx] = _generate_weighted_random_symbols(
                columns, config_symbols_map, db_symbols, secure_random,
                wild_symbol_config_id, scatter_symbol_config_id
            )
        return grid


def _generate_weighted_random_symbols(count, config_symbols_map, db_symbols, secure_random_instance, wild_symbol_config_id=None, scatter_symbol_config_id=None):
    """
    Generates a list of symbols using weighted random selection.
    """
    valid_db_internal_ids = {s.symbol_internal_id for s in db_symbols}

    spinable_config_symbol_ids = [
        int(s_id_str) for s_id_str, s_config in config_symbols_map.items()
        if isinstance(s_id_str, (int, str)) and str(s_id_str).isdigit()
        and int(s_id_str) in valid_db_internal_ids
    ]

    if not spinable_config_symbol_ids:
        current_app.logger.warning("No DB-validated spinable symbols during weighted generation. Using fallback.")
        spinable_config_symbol_ids = [int(s_id_str) for s_id_str in config_symbols_map.keys() 
                                     if isinstance(s_id_str, (int, str)) and str(s_id_str).isdigit()]
        if not spinable_config_symbol_ids:
            raise ValueError("No numeric symbol IDs available in config_symbols_map for generation.")

    weights = []
    symbols_for_choice = []
    for s_id in spinable_config_symbol_ids:
        symbol_config = config_symbols_map.get(s_id) or config_symbols_map.get(str(s_id))
        if not symbol_config:
            continue

        current_weight = 1.0
        raw_weight = symbol_config.get('weight')

        if isinstance(raw_weight, (int, float)) and raw_weight > 0:
            current_weight = float(raw_weight)
        else:
            is_wild = symbol_config.get('is_wild', False) or (wild_symbol_config_id is not None and s_id == wild_symbol_config_id)
            is_scatter = symbol_config.get('is_scatter', False) or (scatter_symbol_config_id is not None and s_id == scatter_symbol_config_id)
            if is_wild and current_weight == 1.0: 
                current_weight = 0.5
            elif is_scatter and current_weight == 1.0: 
                current_weight = 0.4

        weights.append(current_weight)
        symbols_for_choice.append(s_id)

    if not symbols_for_choice:
        raise ValueError("Cannot generate symbols: No symbols available for choice after filtering and weighting.")

    total_weight = sum(weights)
    if total_weight <= 0:
        current_app.logger.warning(f"Total weight is {total_weight}. Using uniform distribution for {count} symbols.")
        return secure_random_instance.choices(symbols_for_choice, k=count)
    else:
        return secure_random_instance.choices(symbols_for_choice, weights=weights, k=count)


def calculate_win(grid, config_paylines, config_symbols_map, total_bet_sats, wild_symbol_id, scatter_symbol_id, min_symbols_to_match):
    """Calculates total win amount and identifies winning lines using config."""
    total_win_sats = 0
    winning_lines_data = []
    all_winning_symbol_coords = set()
    num_rows = len(grid)
    num_cols = len(grid[0]) if num_rows > 0 else 0

    # Calculate bet per payline
    num_active_paylines = len(config_paylines)
    bet_per_payline = total_bet_sats / num_active_paylines if num_active_paylines > 0 else total_bet_sats
    
    # Payline wins
    for payline_config in config_paylines:
        payline_id = payline_config.get("id", "unknown_line")
        payline_positions = payline_config.get("coords", [])
        
        line_symbols_on_grid = []
        actual_positions_on_line = []

        # Extract symbols from grid following payline coordinates
        for r, c in payline_positions:
            if 0 <= r < num_rows and 0 <= c < num_cols:
                symbol_on_grid = grid[r][c]
                line_symbols_on_grid.append(symbol_on_grid)
                actual_positions_on_line.append([r, c])
            else:
                line_symbols_on_grid.append(None)
                actual_positions_on_line.append(None)

        # Skip if payline starts with invalid position
        first_symbol = line_symbols_on_grid[0] if line_symbols_on_grid else None
        if first_symbol is None or first_symbol == scatter_symbol_id:
            continue

        # Count consecutive matching symbols from left
        match_symbol_id = first_symbol
        consecutive_count = 1
        winning_positions = [actual_positions_on_line[0]]

        # Handle wild substitution at start
        if first_symbol == wild_symbol_id:
            # Find first non-wild to determine match type
            for i in range(1, len(line_symbols_on_grid)):
                symbol = line_symbols_on_grid[i]
                if symbol != wild_symbol_id and symbol != scatter_symbol_id and symbol is not None:
                    match_symbol_id = symbol
                    break
            else:
                # All wilds - check if wilds have their own payout
                wild_config = config_symbols_map.get(wild_symbol_id, {})
                if not wild_config.get('value_multipliers'):
                    continue
                match_symbol_id = wild_symbol_id

        # Count consecutive matches including wilds
        for i in range(1, len(line_symbols_on_grid)):
            symbol = line_symbols_on_grid[i]
            if symbol == match_symbol_id or symbol == wild_symbol_id:
                consecutive_count += 1
                if actual_positions_on_line[i] is not None:
                    winning_positions.append(actual_positions_on_line[i])
            else:
                break

        # Calculate payout
        payout_multiplier = get_symbol_payout(match_symbol_id, consecutive_count, config_symbols_map, is_scatter=False)
        
        if payout_multiplier > 0:
            line_win_sats = int(bet_per_payline * payout_multiplier)
            total_win_sats += line_win_sats
            winning_lines_data.append({
                "line_id": payline_id,
                "symbol_id": match_symbol_id,
                "count": consecutive_count,
                "positions": winning_positions,
                "win_amount_sats": line_win_sats
            })
            for pos in winning_positions:
                all_winning_symbol_coords.add(tuple(pos))

    # Scatter wins
    scatter_positions = []
    scatter_count = 0
    if scatter_symbol_id is not None:
        for r in range(num_rows):
            for c in range(num_cols):
                if grid[r][c] == scatter_symbol_id:
                    scatter_count += 1
                    scatter_positions.append([r, c])

    scatter_payout = get_symbol_payout(scatter_symbol_id, scatter_count, config_symbols_map, is_scatter=True)
    if scatter_payout > 0:
        scatter_win = int(total_bet_sats * scatter_payout)
        total_win_sats += scatter_win
        winning_lines_data.append({
            "line_id": "scatter",
            "symbol_id": scatter_symbol_id,
            "count": scatter_count,
            "positions": scatter_positions,
            "win_amount_sats": scatter_win
        })
        for pos in scatter_positions:
            all_winning_symbol_coords.add(tuple(pos))

    # Cluster logic if enabled
    if min_symbols_to_match is not None and min_symbols_to_match > 0:
        symbol_counts = {}
        symbol_positions = {}
        
        for r in range(num_rows):
            for c in range(num_cols):
                symbol = grid[r][c]
                if symbol != wild_symbol_id and symbol != scatter_symbol_id and symbol is not None:
                    symbol_counts[symbol] = symbol_counts.get(symbol, 0) + 1
                    if symbol not in symbol_positions:
                        symbol_positions[symbol] = []
                    symbol_positions[symbol].append([r, c])

        # Count wilds
        wild_count = 0
        wild_positions = []
        if wild_symbol_id is not None:
            for r in range(num_rows):
                for c in range(num_cols):
                    if grid[r][c] == wild_symbol_id:
                        wild_count += 1
                        wild_positions.append([r, c])

        # Check cluster wins
        for symbol_id, count in symbol_counts.items():
            effective_count = count + wild_count
            if effective_count >= min_symbols_to_match:
                symbol_config = config_symbols_map.get(symbol_id, {})
                cluster_payouts = symbol_config.get('cluster_payouts', {})
                cluster_multiplier = float(cluster_payouts.get(str(effective_count), 0.0))
                
                if cluster_multiplier > 0:
                    cluster_win = int(total_bet_sats * cluster_multiplier)
                    total_win_sats += cluster_win
                    
                    all_positions = symbol_positions.get(symbol_id, []) + wild_positions
                    winning_lines_data.append({
                        "line_id": f"cluster_{symbol_id}_{effective_count}",
                        "symbol_id": symbol_id,
                        "count": effective_count,
                        "positions": all_positions,
                        "win_amount_sats": cluster_win,
                        "type": "cluster"
                    })
                    for pos in all_positions:
                        all_winning_symbol_coords.add(tuple(pos))

    return {
        "total_win_sats": total_win_sats,
        "winning_lines": winning_lines_data,
        "winning_symbol_coords": [list(coords) for coords in all_winning_symbol_coords]
    }


def get_symbol_payout(symbol_id, count, config_symbols_map, is_scatter=False):
    """
    Retrieves the payout multiplier for a given symbol and count.
    """
    symbol_config = config_symbols_map.get(symbol_id)
    if not symbol_config: 
        return 0.0

    payout_key = 'scatter_payouts' if is_scatter else 'value_multipliers'
    payout_map = symbol_config.get(payout_key, {})

    payout_map_str_keys = {str(k): v for k, v in payout_map.items()}
    multiplier = payout_map_str_keys.get(str(count), 0.0)

    try:
        if multiplier is None or str(multiplier).strip() == "": 
            return 0.0
        return float(multiplier)
    except ValueError:
        current_app.logger.warning(f"Invalid multiplier value '{multiplier}' for symbol {symbol_id}, count {count}. Defaulting to 0.0.")
        return 0.0


def handle_cascade_fill(current_grid, winning_coords_to_clear, cascade_type, db_symbols, config_symbols_map, wild_symbol_config_id, scatter_symbol_config_id):
    """
    Handles the filling of the grid after winning symbols are removed in a cascade.
    """
    if not current_grid:
        return []

    rows = len(current_grid)
    cols = len(current_grid[0])
    new_grid = [row[:] for row in current_grid]

    for r, c in winning_coords_to_clear:
        if 0 <= r < rows and 0 <= c < cols:
            new_grid[r][c] = None

    if cascade_type == "fall_from_top":
        for c_idx_fill in range(cols):
            empty_slots_in_col = 0
            for r_idx_fill in range(rows - 1, -1, -1):
                if new_grid[r_idx_fill][c_idx_fill] is None:
                    empty_slots_in_col += 1
                elif empty_slots_in_col > 0:
                    new_grid[r_idx_fill + empty_slots_in_col][c_idx_fill] = new_grid[r_idx_fill][c_idx_fill]
                    new_grid[r_idx_fill][c_idx_fill] = None

            if empty_slots_in_col > 0:
                secure_random_instance = secrets.SystemRandom()
                new_symbols_for_col = _generate_weighted_random_symbols(
                    empty_slots_in_col, config_symbols_map, db_symbols,
                    secure_random_instance, wild_symbol_config_id, scatter_symbol_config_id
                )
                for r_fill_new in range(empty_slots_in_col):
                    new_grid[r_fill_new][c_idx_fill] = new_symbols_for_col[r_fill_new]

    elif cascade_type == "replace_in_place":
        secure_random_instance = secrets.SystemRandom()
        coords_to_fill = []
        for r_idx_fill in range(rows):
            for c_idx_fill in range(cols):
                if new_grid[r_idx_fill][c_idx_fill] is None:
                    coords_to_fill.append((r_idx_fill, c_idx_fill))

        num_to_replace = len(coords_to_fill)
        if num_to_replace > 0:
            new_symbols = _generate_weighted_random_symbols(
                num_to_replace, config_symbols_map, db_symbols,
                secure_random_instance, wild_symbol_config_id, scatter_symbol_config_id
            )
            for i, (r_coord, c_coord) in enumerate(coords_to_fill):
                new_grid[r_coord][c_coord] = new_symbols[i]

    return new_grid


def check_bonus_trigger(grid, scatter_symbol_id, config_bonus_features):
    """
    Checks if conditions are met to trigger a bonus feature (e.g., free spins).
    """
    free_spins_config = config_bonus_features.get('free_spins')
    if not free_spins_config:
        return {'triggered': False}
    
    min_scatter_to_trigger = free_spins_config.get('trigger_count')
    if not isinstance(min_scatter_to_trigger, int) or min_scatter_to_trigger <= 0:
        return {'triggered': False}

    scatter_count = 0
    for r_idx, row in enumerate(grid):
        for c_idx, symbol_id_in_cell in enumerate(row):
            if symbol_id_in_cell == scatter_symbol_id:
                scatter_count += 1

    if scatter_count >= min_scatter_to_trigger:
        spins_awarded = free_spins_config.get('spins_awarded', 10)
        multiplier = free_spins_config.get('multiplier', 1.0)
        
        return {
            'triggered': True,
            'spins_awarded': spins_awarded,
            'multiplier': multiplier,
            'trigger_symbol_count': scatter_count
        }
    
    return {'triggered': False}
