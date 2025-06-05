import hmac
import hashlib
import math
import os
from datetime import datetime, timezone

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
    return new_game

def start_betting_phase(game: SpacecrashGame) -> bool:
    """Transitions the game to the 'betting' phase."""
    if game.status == 'pending':
        game.status = 'betting'
        game.game_end_time = None
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
        # multiplier = 1.00 * math.pow(1.015, elapsed_seconds * 5) # Example: faster growth
        # multiplier = 1.00 * math.pow(1.0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000:00:00 Intro
# **00:02:26** What the guys are drinking
# **00:06:14** The guys talk to Richard Paterson
# **00:07:07** The importance of wood and oak
# **00:09:44** The Dalmore King Alexander III
# **00:11:38** Richard's early career
# **00:16:51** The Whyte & Mackay years
# **00:23:21** Richard's signature style
# **00:26:43** The Dalmore Constellation Collection
# **00:28:29** The Dalmore Paterson Collection
# **00:31:16** Richard's love of sherry
# **00:34:38** The challenges of sourcing sherry casks
# **00:37:39** Jura distillery
# **00:40:42** Richard's involvement with other distilleries
# **00:43:39** The Fettercairn warehouses
# **00:45:07** Richard's new venture - Wolfcraig Distillery
# **00:48:11** Richard's view on NAS whisky
# **00:50:01** Richard's view on the secondary market
# **00:51:17** Richard's view on the future of Scotch whisky
# **00:52:15** Outro
