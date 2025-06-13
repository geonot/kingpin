import random
import json
import os
import secrets
from datetime import datetime, timezone
from ..models import db, SlotSpin, GameSession, User, Transaction, UserBonus

# --- Configuration ---
# SLOT_CONFIG_BASE_PATH = "public/slots" # Example, actual path construction is dynamic

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
        # NOTE_LOG: LOG_INFO: f"Configuration for '{slot_short_name}' not found at primary path '{file_path}', trying fallback: {alt_file_path}"
        if os.path.exists(alt_file_path):
            file_path = alt_file_path
        else:
            # NOTE_LOG: LOG_ERROR: f"Configuration file critical error: Not found for slot '{slot_short_name}' at primary '{file_path}' or fallback '{alt_file_path}'"
            raise FileNotFoundError(f"Configuration file not found for slot '{slot_short_name}' at {file_path} (also checked {alt_file_path})")

    try:
        with open(file_path, 'r') as f:
            config = json.load(f)
        _validate_game_config(config, slot_short_name)
        # NOTE_LOG: LOG_INFO: f"Successfully loaded and validated config for '{slot_short_name}' from {file_path}"
        return config
    except FileNotFoundError:
        # NOTE_LOG: LOG_ERROR: f"Game config file not found at {file_path} for slot '{slot_short_name}' (re-throw after path resolution)"
        raise # Re-raise the FileNotFoundError if it somehow occurs after path checks
    except json.JSONDecodeError as e:
        # NOTE_LOG: LOG_ERROR: f"JSON decode error for {file_path} (slot '{slot_short_name}'): {e.msg} at line {e.lineno} col {e.colno}"
        raise ValueError(f"Invalid JSON in {file_path}: {e.msg} (line {e.lineno}, col {e.colno})")
    except ValueError as e: # Catch validation errors from _validate_game_config
        # NOTE_LOG: LOG_ERROR: f"Configuration validation error for slot '{slot_short_name}': {str(e)}"
        raise # Re-raise validation errors
    except Exception as e:
        # NOTE_LOG: LOG_ERROR: f"Unexpected error loading game config for '{slot_short_name}' from {file_path}: {type(e).__name__} - {str(e)}"
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
    if not isinstance(layout, dict): raise ValueError(f"Config validation error for slot '{slot_short_name}': game.layout must be a dictionary.")
    rows = layout.get('rows')
    if not isinstance(rows, int) or rows <= 0: raise ValueError(f"Config validation error for slot '{slot_short_name}': game.layout.rows must be a positive integer.")
    columns = layout.get('columns')
    if not isinstance(columns, int) or columns <= 0: raise ValueError(f"Config validation error for slot '{slot_short_name}': game.layout.columns must be a positive integer.")

    paylines = layout.get('paylines', []) # Paylines can be empty for cluster/scatter-only games
    if not isinstance(paylines, list): raise ValueError(f"Config validation error for slot '{slot_short_name}': game.layout.paylines must be a list.")
    for i, pl in enumerate(paylines):
        if not isinstance(pl, dict): raise ValueError(f"Config validation error for slot '{slot_short_name}': game.layout.paylines[{i}] must be a dictionary.")
        if 'id' not in pl or 'coords' not in pl: raise ValueError(f"Config validation error for slot '{slot_short_name}': game.layout.paylines[{i}] must have 'id' and 'coords'.")
        if not isinstance(pl['coords'], list): raise ValueError(f"Config validation error for slot '{slot_short_name}': game.layout.paylines[{i}].coords must be a list.")
        for j, coord in enumerate(pl['coords']):
            if not (isinstance(coord, list) and len(coord) == 2 and isinstance(coord[0], int) and isinstance(coord[1], int)):
                raise ValueError(f"Config validation error for slot '{slot_short_name}': game.layout.paylines[{i}].coords[{j}] must be a list of two integers.")
            r, c = coord
            if not (0 <= r < rows and 0 <= c < columns): raise ValueError(f"Config validation error for slot '{slot_short_name}': game.layout.paylines[{i}].coords[{j}] ([{r},{c}]) out of bounds (rows: {rows}, cols: {columns}).")

    symbols_data = game.get('symbols')
    if not isinstance(symbols_data, list) or not symbols_data: raise ValueError(f"Config validation error for slot '{slot_short_name}': game.symbols must be a non-empty list.")
    collected_symbol_ids = set()
    for i, sym in enumerate(symbols_data):
        if not isinstance(sym, dict): raise ValueError(f"Config validation error for slot '{slot_short_name}': game.symbols[{i}] must be a dictionary.")
        for key_info in [('id', int, False), ('name', str, False), ('icon', str, True)]: # Icon can be empty string if not used
            key_name, key_type, can_be_empty_str = key_info
            val = sym.get(key_name)
            if not isinstance(val, key_type) or (key_type == str and not can_be_empty_str and not str(val).strip()):
                 raise ValueError(f"Config validation error for slot '{slot_short_name}': game.symbols[{i}].{key_name} must be a valid non-empty {key_type.__name__} (or allowed empty for icon).")
            if key_name == 'id': collected_symbol_ids.add(val)
        if sym.get('weight') is not None and not (isinstance(sym.get('weight'), (int, float)) and sym.get('weight') > 0):
            raise ValueError(f"Config validation error for slot '{slot_short_name}': game.symbols[{i}].weight must be a positive number if present.")
        for opt_key, opt_type in [('is_wild', bool), ('is_scatter', bool), ('value_multipliers', dict), ('scatter_payouts', dict), ('cluster_payouts', dict)]:
            if opt_key in sym and not isinstance(sym[opt_key], opt_type): raise ValueError(f"Config validation error for slot '{slot_short_name}': game.symbols[{i}].{opt_key} must be a {opt_type.__name__} if present.")

    for special_key in ['wild_symbol_id', 'scatter_symbol_id']:
        s_id = game.get(special_key)
        if s_id is not None and (not isinstance(s_id, int) or s_id not in collected_symbol_ids):
            raise ValueError(f"Config validation error for slot '{slot_short_name}': game.{special_key} ID {s_id} is invalid or not found in defined symbols.")

    reel_strips = game.get('reel_strips') # Optional
    if reel_strips is not None:
        if not isinstance(reel_strips, list) or len(reel_strips) != columns:
            raise ValueError(f"Config validation error for slot '{slot_short_name}': game.reel_strips must be a list matching column count if present.")
        for i, strip in enumerate(reel_strips):
            if not isinstance(strip, list) or not strip: raise ValueError(f"Config validation error for slot '{slot_short_name}': game.reel_strips[{i}] must be a non-empty list.")
            for j, s_id in enumerate(strip):
                if not isinstance(s_id, int) or s_id not in collected_symbol_ids:
                     raise ValueError(f"Config validation error for slot '{slot_short_name}': game.reel_strips[{i}][{j}] ID {s_id} is invalid or not in defined symbols.")

    bonus_features = game.get('bonus_features') # Optional
    if bonus_features is not None:
        if not isinstance(bonus_features, dict): raise ValueError(f"Config validation error for slot '{slot_short_name}': game.bonus_features must be a dictionary if present.")
        free_spins = bonus_features.get('free_spins') # Optional free spins feature
        if free_spins is not None:
            if not isinstance(free_spins, dict): raise ValueError(f"Config validation error for slot '{slot_short_name}': game.bonus_features.free_spins must be a dictionary.")
            fs_trigger_id = free_spins.get('trigger_symbol_id')
            if not isinstance(fs_trigger_id, int) or fs_trigger_id not in collected_symbol_ids:
                raise ValueError(f"Config validation error for slot '{slot_short_name}': game.bonus_features.free_spins.trigger_symbol_id must be a valid symbol ID.")
            if not (isinstance(free_spins.get('trigger_count'), int) and free_spins.get('trigger_count') > 0):
                raise ValueError(f"Config validation error for slot '{slot_short_name}': game.bonus_features.free_spins.trigger_count must be a positive integer.")
            if not (isinstance(free_spins.get('spins_awarded'), int) and free_spins.get('spins_awarded') >= 0):
                raise ValueError(f"Config validation error for slot '{slot_short_name}': game.bonus_features.free_spins.spins_awarded must be a non-negative integer.")
            if not (isinstance(free_spins.get('multiplier'), (int, float)) and free_spins.get('multiplier') >= 1.0):
                 raise ValueError(f"Config validation error for slot '{slot_short_name}': game.bonus_features.free_spins.multiplier must be a number >= 1.0.")

    if 'is_cascading' in game and not isinstance(game['is_cascading'], bool): raise ValueError(f"Config validation error for slot '{slot_short_name}': game.is_cascading must be a boolean if present.")
    if game.get('min_symbols_to_match') is not None and (not isinstance(game.get('min_symbols_to_match'), int) or game.get('min_symbols_to_match') <= 0):
        raise ValueError(f"Config validation error for slot '{slot_short_name}': game.min_symbols_to_match must be a positive integer if present.")
    if game.get('is_cascading'):
        if game.get('cascade_type') not in ["fall_from_top", "replace_in_place"]:
            raise ValueError(f"Config validation error for slot '{slot_short_name}': game.cascade_type must be 'fall_from_top' or 'replace_in_place' if is_cascading is true.")
        win_multipliers = game.get('win_multipliers')
        if win_multipliers is not None and (not isinstance(win_multipliers, list) or not all(isinstance(m, (int, float)) and m > 0 for m in win_multipliers)):
            raise ValueError(f"Config validation error for slot '{slot_short_name}': game.win_multipliers must be a list of positive numbers if present and is_cascading is true.")


# --- Helper Functions for handle_spin ---

def _load_and_prepare_config(slot_short_name):
    """
    Loads and prepares the game configuration for a specific slot.

    This involves loading the raw JSON configuration, then extracting and structuring
    key parameters into a dictionary for easier access during spin processing.

    Args:
        slot_short_name (str): The short name of the slot machine.

    Returns:
        dict: A dictionary containing structured configuration data.
    """
    game_config = load_game_config(slot_short_name)
    cfg_game_root = game_config.get('game', {})
    cfg_layout = cfg_game_root.get('layout', {})

    return {
        "game_config": game_config,
        "symbols_map": {s['id']: s for s in cfg_game_root.get('symbols', [])},
        "paylines": cfg_layout.get('paylines', []),
        "rows": cfg_layout.get('rows', 3),
        "columns": cfg_layout.get('columns', 5),
        "wild_symbol_id": cfg_game_root.get('wild_symbol_id'),
        "scatter_symbol_id": cfg_game_root.get('scatter_symbol_id'),
        "bonus_features": cfg_game_root.get('bonus_features', {}),
        "is_cascading": cfg_game_root.get('is_cascading', False),
        "cascade_type": cfg_game_root.get('cascade_type'),
        "min_symbols_to_match": cfg_game_root.get('min_symbols_to_match'),
        "win_multipliers": cfg_game_root.get('win_multipliers', []),
        "reel_strips": cfg_game_root.get('reel_strips')
    }

def _validate_bet_and_balance(user_balance, bet_amount_sats, game_session_bonus_active, game_session_spins_remaining, num_paylines_from_config):
    """
    Validates the bet amount against game rules and user's balance.

    Args:
        user_balance (int): Current balance of the user.
        bet_amount_sats (int): The amount bet by the user.
        game_session_bonus_active (bool): If a bonus round is active.
        game_session_spins_remaining (int): Number of free spins remaining.
        num_paylines_from_config (int): Number of paylines for the slot.

    Raises:
        ValueError: If bet amount is invalid or balance is insufficient.
    """
    if not isinstance(bet_amount_sats, int) or bet_amount_sats <= 0:
        raise ValueError("Invalid bet amount. Must be a positive integer (satoshis).")
    if num_paylines_from_config > 0 and bet_amount_sats % num_paylines_from_config != 0:
        next_valid_bet = ((bet_amount_sats // num_paylines_from_config) + 1) * num_paylines_from_config
        prev_valid_bet = (bet_amount_sats // num_paylines_from_config) * num_paylines_from_config
        if prev_valid_bet == 0: prev_valid_bet = num_paylines_from_config
        raise ValueError(
            f"Bet amount ({bet_amount_sats} sats) must be evenly divisible by number of paylines ({num_paylines_from_config}). "
            f"Try {prev_valid_bet} or {next_valid_bet} sats instead."
        )
    if not (game_session_bonus_active and game_session_spins_remaining > 0):
        if user_balance < bet_amount_sats:
            raise ValueError("Insufficient balance for this bet.")

def _update_wagering_progress(user_id, bet_amount_sats, game_session):
    """
    Updates wagering progress for an active bonus if the spin is paid.

    Args:
        user_id (int): The ID of the user.
        bet_amount_sats (int): The amount bet (if a paid spin).
        game_session (GameSession): The current game session.
    """
    if not (game_session.bonus_active and game_session.bonus_spins_remaining > 0) and bet_amount_sats > 0:
        active_bonus = UserBonus.query.filter_by(
            user_id=user_id, is_active=True, is_completed=False, is_cancelled=False
        ).first()
        if active_bonus:
            active_bonus.wagering_progress_sats += bet_amount_sats
            active_bonus.updated_at = datetime.now(timezone.utc)
            # NOTE_LOG: LOG_INFO: f"User {user_id} wagering progress for bonus {active_bonus.id}: {active_bonus.wagering_progress_sats}/{active_bonus.wagering_requirement_sats}"
            if active_bonus.wagering_progress_sats >= active_bonus.wagering_requirement_sats:
                active_bonus.is_active = False
                active_bonus.is_completed = True
                active_bonus.completed_at = datetime.now(timezone.utc)
                # NOTE_LOG: LOG_INFO: f"User {user_id} completed wagering for UserBonus {active_bonus.id}."

def _process_bet_deduction_and_type(user, game_session, bet_amount_sats, slot_name):
    """
    Determines spin type, deducts bet, and creates wager transaction.

    Args:
        user (User): The user object.
        game_session (GameSession): The current game session.
        bet_amount_sats (int): The bet amount.
        slot_name (str): The name of the slot.

    Returns:
        tuple: (is_bonus_spin, current_spin_multiplier, actual_bet_this_spin, wager_tx_obj)
    """
    wager_tx = None
    if game_session.bonus_active and game_session.bonus_spins_remaining > 0:
        is_bonus_spin = True
        current_spin_multiplier = game_session.bonus_multiplier
        game_session.bonus_spins_remaining -= 1
        actual_bet_this_spin = 0
        # NOTE_LOG: LOG_INFO: f"User {user.id} using bonus spin for slot {slot_name}. Spins remaining: {game_session.bonus_spins_remaining}"
    else:
        is_bonus_spin = False
        current_spin_multiplier = 1.0
        user.balance -= bet_amount_sats
        actual_bet_this_spin = bet_amount_sats
        wager_tx = Transaction(
            user_id=user.id, amount=-actual_bet_this_spin, transaction_type='wager',
            details={'slot_name': slot_name, 'session_id': game_session.id}
        )
        db.session.add(wager_tx)
    return is_bonus_spin, current_spin_multiplier, actual_bet_this_spin, wager_tx

def _calculate_initial_and_cascading_wins(initial_spin_grid, slot_symbols_db, config_params, bet_amount_sats_for_calc):
    """
    Calculates initial win and subsequent cascading wins.

    Args:
        initial_spin_grid (list[list[int]]): The starting grid for the spin.
        slot_symbols_db (list): ORM objects for slot symbols (used for cascade fill).
        config_params (dict): Prepared configuration dictionary.
        bet_amount_sats_for_calc (int): Bet amount for win calculations.

    Returns:
        dict: Results including total win, initial win, winning lines, and cascade level.
    """
    current_grid_state = [row[:] for row in initial_spin_grid]
    win_info = calculate_win(
        current_grid_state, config_params['paylines'], config_params['symbols_map'],
        bet_amount_sats_for_calc, config_params['wild_symbol_id'],
        config_params['scatter_symbol_id'], config_params['min_symbols_to_match']
    )

    initial_raw_win_sats = win_info['total_win_sats']
    winning_lines_from_initial_spin = win_info['winning_lines']
    current_winning_coords = win_info['winning_symbol_coords']

    total_win_for_entire_spin_sequence = initial_raw_win_sats
    current_raw_win_for_cascade_loop = initial_raw_win_sats
    max_cascade_multiplier_level_achieved = 0

    if config_params['is_cascading'] and initial_raw_win_sats > 0 and current_winning_coords:
        # NOTE_LOG: LOG_INFO: f"Cascade initiated. Initial win: {initial_raw_win_sats}, Bet: {bet_amount_sats_for_calc}"
        cascade_level_counter = 0
        while current_raw_win_for_cascade_loop > 0 and current_winning_coords:
            current_grid_state = handle_cascade_fill(
                current_grid_state, current_winning_coords, config_params['cascade_type'],
                slot_symbols_db, config_params['symbols_map'],
                config_params['wild_symbol_id'], config_params['scatter_symbol_id']
            )
            cascade_win_info = calculate_win(
                current_grid_state, config_params['paylines'], config_params['symbols_map'],
                bet_amount_sats_for_calc, config_params['wild_symbol_id'],
                config_params['scatter_symbol_id'], config_params['min_symbols_to_match']
            )
            new_raw_win_this_cascade = cascade_win_info['total_win_sats']
            current_winning_coords = cascade_win_info['winning_symbol_coords']

            if new_raw_win_this_cascade > 0:
                cascade_level_counter += 1
                cascade_multiplier = 1.0
                if config_params['win_multipliers']:
                    if cascade_level_counter - 1 < len(config_params['win_multipliers']):
                        cascade_multiplier = config_params['win_multipliers'][cascade_level_counter - 1]
                    elif config_params['win_multipliers']: # Not empty, use last if counter exceeds
                        cascade_multiplier = config_params['win_multipliers'][-1]

                if cascade_level_counter > max_cascade_multiplier_level_achieved:
                    max_cascade_multiplier_level_achieved = cascade_level_counter

                total_win_for_entire_spin_sequence += int(new_raw_win_this_cascade * cascade_multiplier)
                current_raw_win_for_cascade_loop = new_raw_win_this_cascade
                # NOTE_LOG: LOG_INFO: f"Cascade level {cascade_level_counter} win: {new_raw_win_this_cascade}, multiplier: {cascade_multiplier}. Cumulative raw: {total_win_for_entire_spin_sequence}"
            else:
                current_raw_win_for_cascade_loop = 0
                current_winning_coords = []

    return {
        "total_win_for_entire_spin_sequence": total_win_for_entire_spin_sequence,
        "initial_raw_win_sats": initial_raw_win_sats,
        "winning_lines_from_initial_spin": winning_lines_from_initial_spin,
        "max_cascade_multiplier_level_achieved": max_cascade_multiplier_level_achieved
    }

def _apply_bonus_spin_multiplier(total_win_for_entire_spin_sequence, is_bonus_spin, current_spin_multiplier):
    """
    Applies overall bonus multiplier to the total sequence win if it's a bonus spin.

    Args:
        total_win_for_entire_spin_sequence (int): Accumulated win from initial spin and cascades.
        is_bonus_spin (bool): True if the spin is part of a bonus round.
        current_spin_multiplier (float): The multiplier for the bonus round.

    Returns:
        int: Win amount after applying the bonus multiplier.
    """
    if is_bonus_spin and current_spin_multiplier > 1.0:
        return int(total_win_for_entire_spin_sequence * current_spin_multiplier)
    return total_win_for_entire_spin_sequence

def _check_and_apply_bonus_trigger(game_session, initial_spin_grid_for_record, cfg_scatter_symbol_id, cfg_bonus_features, is_bonus_spin):
    """
    Checks for bonus triggers and updates game session state.

    Args:
        game_session (GameSession): The current game session.
        initial_spin_grid_for_record (list[list[int]]): The initial grid result.
        cfg_scatter_symbol_id (int | None): Scatter symbol ID from config.
        cfg_bonus_features (dict): Bonus features configuration.
        is_bonus_spin (bool): Whether the current spin is already a bonus spin.

    Returns:
        bool: True if a bonus was triggered or re-triggered this spin.
    """
    bonus_triggered_this_spin = False
    if not is_bonus_spin:
        bonus_trigger_info = check_bonus_trigger(
            initial_spin_grid_for_record, cfg_scatter_symbol_id, cfg_bonus_features
        )
        if bonus_trigger_info['triggered']:
            bonus_triggered_this_spin = True
            newly_awarded_spins = bonus_trigger_info.get('spins_awarded', 0)
            new_bonus_multiplier = bonus_trigger_info.get('multiplier', 1.0)
            if not game_session.bonus_active:
                game_session.bonus_active = True
                game_session.bonus_spins_remaining = newly_awarded_spins
                game_session.bonus_multiplier = new_bonus_multiplier
                # NOTE_LOG: LOG_INFO: f"Bonus activated for session {game_session.id}. Awarded spins: {newly_awarded_spins}, Multiplier: {new_bonus_multiplier}"
            else:
                game_session.bonus_spins_remaining += newly_awarded_spins
                if new_bonus_multiplier != game_session.bonus_multiplier and newly_awarded_spins > 0 :
                     game_session.bonus_multiplier = new_bonus_multiplier
                # NOTE_LOG: LOG_INFO: f"Bonus re-triggered/extended for session {game_session.id}. Spins added: {newly_awarded_spins}. Total remaining: {game_session.bonus_spins_remaining}."

    if game_session.bonus_active and game_session.bonus_spins_remaining <= 0:
        game_session.bonus_active = False
        game_session.bonus_multiplier = 1.0
        # NOTE_LOG: LOG_INFO: f"Bonus round ended for session {game_session.id}."

    return bonus_triggered_this_spin

def _update_session_aggregates(game_session, actual_bet_this_spin, final_win_amount_for_session_and_tx, is_bonus_spin):
    """
    Updates game session aggregates (spin count, wagered, won).

    Args:
        game_session (GameSession): The current game session.
        actual_bet_this_spin (int): Bet amount for this spin.
        final_win_amount_for_session_and_tx (int): Final win for this spin.
        is_bonus_spin (bool): If it was a bonus spin.
    """
    game_session.num_spins += 1
    if not is_bonus_spin:
        game_session.amount_wagered = (game_session.amount_wagered or 0) + actual_bet_this_spin
    game_session.amount_won = (game_session.amount_won or 0) + final_win_amount_for_session_and_tx

def _create_spin_record_and_transactions(user, slot_name, game_session_id, final_win_amount_sats,
                                         actual_bet_sats, is_bonus_spin, initial_spin_grid,
                                         max_cascade_level, cfg_is_cascading, initial_raw_win,
                                         total_win_sequence, current_bonus_multiplier_val, wager_tx_obj):
    """
    Creates SlotSpin record, win transaction, and links them. Updates user balance.

    Args:
        user (User): The user.
        slot_name (str): Name of the slot.
        game_session_id (int): Current game session ID.
        final_win_amount_sats (int): Final win from the spin sequence.
        actual_bet_sats (int): Actual bet amount for the spin.
        is_bonus_spin (bool): True if it was a bonus spin.
        initial_spin_grid (list[list[int]]): The initial grid state.
        max_cascade_level (int): Max cascade level achieved.
        cfg_is_cascading (bool): Whether the slot is cascading.
        initial_raw_win (int): Raw win from the initial grid.
        total_win_sequence (int): Total raw win from initial + cascades (with cascade multipliers).
        current_bonus_multiplier_val (float): Overall bonus multiplier for the spin.
        wager_tx_obj (Transaction | None): The wager transaction object, if any.

    Returns:
        int: ID of the new SlotSpin record.
    """
    win_tx_obj = None
    if final_win_amount_sats > 0:
        user.balance += final_win_amount_sats
        win_tx_obj = Transaction(
            user_id=user.id, amount=final_win_amount_sats, transaction_type='win',
            details={
                'slot_name': slot_name, 'session_id': game_session_id,
                'is_cascade_win': cfg_is_cascading and max_cascade_level > 0,
                'initial_win': initial_raw_win,
                'total_cascade_win_multiplied': total_win_sequence - initial_raw_win,
                'bonus_spin_multiplier_applied': current_bonus_multiplier_val if is_bonus_spin else 1.0
            }
        )
        db.session.add(win_tx_obj)

    new_spin = SlotSpin(
        game_session_id=game_session_id, spin_result=initial_spin_grid,
        win_amount=final_win_amount_sats, bet_amount=actual_bet_sats,
        is_bonus_spin=is_bonus_spin, spin_time=datetime.now(timezone.utc),
        current_multiplier_level=max_cascade_level
    )
    db.session.add(new_spin)
    db.session.flush()

    if wager_tx_obj:
        wager_tx_obj.slot_spin_id = new_spin.id
        if wager_tx_obj.details:
             wager_tx_obj.details['slot_spin_id'] = new_spin.id
        else:
             wager_tx_obj.details = {'slot_spin_id': new_spin.id}

    if win_tx_obj:
        win_tx_obj.slot_spin_id = new_spin.id
        if win_tx_obj.details:
            win_tx_obj.details['slot_spin_id'] = new_spin.id

    return new_spin.id

# --- Main Spin Handler ---
def handle_spin(user, slot, game_session, bet_amount_sats):
    """
    Orchestrates the slot spin process using helper functions.
    (Full docstring from original file)
    """
    # NOTE_LOG: LOG_INFO: f"User {user.id}, Slot {slot.id}, Session {game_session.id}: Starting handle_spin with bet {bet_amount_sats} sats."
    try:
        config = _load_and_prepare_config(slot.short_name)
        config['bet_amount_sats'] = bet_amount_sats

        _validate_bet_and_balance(user.balance, bet_amount_sats,
                                  game_session.bonus_active, game_session.bonus_spins_remaining,
                                  len(config['paylines']))
        _update_wagering_progress(user.id, bet_amount_sats, game_session)

        is_bonus_spin, current_spin_multiplier, actual_bet_this_spin, wager_tx = \
            _process_bet_deduction_and_type(user, game_session, bet_amount_sats, slot.name)

        spin_result_grid = generate_spin_grid(
            config['rows'], config['columns'], slot.symbols,
            config['wild_symbol_id'], config['scatter_symbol_id'],
            config['symbols_map'], config['reel_strips']
        )
        initial_spin_grid_for_record = [row[:] for row in spin_result_grid]

        # Pass bet_amount_sats_for_calc to _calculate_initial_and_cascading_wins
        # This should be actual_bet_this_spin if we want wins based on actual stake,
        # or bet_amount_sats if wins are always calculated on original bet even for bonus spins (config dependent)
        # For typical slots, payouts are based on the original bet that initiated the spin or bonus round.
        # If bonus spins have a fixed bet value, that should be used. Here, using original bet_amount_sats.
        cascade_results = _calculate_initial_and_cascading_wins(
            initial_spin_grid_for_record,
            slot.symbols,
            config, # Contains bet_amount_sats
            bet_amount_sats # Explicitly pass bet_amount_sats for win calculation base
        )
        # NOTE_LOG: LOG_DEBUG: f"User {user.id}, Slot {slot.id}: Cascade results: {cascade_results}"

        final_win_amount_for_session_and_tx = _apply_bonus_spin_multiplier(
            cascade_results['total_win_for_entire_spin_sequence'],
            is_bonus_spin,
            current_spin_multiplier
        )

        if config['is_cascading'] and cascade_results['max_cascade_multiplier_level_achieved'] > 0:
            # NOTE_LOG: LOG_INFO: f"User {user.id}, Slot {slot.id}: Cascade occurred. Max level: {cascade_results['max_cascade_multiplier_level_achieved']}, Initial raw: {cascade_results['initial_raw_win_sats']}, Total sequence raw: {cascade_results['total_win_for_entire_spin_sequence']}"
            pass

        bonus_triggered_this_spin = _check_and_apply_bonus_trigger(
            game_session, initial_spin_grid_for_record,
            config['scatter_symbol_id'], config['bonus_features'], is_bonus_spin
        )
        if bonus_triggered_this_spin:
            # NOTE_LOG: LOG_INFO: f"User {user.id}, Slot {slot.id}: Bonus triggered. Spins remaining: {game_session.bonus_spins_remaining}, Multiplier: {game_session.bonus_multiplier}"
            pass

        _update_session_aggregates(game_session, actual_bet_this_spin, final_win_amount_for_session_and_tx, is_bonus_spin)

        new_spin_id = _create_spin_record_and_transactions(
            user, slot.name, game_session.id, final_win_amount_for_session_and_tx,
            actual_bet_this_spin, is_bonus_spin, initial_spin_grid_for_record,
            cascade_results['max_cascade_multiplier_level_achieved'], config['is_cascading'],
            cascade_results['initial_raw_win_sats'], cascade_results['total_win_for_entire_spin_sequence'],
            current_spin_multiplier, wager_tx
        )

        # NOTE_LOG: LOG_INFO: f"User {user.id}, Slot {slot.id}, Session {game_session.id}: Spin processed successfully. Spin ID: {new_spin_id}, Final Win: {final_win_amount_for_session_and_tx} sats."
        return {
            "spin_id": new_spin_id,
            "spin_result": initial_spin_grid_for_record,
            "win_amount_sats": int(final_win_amount_for_session_and_tx),
            "winning_lines": cascade_results['winning_lines_from_initial_spin'],
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
        # NOTE_LOG: LOG_ERROR: f"User {user.id if user else 'UnknownUser'}, Slot {slot.short_name if slot else 'UnknownSlot'}: Configuration file not found. Error: {str(e)}"
        db.session.rollback()
        raise ValueError(str(e))
    except ValueError as e:
        # NOTE_LOG: LOG_WARNING: f"User {user.id if user else 'UnknownUser'}, Slot {slot.short_name if slot else 'UnknownSlot'}: Validation error during spin (bet: {bet_amount_sats}). Error: {str(e)}"
        db.session.rollback()
        raise e
    except Exception as e:
        # NOTE_LOG: LOG_ERROR: f"User {user.id if user else 'UnknownUser'}, Slot {slot.short_name if slot else 'UnknownSlot'}: Unexpected error during spin (bet: {bet_amount_sats}). Error: {type(e).__name__} - {str(e)}"
        db.session.rollback()
        raise RuntimeError(f"An unexpected error occurred during the spin: {str(e)}")


def generate_spin_grid(rows, columns, db_symbols, wild_symbol_config_id, scatter_symbol_config_id, config_symbols_map, reel_strips=None):
    """
    Generates the symbol grid for a spin.
    (Full docstring from original file)
    """
    if not db_symbols:
        s_ids = list(config_symbols_map.keys())
        # NOTE_LOG: LOG_WARNING: "db_symbols is empty in generate_spin_grid. Falling back to a default symbol grid using first config symbol."
        return [[int(s_ids[0]) if s_ids else 1 for _ in range(columns)] for _ in range(rows)]

    secure_random = secrets.SystemRandom()
    grid = [[None for _ in range(columns)] for _ in range(rows)]

    use_reel_strips = False
    if reel_strips is not None:
        if isinstance(reel_strips, list) and len(reel_strips) == columns:
            all_strips_valid = True
            for i, strip in enumerate(reel_strips):
                if not isinstance(strip, list) or not strip:
                    # NOTE_LOG: LOG_WARNING: f"Reel strip at index {i} is not a list or is empty. Invalidating reel_strips usage."
                    all_strips_valid = False; break
                for symbol_id in strip:
                    if not isinstance(symbol_id, int):
                        # NOTE_LOG: LOG_WARNING: f"Reel strip at index {i} contains non-integer symbol ID '{symbol_id}'. Invalidating reel_strips usage."
                        all_strips_valid = False; break
                if not all_strips_valid: break
            if all_strips_valid: use_reel_strips = True
        # else: # NOTE_LOG: LOG_WARNING: "reel_strips configuration is invalid (not a list or length mismatch). Falling back."
            pass
    # else: # NOTE_LOG: LOG_INFO: "reel_strips not found. Using weighted random generation."
        pass

    if use_reel_strips:
        # NOTE_LOG: LOG_INFO: "Using reel_strips for grid generation."
        for c_idx in range(columns):
            current_reel_strip = reel_strips[c_idx]
            strip_len = len(current_reel_strip)
            if strip_len == 0:
                # NOTE_LOG: LOG_ERROR: f"Reel strip {c_idx} is empty. Cannot generate grid from it."
                raise ValueError(f"Reel strip {c_idx} is empty.")
            start_index = secure_random.randrange(strip_len)
            for r_idx in range(rows):
                grid[r_idx][c_idx] = current_reel_strip[(start_index + r_idx) % strip_len]
        return grid
    else:
        # NOTE_LOG: LOG_INFO: "Using weighted random symbol generation for grid."
        for r_idx in range(rows):
            grid[r_idx] = _generate_weighted_random_symbols(
                columns, config_symbols_map, db_symbols, secure_random,
                wild_symbol_config_id, scatter_symbol_config_id
            )
        return grid


def get_symbol_payout(symbol_id, count, config_symbols_map, is_scatter=False):
    """
    Retrieves the payout multiplier for a given symbol and count.
    (Full docstring from original file)
    """
    symbol_config = config_symbols_map.get(symbol_id)
    if not symbol_config: return 0.0

    payout_key = 'scatter_payouts' if is_scatter else 'value_multipliers'
    payout_map = symbol_config.get(payout_key, {})

    payout_map_str_keys = {str(k): v for k, v in payout_map.items()}
    multiplier = payout_map_str_keys.get(str(count), 0.0)

    try:
        if multiplier is None or str(multiplier).strip() == "": return 0.0
        return float(multiplier)
    except ValueError: # NOTE_LOG: LOG_WARNING: f"Invalid multiplier value '{multiplier}' for symbol {symbol_id}, count {count}. Defaulting to 0.0."
        return 0.0


# --- Helper Functions for calculate_win ---

def _calculate_payline_wins_for_grid(grid, config_paylines, config_symbols_map, total_bet_sats,
                                     wild_symbol_id, scatter_symbol_id, num_rows, num_cols):
    """
    Calculates wins based on configured paylines.
    (Full docstring from original file)
    """
    payline_win_sats = 0
    payline_winning_lines_data = []
    payline_winning_coords = set()

    base_bet_unit = max(1, total_bet_sats // 100) if total_bet_sats >= 100 else 1
    
    for payline_config in config_paylines:
        payline_id = payline_config.get("id", "unknown_line")
        payline_positions = payline_config.get("coords", [])
        line_symbols_on_grid = []
        actual_positions_on_line = []
        for r, c in payline_positions:
            if 0 <= r < num_rows and 0 <= c < num_cols:
                line_symbols_on_grid.append(grid[r][c])
                actual_positions_on_line.append([r,c])
            else:
                # NOTE_LOG: LOG_WARNING: f"Invalid coordinate [{r},{c}] in payline {payline_id} for grid size {num_rows}x{num_cols}."
                line_symbols_on_grid.append(None)
                actual_positions_on_line.append(None)
        
        first_symbol_on_line = line_symbols_on_grid[0]
        if first_symbol_on_line is None or first_symbol_on_line == scatter_symbol_id:
            continue

        match_symbol_id = None
        consecutive_count = 0
        winning_symbol_positions_for_line = []

        if first_symbol_on_line == wild_symbol_id:
            wilds_at_start_count = 0
            for i in range(len(line_symbols_on_grid)):
                s_id_on_line = line_symbols_on_grid[i]
                if s_id_on_line == wild_symbol_id:
                    wilds_at_start_count += 1
                    winning_symbol_positions_for_line.append(actual_positions_on_line[i])
                elif s_id_on_line != scatter_symbol_id:
                    match_symbol_id = s_id_on_line
                    consecutive_count = wilds_at_start_count + 1
                    winning_symbol_positions_for_line.append(actual_positions_on_line[i])
                    break
                else: break

            if match_symbol_id is None and wilds_at_start_count > 0:
                wild_config = config_symbols_map.get(wild_symbol_id)
                if wild_config and wild_config.get('value_multipliers'):
                    match_symbol_id = wild_symbol_id
                    consecutive_count = wilds_at_start_count
                else: continue
        else:
            match_symbol_id = first_symbol_on_line
            consecutive_count = 1
            winning_symbol_positions_for_line.append(actual_positions_on_line[0])

        if match_symbol_id:
            for i in range(consecutive_count, len(line_symbols_on_grid)):
                current_symbol_on_grid = line_symbols_on_grid[i]
                if current_symbol_on_grid == match_symbol_id or current_symbol_on_grid == wild_symbol_id:
                    consecutive_count += 1
                    winning_symbol_positions_for_line.append(actual_positions_on_line[i])
                else: break

        payout_multiplier = get_symbol_payout(match_symbol_id, consecutive_count, config_symbols_map, is_scatter=False)

        if payout_multiplier > 0:
            line_win_sats_calc = int(base_bet_unit * payout_multiplier)
            min_win_threshold = max(1, total_bet_sats // 20)
            line_win_sats_final = max(line_win_sats_calc, min_win_threshold)

            if line_win_sats_final > 0:
                payline_win_sats += line_win_sats_final
                payline_winning_lines_data.append({
                    "line_id": payline_id, "symbol_id": match_symbol_id,
                    "count": consecutive_count, "positions": winning_symbol_positions_for_line,
                    "win_amount_sats": line_win_sats_final, "type": "payline"
                })
                for pos in winning_symbol_positions_for_line:
                    payline_winning_coords.add(tuple(pos))

    return {
        "win_sats": payline_win_sats,
        "winning_lines": payline_winning_lines_data,
        "winning_coords": payline_winning_coords
    }

def _calculate_scatter_wins_for_grid(grid, scatter_symbol_id, config_symbols_map, total_bet_sats):
    """
    Calculates wins from scatter symbols anywhere on the grid.
    (Full docstring from original file)
    """
    scatter_win_sats = 0
    scatter_winning_lines_data = []
    scatter_winning_coords = set()

    if scatter_symbol_id is None: return {"win_sats": 0, "winning_lines": [], "winning_coords": set()}

    scatter_positions_on_grid = []
    scatter_count_on_grid = 0
    for r_idx, row in enumerate(grid):
        for c_idx, symbol_in_cell in enumerate(row):
            if symbol_in_cell == scatter_symbol_id:
                scatter_count_on_grid += 1
                scatter_positions_on_grid.append([r_idx, c_idx])

    if scatter_count_on_grid > 0:
        scatter_payout_multiplier = get_symbol_payout(scatter_symbol_id, scatter_count_on_grid, config_symbols_map, is_scatter=True)
        if scatter_payout_multiplier > 0:
            calculated_scatter_win = int(total_bet_sats * scatter_payout_multiplier)
            if calculated_scatter_win > 0:
                scatter_win_sats += calculated_scatter_win
                scatter_winning_lines_data.append({
                    "line_id": "scatter", "symbol_id": scatter_symbol_id,
                    "count": scatter_count_on_grid, "positions": scatter_positions_on_grid,
                    "win_amount_sats": calculated_scatter_win, "type": "scatter"
                })
                for pos in scatter_positions_on_grid:
                    scatter_winning_coords.add(tuple(pos))

    return {
        "win_sats": scatter_win_sats,
        "winning_lines": scatter_winning_lines_data,
        "winning_coords": scatter_winning_coords
    }

def _calculate_cluster_wins_for_grid(grid, config_symbols_map, total_bet_sats,
                                     wild_symbol_id, scatter_symbol_id, min_symbols_to_match):
    """
    Calculates wins based on cluster pays logic.
    (Full docstring from original file)
    """
    cluster_win_sats = 0 # Initialize accumulator for this call
    cluster_winning_lines_data = []
    cluster_winning_coords = set()

    if min_symbols_to_match is None or min_symbols_to_match <= 0:
        return {"win_sats": 0, "winning_lines": [], "winning_coords": set()}

    symbol_counts = {}
    symbol_positions_map = {}

    for r, row_data in enumerate(grid):
        for c, s_id_in_cell in enumerate(row_data):
            if s_id_in_cell is None: continue
            if s_id_in_cell != wild_symbol_id and s_id_in_cell != scatter_symbol_id:
                symbol_counts[s_id_in_cell] = symbol_counts.get(s_id_in_cell, 0) + 1
                if s_id_in_cell not in symbol_positions_map:
                    symbol_positions_map[s_id_in_cell] = []
                symbol_positions_map[s_id_in_cell].append([r, c])

    num_wilds_on_grid = 0
    wild_positions_on_grid = []
    if wild_symbol_id is not None:
        for r_idx, row_data in enumerate(grid):
            for c_idx, s_id_in_cell in enumerate(row_data):
                if s_id_in_cell == wild_symbol_id:
                    num_wilds_on_grid += 1
                    wild_positions_on_grid.append([r_idx, c_idx])

    for symbol_id, literal_symbol_count in symbol_counts.items():
        if symbol_id == wild_symbol_id or symbol_id == scatter_symbol_id:
            continue
        effective_count = literal_symbol_count + num_wilds_on_grid

        # print(f"LOG_DEBUG_CLUSTER: sym={symbol_id}, lit_count={literal_symbol_count}, wilds={num_wilds_on_grid}, eff_count={effective_count}") # Debug print removed

        if effective_count >= min_symbols_to_match:
            payout_value_for_cluster = 0
            symbol_config_data = config_symbols_map.get(symbol_id, {})
            cluster_payout_rules = symbol_config_data.get('cluster_payouts', {})
            if cluster_payout_rules:
                payout_value_for_cluster = cluster_payout_rules.get(str(effective_count), 0.0)

            # print(f"LOG_DEBUG_CLUSTER: sym={symbol_id}, eff_count={effective_count}, payout_val={payout_value_for_cluster}") # Debug print removed

            if payout_value_for_cluster > 0:
                cluster_win_sats_this_group = int(total_bet_sats * payout_value_for_cluster)
                if cluster_win_sats_this_group > 0:
                    cluster_win_sats += cluster_win_sats_this_group
                    current_symbol_positions = symbol_positions_map.get(symbol_id, [])
                    combined_positions_set = set(tuple(p) for p in current_symbol_positions)
                    for wild_pos in wild_positions_on_grid:
                        combined_positions_set.add(tuple(wild_pos))

                    winning_coords_for_this_cluster = [list(pos) for pos in combined_positions_set]
                    cluster_winning_lines_data.append({
                        "line_id": f"cluster_{symbol_id}_{effective_count}",
                        "symbol_id": symbol_id, "count": effective_count,
                        "positions": winning_coords_for_this_cluster,
                        "win_amount_sats": cluster_win_sats_this_group, "type": "cluster"
                    })
                    for pos_tuple in combined_positions_set:
                        cluster_winning_coords.add(pos_tuple)

    return {
        "win_sats": cluster_win_sats,
        "winning_lines": cluster_winning_lines_data,
        "winning_coords": cluster_winning_coords
    }


def calculate_win(grid, config_paylines, config_symbols_map, total_bet_sats, wild_symbol_id, scatter_symbol_id, min_symbols_to_match):
    """
    Calculates the total win amount and identifies winning lines/clusters from a spin grid.
    Delegates to helper functions for payline, scatter, and cluster win calculations.
    """
    total_win_sats = 0
    winning_lines_data = []
    all_winning_symbol_coords = set()
    num_rows = len(grid)
    num_cols = len(grid[0]) if num_rows > 0 else 0

    payline_results = _calculate_payline_wins_for_grid(
        grid, config_paylines, config_symbols_map, total_bet_sats,
        wild_symbol_id, scatter_symbol_id, num_rows, num_cols
    )
    total_win_sats += payline_results["win_sats"]
    winning_lines_data.extend(payline_results["winning_lines"])
    all_winning_symbol_coords.update(payline_results["winning_coords"])

    scatter_results = _calculate_scatter_wins_for_grid(
        grid, scatter_symbol_id, config_symbols_map, total_bet_sats
    )
    total_win_sats += scatter_results["win_sats"]
    winning_lines_data.extend(scatter_results["winning_lines"])
    all_winning_symbol_coords.update(scatter_results["winning_coords"])

    cluster_results = _calculate_cluster_wins_for_grid(
        grid, config_symbols_map, total_bet_sats, wild_symbol_id,
        scatter_symbol_id, min_symbols_to_match
    )
    total_win_sats += cluster_results["win_sats"]
    winning_lines_data.extend(cluster_results["winning_lines"])
    all_winning_symbol_coords.update(cluster_results["winning_coords"])

    return {
        "total_win_sats": total_win_sats,
        "winning_lines": winning_lines_data,
        "winning_symbol_coords": [list(coords) for coords in all_winning_symbol_coords]
    }

# --- Cascade Logic Helper ---
def handle_cascade_fill(current_grid, winning_coords_to_clear, cascade_type, db_symbols, config_symbols_map, wild_symbol_config_id, scatter_symbol_config_id):
    """
    Handles the filling of the grid after winning symbols are removed in a cascade.
    Uses `_generate_weighted_random_symbols` for new symbol generation.

    Args:
        current_grid (list[list[int]]): The current state of the slot grid.
        winning_coords_to_clear (list[list[int]]): List of [row, col] of symbols to remove.
        cascade_type (str): How new symbols are introduced (e.g., "fall_from_top", "replace_in_place").
        db_symbols (list): List of SlotSymbol ORM objects for the slot.
        config_symbols_map (dict): Map of symbol configurations from gameConfig.json.
        wild_symbol_config_id (int | None): ID of the wild symbol.
        scatter_symbol_config_id (int | None): ID of the scatter symbol.

    Returns:
        list[list[int]]: The new grid after clearing winning symbols and filling empty spaces.
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
    else:
        # NOTE_LOG: LOG_WARNING: f"Unknown or unimplemented cascade_type: {cascade_type}. Grid will only have symbols removed."
        pass

    return new_grid


def check_bonus_trigger(grid, scatter_symbol_id, config_bonus_features):
    """
    Checks if conditions are met to trigger a bonus feature (e.g., free spins).
    (Full docstring from original file)
    """
    free_spins_config = config_bonus_features.get('free_spins')
    if not free_spins_config:
        return {'triggered': False}

    trigger_sym_id_for_fs = free_spins_config.get('trigger_symbol_id', scatter_symbol_id)
    if trigger_sym_id_for_fs is None:
        return {'triggered': False}

    min_scatter_to_trigger = free_spins_config.get('trigger_count')
    if not isinstance(min_scatter_to_trigger, int) or min_scatter_to_trigger <= 0:
        return {'triggered': False}

    actual_trigger_symbol_count = 0
    for r_idx, row in enumerate(grid):
        for c_idx, symbol_id_in_cell in enumerate(row):
            if symbol_id_in_cell == trigger_sym_id_for_fs:
                actual_trigger_symbol_count += 1

    if actual_trigger_symbol_count >= min_scatter_to_trigger:
        return {
            'triggered': True,
            'type': 'free_spins',
            'spins_awarded': free_spins_config.get('spins_awarded', 0),
            'multiplier': free_spins_config.get('multiplier', 1.0)
        }
    return {'triggered': False}
# TODO: Add checks for other bonus types if they are introduced.


def _generate_weighted_random_symbols(count, config_symbols_map, db_symbols, secure_random_instance, wild_symbol_config_id=None, scatter_symbol_config_id=None):
    """
    Generates a list of symbols using weighted random selection.
    Filters symbols from config_symbols_map against db_symbols (actual SlotSymbol ORM objects)
    to get valid, spinable symbols. Weights are taken from symbol_config.get('weight').
    `db_symbols` should be a list of SlotSymbol ORM objects.
    `wild_symbol_config_id` and `scatter_symbol_config_id` are passed to assist with potential default weights
    if symbol configurations themselves don't specify 'is_wild' or 'is_scatter' flags and rely on these IDs.
    """
    valid_db_internal_ids = {s.symbol_internal_id for s in db_symbols}

    spinable_config_symbol_ids = [
        int(s_id_str) for s_id_str, s_config in config_symbols_map.items()
        if isinstance(s_id_str, (int, str)) and str(s_id_str).isdigit()
        and int(s_id_str) in valid_db_internal_ids
    ]
    # The following line was redundant and has been removed:
    # spinable_config_symbol_ids = [int(s_id) for s_id in spinable_config_symbol_ids]


    if not spinable_config_symbol_ids:
        # NOTE_LOG: LOG_WARNING: "No DB-validated spinable symbols during weighted generation. Attempting fallback."
        spinable_config_symbol_ids = [int(s_id_str) for s_id_str in config_symbols_map.keys() if isinstance(s_id_str, (int, str)) and str(s_id_str).isdigit()]
        if not spinable_config_symbol_ids:
            # NOTE_LOG: LOG_ERROR: "No numeric symbol IDs available in config_symbols_map for generation."
            raise ValueError("No numeric symbol IDs available in config_symbols_map for generation.")
        # NOTE_LOG: LOG_WARNING: f"Using all numeric-keyed config symbols for weighted generation. Count: {len(spinable_config_symbol_ids)}"


    weights = []
    symbols_for_choice = []
    for s_id in spinable_config_symbol_ids:
        symbol_config = config_symbols_map.get(s_id) or config_symbols_map.get(str(s_id))
        if not symbol_config:
            # NOTE_LOG: LOG_WARNING: f"Symbol ID {s_id} not found in config_symbols_map during weighted generation. Skipping."
            continue

        current_weight = 1.0
        raw_weight = symbol_config.get('weight')

        if isinstance(raw_weight, (int, float)) and raw_weight > 0:
            current_weight = float(raw_weight)
        else:
            is_wild = symbol_config.get('is_wild', False) or (wild_symbol_config_id is not None and s_id == wild_symbol_config_id)
            is_scatter = symbol_config.get('is_scatter', False) or (scatter_symbol_config_id is not None and s_id == scatter_symbol_config_id)
            if is_wild and current_weight == 1.0: current_weight = 0.5
            elif is_scatter and current_weight == 1.0: current_weight = 0.4
            # else: NOTE_LOG: LOG_DEBUG: f"Symbol ID {s_id} has invalid/missing weight '{raw_weight}'. Defaulting to 1.0 if not wild/scatter."

        weights.append(current_weight)
        symbols_for_choice.append(s_id)

    if not symbols_for_choice:
        # NOTE_LOG: LOG_ERROR: "Cannot generate symbols: No symbols available for choice after filtering/weighting."
        raise ValueError("Cannot generate symbols: No symbols available for choice after filtering and weighting.")

    total_weight = sum(weights)
    if total_weight <= 0:
        if not symbols_for_choice:
             # NOTE_LOG: LOG_ERROR: "No symbols to choose from for uniform random generation (total_weight is <= 0)."
             raise ValueError("No symbols to choose from for uniform random generation (total_weight is <= 0).")
        # NOTE_LOG: LOG_WARNING: f"Total weight is {total_weight}. Using uniform distribution for {count} symbols."
        return secure_random_instance.choices(symbols_for_choice, k=count)
    else:
        return secure_random_instance.choices(symbols_for_choice, weights=weights, k=count)
