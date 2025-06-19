import random
from datetime import datetime, timezone
from sqlalchemy.orm import joinedload

from casino_be.models import db, User, AstroMinerXExpedition, AstroMinerXAsteroid, AstroMinerXResource, Transaction
from casino_be.exceptions import InsufficientFundsException, ValidationException, NotFoundException, GameLogicException
from casino_be.error_codes import ErrorCodes

# --- Constants for Game Balance (Placeholders) ---
ASTEROID_COUNT_MIN = 10
ASTEROID_COUNT_MAX = 20
SCAN_COST_PERCENTAGE = 0.005 # 0.5% of bet amount, or could be a flat fee or free

# Asteroid type distribution (example)
# Format: (type_name, is_hazard, is_empty, min_value, max_value, probability_weight)
ASTEROID_TYPES_POOL = [
    ("iron_ore", False, False, 5, 20, 40),       # Common resource
    ("copper_vein", False, False, 10, 30, 30),    # Common resource
    ("silver_crystal", False, False, 25, 75, 15), # Uncommon resource
    ("gold_nugget", False, False, 80, 200, 7),   # Rare resource
    ("diamond_cluster", False, False, 250, 750, 3), # Very Rare resource
    ("empty_rock", False, True, 0, 0, 15),       # Empty
    ("unstable_crystal", True, False, 50, 150, 5), # Hazard with potential value if special tech used (future)
    ("gas_pocket", True, True, 0, 0, 10),         # Hazard, empty
    ("derelict_ship_small", False, False, 100, 300, 2), # Motherlode type (contains multiple resources or high value)
    ("ancient_artifact", False, False, 500, 1500, 1) # Gem type (high value single item)
]

# Mini-event probabilities (placeholder)
MINI_EVENT_CHANCE = 0.05 # 5% chance per scan to trigger an event
PIRATE_AMBUSH_CHANCE = 0.3 # If event triggers, 30% chance it's a pirate ambush

# --- Helper Functions ---

def _generate_random_asteroid_properties():
    """Selects an asteroid type and its properties based on weighted probabilities."""
    total_weight = sum(item[-1] for item in ASTEROID_TYPES_POOL)
    roll = random.uniform(0, total_weight)
    current_weight = 0
    for type_name, is_hazard, is_empty, min_val, max_val, weight in ASTEROID_TYPES_POOL:
        current_weight += weight
        if roll <= current_weight:
            value = random.uniform(min_val, max_val) if not is_empty else 0
            # Standardize type for db, actual resource name in 'value' or new field later
            # For now, type_name can be the resource name.
            return {
                "asteroid_type": type_name,
                "is_hazard": is_hazard,
                "is_empty": is_empty,
                "value": round(value, 2) if value > 0 else 0
            }
    return {"asteroid_type": "empty_rock", "is_hazard": False, "is_empty": True, "value": 0} # Fallback

def _create_initial_asteroid_field(expedition_id: int, num_asteroids: int):
    """Creates a set of asteroids for the expedition with placeholder types."""
    asteroids = []
    for _ in range(num_asteroids):
        # Initial state: type is generic, actual content revealed on scan.
        # This is a design choice: are types pre-determined or fully random on scan?
        # For this implementation, let's make the *potential* type (e.g. "standard", "dense_field")
        # somewhat visible, but true content (resource, hazard, empty) is on scan.
        # Or, we can pre-assign the types from the pool but hide values/hazard status.
        # Let's go with pre-assigning type but values/hazard revealed on scan.

        # For now, all asteroids are just 'unknown' until scanned.
        # The scan will determine all properties.
        asteroid = AstroMinerXAsteroid(
            expedition_id=expedition_id,
            asteroid_type="unknown_asteroid", # Will be updated upon scan
            value=None, # Revealed on scan
            is_empty=False, # Determined on scan
            is_hazard=False, # Determined on scan
            scan_time=None
        )
        db.session.add(asteroid)
        asteroids.append(asteroid)
    db.session.commit()
    return asteroids

# --- Service Functions ---

def launch_expedition_service(user: User, bet_amount: float):
    """
    Launches a new AstroMiner X expedition for the user.
    """
    if not isinstance(bet_amount, (int, float)) or bet_amount <= 0:
        raise ValidationException(ErrorCodes.INVALID_BET, "Bet amount must be a positive number.")

    if user.balance < bet_amount:
        raise InsufficientFundsException("Insufficient balance to start expedition.")

    # Deduct bet amount
    user.balance -= bet_amount
    bet_transaction = Transaction(
        user_id=user.id,
        amount=-bet_amount,
        transaction_type='astrominerx_bet',
        status='completed',
        details={'description': f'AstroMiner X expedition bet for {bet_amount}'}
    )
    db.session.add(bet_transaction)

    expedition = AstroMinerXExpedition(
        user_id=user.id,
        bet_amount=bet_amount,
        start_time=datetime.now(timezone.utc),
        status="active"
    )
    db.session.add(expedition)
    db.session.commit() # Commit to get expedition.id

    num_asteroids = random.randint(ASTEROID_COUNT_MIN, ASTEROID_COUNT_MAX)
    initial_asteroids = _create_initial_asteroid_field(expedition.id, num_asteroids)

    return expedition, initial_asteroids, user.balance

def scan_asteroid_service(expedition: AstroMinerXExpedition, asteroid_id: int):
    """
    Scans an asteroid, revealing its content and potentially triggering mini-events.
    """
    if expedition.status != "active":
        raise GameLogicException(ErrorCodes.EXPEDITION_NOT_ACTIVE, "Expedition is not active.")

    asteroid = AstroMinerXAsteroid.query.filter_by(id=asteroid_id, expedition_id=expedition.id).first()
    if not asteroid:
        raise NotFoundException(ErrorCodes.ASTEROID_NOT_FOUND, "Asteroid not found in this expedition.")

    if asteroid.scan_time is not None:
        raise GameLogicException(ErrorCodes.ASTEROID_ALREADY_SCANNED, "Asteroid has already been scanned.")

    # Optional: Implement scan cost
    # scan_cost = expedition.bet_amount * SCAN_COST_PERCENTAGE
    # if expedition.user.balance < scan_cost:
    #     raise InsufficientFundsException("Insufficient balance for scan cost.")
    # expedition.user.balance -= scan_cost

    # Determine asteroid content
    properties = _generate_random_asteroid_properties()
    asteroid.asteroid_type = properties["asteroid_type"]
    asteroid.is_hazard = properties["is_hazard"]
    asteroid.is_empty = properties["is_empty"]
    asteroid.value = properties["value"]
    asteroid.scan_time = datetime.now(timezone.utc)

    event_details = None # For mini-events

    # Placeholder for Mini-event logic
    if random.random() < MINI_EVENT_CHANCE:
        if random.random() < PIRATE_AMBUSH_CHANCE:
            event_details = {"type": "pirate_ambush", "message": "Pirates detected nearby! They might steal some goods if you carry too much!"}
            # Future: Could mark some already "collected" (but not banked) resources as lost,
            # or increase hazard rating of nearby unscanned asteroids.
            # For now, it's just a message.
            # Or, could end the expedition:
            # expedition.status = "aborted"
            # expedition.end_time = datetime.now(timezone.utc)
            # db.session.add(Transaction(user_id=expedition.user_id, amount=0, transaction_type='astrominerx_loss', status='completed', details={'description': f'Expedition {expedition.id} aborted due to pirate ambush.'}))
            # raise GameLogicException(ErrorCodes.GAME_LOGIC_ERROR, f"Pirate ambush! Expedition aborted. Details: {event_details['message']}")


    db.session.commit()
    return asteroid, event_details, expedition.user.balance # Include user balance if scan costs money

def collect_resources_service(expedition: AstroMinerXExpedition):
    """
    Completes the expedition, calculates total collected value, and updates user balance.
    """
    if expedition.status != "active":
        # Allow collection for "aborted" expeditions too, but they might have penalties applied earlier.
        if expedition.status == "completed":
             raise GameLogicException(ErrorCodes.GAME_LOGIC_ERROR, "Expedition already completed.")
        elif expedition.status != "aborted": # if it's some other status
             raise GameLogicException(ErrorCodes.EXPEDITION_NOT_ACTIVE, "Expedition cannot be collected at this time.")


    total_collected_value = 0
    collected_resource_objects = []

    # Query for asteroids that have been scanned, are not empty, and not hazards
    scanned_valuable_asteroids = AstroMinerXAsteroid.query.filter(
        AstroMinerXAsteroid.expedition_id == expedition.id,
        AstroMinerXAsteroid.scan_time.isnot(None),
        AstroMinerXAsteroid.is_empty == False,
        AstroMinerXAsteroid.is_hazard == False,
        AstroMinerXAsteroid.value > 0
    ).all()

    for ast in scanned_valuable_asteroids:
        resource_value = ast.value if ast.value is not None else 0
        total_collected_value += resource_value

        resource = AstroMinerXResource(
            expedition_id=expedition.id,
            resource_name=ast.asteroid_type, # e.g., "iron_ore", "diamond_cluster"
            value=resource_value,
            collected_time=datetime.now(timezone.utc)
        )
        db.session.add(resource)
        collected_resource_objects.append(resource)

    expedition.total_value_collected = round(total_collected_value, 2)

    # If expedition was aborted by an event, value might be penalized (e.g. halved)
    if expedition.status == "aborted":
        # Example penalty:
        # expedition.total_value_collected *= 0.5
        # expedition.total_value_collected = round(expedition.total_value_collected, 2)
        pass # No penalty for now for aborted status, just collect what was found.

    expedition.status = "completed"
    expedition.end_time = datetime.now(timezone.utc)

    # Add winnings to user balance
    winnings = expedition.total_value_collected
    expedition.user.balance += winnings

    win_transaction = Transaction(
        user_id=expedition.user_id,
        amount=winnings,
        transaction_type='astrominerx_win',
        status='completed',
        details={
            'description': f'AstroMiner X expedition {expedition.id} winnings.',
            'expedition_id': expedition.id,
            'bet_amount': expedition.bet_amount,
            'collected_value': winnings
        }
    )
    db.session.add(win_transaction)
    db.session.commit()

    return expedition, collected_resource_objects, expedition.user.balance

def get_expedition_state_service(expedition_id: int, user: User):
    """
    Retrieves the state of an expedition, including its asteroids and collected resources.
    """
    expedition = AstroMinerXExpedition.query.options(
        joinedload(AstroMinerXExpedition.asteroids),
        joinedload(AstroMinerXExpedition.resources_collected)
    ).filter_by(id=expedition_id, user_id=user.id).first()

    if not expedition:
        raise NotFoundException(ErrorCodes.GAME_NOT_FOUND, "Expedition not found or does not belong to user.")

    return expedition
