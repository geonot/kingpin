import hmac
import hashlib
import math
import os
from datetime import datetime, timezone
from flask import current_app # For logging
from flask_socketio import emit

from ..app import socketio # Import socketio instance
from casino_be.models import db, SpacecrashGame, SpacecrashBet, User # Assuming models are in casino_be.models
# If your app instance 'app' is needed for config, you might need to import it or pass config values.
# from casino_be.app import app # Or from casino_be.config import Config

MAX_MULTIPLIER_CAP = 9999.00  # Default cap, can be overridden by param

def get_multiplier_from_hash(game_hash_hex_string: str, house_edge: float = 0.01, max_multiplier_cap_param: float = MAX_MULTIPLIER_CAP) -> float:
    """
    Calculates a crash multiplier based on a hexadecimal game hash string,
    simulating a Bustabit-like probability distribution.
    A portion of outcomes result in an instant crash (1.00x).
    """
    if not (0 <= house_edge < 1):
        raise ValueError("House edge must be between 0 (inclusive) and 1 (exclusive).")

    game_hash_int = int(game_hash_hex_string[:13], 16)
    
    if house_edge > 0:
        divisor = int(1.0 / house_edge)
        if game_hash_int % divisor == 0:
            return 1.00

    MAX_52_BIT_HASH = 2**52 -1
    if game_hash_int == MAX_52_BIT_HASH:
        game_hash_int -=1

    r_float = game_hash_int / (2**52)

    multiplier = 1 / (1 - r_float)
    
    multiplier_scaled = math.floor(multiplier * 100) / 100
    
    return min(multiplier_scaled, max_multiplier_cap_param)


def generate_server_seed() -> str:
    return os.urandom(32).hex()

def generate_crash_point(server_seed_hex: str, client_seed_hex: str, nonce: int, house_edge: float = 0.01) -> float:
    """
    Generates a crash point using HMAC-SHA256.
    server_seed_hex: Server seed in hexadecimal.
    client_seed_hex: Client seed in hexadecimal.
    nonce: Game round number (integer).
    house_edge: The house edge for this game.
    """
    message_str = f"{client_seed_hex}:{nonce}"
    
    game_hash = hmac.new(
        bytes.fromhex(server_seed_hex),
        msg=message_str.encode('utf-8'),
        digestmod=hashlib.sha256
    )
    game_hash_hex = game_hash.hexdigest()
    
    return get_multiplier_from_hash(game_hash_hex, house_edge)

# --- Game State Management Functions ---

def create_new_game() -> SpacecrashGame:
    """Creates a new Spacecrash game instance."""
    server_seed = generate_server_seed()
    public_seed = hashlib.sha256(server_seed.encode('utf-8')).hexdigest()

    new_game = SpacecrashGame(
        server_seed=server_seed,
        public_seed=public_seed,
        nonce=0,
        status='pending',
    )
    db.session.add(new_game)
    # It's good to flush here if we need new_game.id for the broadcast helper immediately
    # db.session.flush() # Let's assume commit in route or higher level will handle flush before emit call from there for now
    # However, if helper is called from here, flush is needed for ID.
    # For now, the emit will be added *after* the commit in the calling route/admin function.
    # So, this function remains as is, emit will happen after this function returns and commit occurs.
    # Let's re-evaluate: the subtask says "After these key state transitions...emit it."
    # This implies emission should be *from these helper functions* after the state is logically changed.
    # So, a commit or at least flush + refresh is needed here if we are to get full state.
    # To keep helpers focused, they will change state. The emit will be triggered by the route after commit.
    # Let's stick to the plan: helper _get_current_game_state_for_broadcast, and emit from handler fns.
    # This means the handler function itself must ensure data is flushed/committed before calling emit with state.

    # Decision: To ensure atomicity and that helpers are testable without side-effects of emissions,
    # the emissions will be called by the *routes* after these helpers have successfully executed and data is committed.
    # This means the helper `_get_current_game_state_for_broadcast` will be used by routes.
    # Let's adjust the plan: this file will contain the game logic and the state fetching helper.
    # The routes file will import the state fetching helper and do the emits.
    # This makes more sense than helpers emitting directly before commit.

    # THEREFORE, this file (handler) will NOT have emit calls directly in create_new_game, start_betting_phase etc.
    # It WILL have the _get_current_game_state_for_broadcast helper.
    return new_game

def start_betting_phase(game: SpacecrashGame) -> bool:
    """Transitions the game to the 'betting' phase."""
    if game.status == 'pending':
        game.status = 'betting'
        game.betting_start_time = datetime.now(timezone.utc) # Explicitly set betting start time
        game.game_start_time = None # Ensure game_start_time (for multiplier) is reset
        game.game_end_time = None
        # db.session.add(game) # Caller should add and commit
        return True
    return False

def start_game_round(game: SpacecrashGame, client_seed_param: str, nonce_param: int) -> bool:
    """
    Starts a new game round: sets client_seed, nonce, calculates crash_point,
    sets game_start_time, and updates status to 'in_progress'.
    """
    if game.status == 'betting':
        game.client_seed = client_seed_param
        game.nonce = nonce_param
        
        house_edge_config = 0.01
        game.crash_point = generate_crash_point(game.server_seed, game.client_seed, game.nonce, house_edge_config)
        
        game.status = 'in_progress'
        game.game_start_time = datetime.now(timezone.utc)
        game.game_end_time = None
        # db.session.add(game) # Caller should add and commit
        return True
    return False

def end_game_round(game: SpacecrashGame) -> bool:
    """Ends the current game round, sets status to 'completed' and records end time."""
    if game.status == 'in_progress':
        game.status = 'completed'
        game.game_end_time = datetime.now(timezone.utc)
        
        bets_to_process = SpacecrashBet.query.filter_by(game_id=game.id, status='placed').all()
        for bet in bets_to_process:
            user = User.query.get(bet.user_id)
            if not user:
                continue

            if bet.auto_eject_at and bet.auto_eject_at <= game.crash_point:
                bet.ejected_at = bet.auto_eject_at
                bet.win_amount = int(bet.bet_amount * bet.ejected_at)
                user.balance += bet.win_amount
                bet.status = 'ejected'
            else:
                bet.status = 'busted'
                bet.ejected_at = game.crash_point
                bet.win_amount = 0
            # db.session.add(bet) # Caller should add and commit
        
        # db.session.add(game) # Caller should add and commit
        return True
    return False

def get_current_multiplier(game: SpacecrashGame, default_if_not_started: float = 1.0) -> float:
    """
    Calculates the current multiplier for an 'in_progress' game.
    Returns default_if_not_started if game hasn't started or not in progress.
    """
    if game and game.status == 'in_progress' and game.game_start_time:
        elapsed_seconds = (datetime.now(timezone.utc) - game.game_start_time).total_seconds()
        if elapsed_seconds < 0: elapsed_seconds = 0
        # Growth formula: e.g., 1.00 * (1.07^elapsed_seconds)
        # Adjust base and exponent factor for desired curve
        # For example, a common curve: multiplier = 1.00 * math.pow(1.07, elapsed_seconds)
        # Or using `e`: multiplier = math.exp(elapsed_seconds * k) where k controls speed
        # Using a simple exponential growth for now:
        multiplier = 1.00 * math.pow(1.015, elapsed_seconds * 5) # Example: faster growth
        multiplier = math.floor(multiplier * 100) / 100
        # Ensure multiplier doesn't exceed crash_point if game is still "in_progress" but calculation goes beyond
        # This can happen due to calculation timing vs actual crash event processing
        return min(multiplier, game.crash_point) if game.crash_point else multiplier

    if game and game.status == 'completed' and game.crash_point:
        return game.crash_point # If completed, always show the crash point

    return default_if_not_started


# --- Helper to get game state for broadcasting ---
def get_current_game_state_for_broadcast(game_id: int = None):
    """
    Fetches the comprehensive current game state, suitable for broadcasting.
    If game_id is None, fetches the latest game.
    """
    if game_id:
        game = SpacecrashGame.query.get(game_id)
    else:
        # Ensure we order by ID descending to get the most recent game.
        game = SpacecrashGame.query.order_by(SpacecrashGame.id.desc()).first()

    if not game:
        # current_app.logger.warning("get_current_game_state_for_broadcast: No game found.")
        return {"error": "No game found"} # Or return a default "no active game" state

    current_multiplier_val = 1.00
    if game.status == 'in_progress':
        current_multiplier_val = get_current_multiplier(game)
    elif game.status == 'completed':
        current_multiplier_val = game.crash_point if game.crash_point else 1.00
    elif game.status == 'betting' or game.status == 'pending':
        current_multiplier_val = 1.00

    player_bets_data = []
    # Ensure bets are loaded for the specific game_id
    bets_query = db.session.query(SpacecrashBet, User.username).join(User, User.id == SpacecrashBet.user_id).filter(SpacecrashBet.game_id == game.id).all()

    for bet, username in bets_query:
        player_bets_data.append({
            "user_id": bet.user_id,
            "username": username,
            "bet_amount": bet.bet_amount,
            "status": bet.status, # 'placed', 'ejected', 'busted'
            "ejected_at_multiplier": bet.ejected_at, # Null if not ejected or busted
            "win_amount": bet.win_amount, # Null or 0 if not won
            "auto_eject_at": bet.auto_eject_at # For UI to show if auto-eject is set
        })

    # Calculate betting_ends_at if game is in 'betting' state
    betting_ends_at_iso = None
    if game.status == 'betting' and game.betting_start_time:
        # Assuming a fixed betting duration, e.g., 10 seconds
        # This duration should ideally be a configuration value
        betting_duration_seconds = 10 # Example
        betting_ends_at_dt = game.betting_start_time + timezone.timedelta(seconds=betting_duration_seconds)
        betting_ends_at_iso = betting_ends_at_dt.isoformat()


    return {
        "id": game.id,
        "status": game.status, # 'pending', 'betting', 'in_progress', 'completed'
        "current_multiplier": float(current_multiplier_val) if current_multiplier_val else 1.00,
        "player_bets": player_bets_data,
        "game_start_time": game.game_start_time.isoformat() if game.game_start_time else None, # When multiplier starts rising
        "betting_start_time": game.betting_start_time.isoformat() if game.betting_start_time else None, # When betting phase began
        "betting_ends_at": betting_ends_at_iso, # Calculated: when betting phase will end
        "crash_point": float(game.crash_point) if game.crash_point else None,
        "public_seed": game.public_seed,
        # For security, client_seed and nonce are usually not broadcasted while game is bettable or in progress.
        # Only reveal them if game is completed or for specific user context.
        # "client_seed": game.client_seed if game.status == 'completed' else None,
        # "nonce": game.nonce if game.status == 'completed' else None,
        "created_at": game.created_at.isoformat() if game.created_at else None,
        "game_end_time": game.game_end_time.isoformat() if game.game_end_time else None,
        # Server seed hash is the public seed. If server_seed itself is needed, only after game completion.
        # "server_seed": game.server_seed if game.status == 'completed' else None,
    }
