from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload
from datetime import datetime, timezone
import random
import json # Though direct dict access for JSON field is usually fine with SQLAlchemy
import logging

from casino_be.models import db, User, CrystalSeed, CrystalFlower, PlayerGarden, CrystalCodexEntry

logger = logging.getLogger(__name__)

# --- Custom Exceptions ---
class ServiceError(Exception):
    """Base class for service layer errors."""
    def __init__(self, message, status_code=400, error_code=None):
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code # For more specific client-side handling if needed

class InsufficientFundsError(ServiceError):
    def __init__(self, message="Insufficient funds."):
        super().__init__(message, 402, "INSUFFICIENT_FUNDS")

class PlotOccupiedError(ServiceError):
    def __init__(self, message="Plot is already occupied."):
        super().__init__(message, 409, "PLOT_OCCUPIED")

class InvalidPlotError(ServiceError): # General invalid plot issue
    def __init__(self, message="Plot is invalid."):
        super().__init__(message, 422, "INVALID_PLOT")

class GardenPlotOutOfBoundsError(InvalidPlotError): # Specific subclass for bounds
    def __init__(self, message="Plot is outside garden boundaries."):
        super().__init__(message, 422, "PLOT_OUT_OF_BOUNDS")

class ItemNotFoundError(ServiceError):
    def __init__(self, message="Item not found.", error_code="ITEM_NOT_FOUND"):
        super().__init__(message, 404, error_code)

class UserNotFoundError(ItemNotFoundError):
    def __init__(self, user_id):
        super().__init__(f"User with ID {user_id} not found.", "USER_NOT_FOUND")

class SeedNotFoundError(ItemNotFoundError):
    def __init__(self, seed_id):
        super().__init__(f"CrystalSeed with ID {seed_id} not found.", "SEED_NOT_FOUND")

class FlowerNotFoundError(ItemNotFoundError):
    def __init__(self, flower_id, user_id=None):
        msg = f"CrystalFlower with ID {flower_id} not found"
        if user_id:
            msg += f" for user {user_id}"
        super().__init__(msg, "FLOWER_NOT_FOUND")

class GardenNotFoundError(ItemNotFoundError):
    def __init__(self, garden_id=None, user_id=None):
        msg = "PlayerGarden not found"
        if garden_id:
            msg = f"PlayerGarden with ID {garden_id} not found"
        elif user_id:
            msg = f"PlayerGarden for user ID {user_id} not found"
        super().__init__(msg, "GARDEN_NOT_FOUND")

class InvalidActionError(ServiceError): # General invalid action
    def __init__(self, message="Invalid action or state for this operation.", error_code="INVALID_ACTION", status_code=422):
        super().__init__(message, status_code, error_code)

class PowerUpNotFoundError(InvalidActionError):
    def __init__(self, power_up_type: str):
        super().__init__(f"Unknown power-up type: {power_up_type}", "POWER_UP_NOT_FOUND")

class FlowerNotBloomingError(InvalidActionError):
    def __init__(self, message="Action requires a blooming flower."):
        super().__init__(message, "FLOWER_NOT_BLOOMING")

class FlowerAlreadyAppraisedError(InvalidActionError):
    def __init__(self, message="Flower has already been appraised."):
        super().__init__(message, "FLOWER_ALREADY_APPRAISED", status_code=409) # 409 Conflict

class FlowerNotAppraisedError(InvalidActionError):
    def __init__(self, message="Flower must be appraised before this action."):
        super().__init__(message, "FLOWER_NOT_APPRAISED")

class DatabaseError(ServiceError):
    def __init__(self, message="A database error occurred.", original_exception=None):
        self.original_exception = original_exception
        super().__init__(message, 500, "DATABASE_ERROR")


# --- Constants ---
POWER_UP_COSTS = {
    def __init__(self, message, status_code=400):
        super().__init__(message)
        self.status_code = status_code

class InsufficientFundsError(ServiceError):
    def __init__(self, message="Insufficient funds."):
        super().__init__(message, 402) # HTTP 402 Payment Required

class PlotOccupiedError(ServiceError):
    def __init__(self, message="Plot is already occupied."):
        super().__init__(message, 409) # HTTP 409 Conflict

class InvalidPlotError(ServiceError):
    def __init__(self, message="Plot is invalid or outside garden boundaries."):
        super().__init__(message, 422) # HTTP 422 Unprocessable Entity

class ItemNotFoundError(ServiceError):
    def __init__(self, message="Item not found."):
        super().__init__(message, 404) # HTTP 404 Not Found

class InvalidActionError(ServiceError):
    def __init__(self, message="Invalid action or state for this operation."):
        super().__init__(message, 403) # HTTP 403 Forbidden or 422

# --- Constants ---
POWER_UP_COSTS = {
    'fertilizer': 10,           # Speeds growth / size boost
    'moon_glow': 15,            # Enhances clarity and special type chance
    'azure_dye': 25,            # Guarantees blue color
    'clarity_elixir': 30,       # Ensures minimum clarity of 0.6
    'sparkle_infusion': 40,     # Greatly boosts rare special type chance
}
APPRAISAL_COST = 5

COLOR_VALUE_MAP = { # Example values
    'blue': 10, 'red': 15, 'green': 12, 'yellow': 8, 'purple': 20, 'clear': 5,
    'common_glow': 5, 'rare_sparkle': 25 # Example for special types if they have a base color value
}
SPECIAL_TYPE_BONUS_MAP = { # Example bonuses
    'rare_sparkle': 50,
    'common_glow': 20,
    'none': 0,
}


class CrystalGardenService:

    def get_or_create_player_garden(self, user_id: int) -> PlayerGarden:
        """
        Retrieves an existing PlayerGarden for the user or creates a new one.
        Raises UserNotFoundError if user does not exist, DatabaseError on commit issues.
        """
        if not isinstance(user_id, int):
            logger.warning(f"get_or_create_player_garden: Invalid user_id type: {user_id}")
            raise ServiceError("Invalid user ID type.", status_code=400, error_code="INVALID_INPUT_TYPE")

        garden = PlayerGarden.query.filter_by(user_id=user_id).first()
        if not garden:
            user = User.query.get(user_id)
            if not user:
                logger.warning(f"User not found for garden creation: user_id={user_id}")
                raise UserNotFoundError(user_id)
            try:
                logger.info(f"Creating new garden for user_id: {user_id}")
                garden = PlayerGarden(user_id=user_id)
                db.session.add(garden)
                db.session.commit()
            except IntegrityError as e:
                db.session.rollback()
                logger.error(f"IntegrityError creating garden for user_id {user_id}: {e}", exc_info=True)
                # Attempt to refetch in case of a race condition
                garden = PlayerGarden.query.filter_by(user_id=user_id).first()
                if not garden:
                     raise DatabaseError(f"Failed to create or retrieve garden after integrity error for user {user_id}.", original_exception=e)
            except Exception as e:
                db.session.rollback()
                logger.error(f"Exception creating garden for user_id {user_id}: {e}", exc_info=True)
                raise DatabaseError(f"Error creating garden for user {user_id}.", original_exception=e)
        return garden

    def buy_seed(self, user_id: int, seed_id: int) -> CrystalSeed:
        """
        Allows a user to buy a crystal seed.
        Raises UserNotFoundError, SeedNotFoundError, InsufficientFundsError, DatabaseError.
        """
        if not all(isinstance(arg, int) for arg in [user_id, seed_id]):
            logger.warning(f"buy_seed: Invalid input types: user_id={user_id}, seed_id={seed_id}")
            raise ServiceError("Invalid input type for user_id or seed_id.", status_code=400, error_code="INVALID_INPUT_TYPE")

        user = User.query.get(user_id)
        if not user:
            raise UserNotFoundError(user_id)

        seed = CrystalSeed.query.get(seed_id)
        if not seed:
            raise SeedNotFoundError(seed_id)

        if user.balance < seed.cost:
            logger.info(f"User {user_id} insufficient funds for seed {seed_id} (cost {seed.cost}, balance {user.balance})")
            raise InsufficientFundsError(f"User {user_id} has insufficient funds ({user.balance}) for seed {seed_id} (cost {seed.cost}).")

        try:
            user.balance -= seed.cost
            db.session.commit()
            logger.info(f"User {user_id} purchased seed {seed_id} for {seed.cost}. New balance: {user.balance}")
        except Exception as e:
            db.session.rollback()
            logger.error(f"Database error during seed purchase for user {user_id}, seed {seed_id}: {e}", exc_info=True)
            raise DatabaseError("Error processing seed purchase.", original_exception=e)

        return seed

    def plant_seed(self, user_id: int, seed_id: int, garden_plot_x: int, garden_plot_y: int) -> CrystalFlower:
        """
        Plants a seed in the player's garden.
        Raises UserNotFoundError, SeedNotFoundError, GardenPlotOutOfBoundsError, PlotOccupiedError, DatabaseError.
        """
        if not all(isinstance(arg, int) for arg in [user_id, seed_id, garden_plot_x, garden_plot_y]):
            logger.warning(f"plant_seed: Invalid input types: user_id={user_id}, seed_id={seed_id}, x={garden_plot_x}, y={garden_plot_y}")
            raise ServiceError("Invalid input type for user_id, seed_id, or plot coordinates.", status_code=400, error_code="INVALID_INPUT_TYPE")

        # get_or_create_player_garden handles UserNotFoundError
        garden = self.get_or_create_player_garden(user_id)

        seed = CrystalSeed.query.get(seed_id)
        if not seed:
            raise SeedNotFoundError(seed_id)

        if not (0 <= garden_plot_x < garden.grid_size_x and 0 <= garden_plot_y < garden.grid_size_y):
            logger.warning(f"Plot ({garden_plot_x}, {garden_plot_y}) for user {user_id} is outside garden boundaries ({garden.grid_size_x}x{garden.grid_size_y}).")
            raise GardenPlotOutOfBoundsError(f"Plot ({garden_plot_x}, {garden_plot_y}) is outside garden boundaries.")

        existing_flower = CrystalFlower.query.filter_by(
            player_garden_id=garden.id,
            position_x=garden_plot_x,
            position_y=garden_plot_y
        ).first()
        if existing_flower:
            logger.info(f"Plot ({garden_plot_x}, {garden_plot_y}) in garden {garden.id} for user {user_id} is already occupied by flower {existing_flower.id}.")
            raise PlotOccupiedError(f"Plot ({garden_plot_x}, {garden_plot_y}) is already occupied.")

        try:
            new_flower = CrystalFlower(
                user_id=user_id,
                crystal_seed_id=seed_id,
                player_garden_id=garden.id,
                position_x=garden_plot_x,
                position_y=garden_plot_y,
                growth_stage='seeded',
                planted_at=datetime.now(timezone.utc),
                active_power_ups=[]
            )
            db.session.add(new_flower)
            db.session.commit()
            logger.info(f"Seed {seed_id} planted for user {user_id} at ({garden_plot_x}, {garden_plot_y}), new flower ID: {new_flower.id}")
        except Exception as e:
            db.session.rollback()
            logger.error(f"Database error planting seed {seed_id} for user {user_id}: {e}", exc_info=True)
            raise DatabaseError(f"Error planting seed.", original_exception=e)
        return new_flower

    def get_garden_state(self, user_id: int) -> dict:
        """
        Retrieves the state of the player's garden.
        Raises UserNotFoundError.
        """
        if not isinstance(user_id, int):
            logger.warning(f"get_garden_state: Invalid user_id type: {user_id}")
            raise ServiceError("Invalid user ID type.", status_code=400, error_code="INVALID_INPUT_TYPE")

        # get_or_create_player_garden handles UserNotFoundError if user doesn't exist
        # and garden needs to be created. If it only gets, it implies user exists.
        garden = self.get_or_create_player_garden(user_id)
        # At this point, garden is guaranteed to exist or an error would have been raised.

        # Eager load seed information as it might be useful for display in the garden state eventually.
        flowers = CrystalFlower.query.filter_by(player_garden_id=garden.id)\
            .options(joinedload(CrystalFlower.seed)).all()

        flower_list = []
        for flower in flowers:
            flower_list.append({
                "id": flower.id, "crystal_seed_id": flower.crystal_seed_id,
                "planted_at": flower.planted_at.isoformat(), "growth_stage": flower.growth_stage,
                "color": flower.color, "size": flower.size, "clarity": flower.clarity,
                "special_type": flower.special_type, "appraised_value": flower.appraised_value,
                "position_x": flower.position_x, "position_y": flower.position_y,
                "active_power_ups": flower.active_power_ups if flower.active_power_ups else []
            })

        return {
            "garden_id": garden.id, "user_id": garden.user_id,
            "grid_size_x": garden.grid_size_x, "grid_size_y": garden.grid_size_y,
            "last_cycle_time": garden.last_cycle_time.isoformat() if garden.last_cycle_time else None,
            "flowers": flower_list
        }

    def get_player_codex(self, user_id: int) -> list[CrystalCodexEntry]:
        """
        Retrieves all CrystalCodexEntry items for a user.
        Raises UserNotFoundError.
        """
        if not isinstance(user_id, int):
            logger.warning(f"get_player_codex: Invalid user_id type: {user_id}")
            raise ServiceError("Invalid user ID type.", status_code=400, error_code="INVALID_INPUT_TYPE")

        user = User.query.get(user_id)
        if not user:
            # This check might be redundant if user_id comes from authenticated session,
            # but good for service layer integrity.
            raise UserNotFoundError(user_id)
        return CrystalCodexEntry.query.filter_by(user_id=user_id).all()

    def apply_power_up(self, user_id: int, flower_id: int, power_up_type: str) -> CrystalFlower:
        """
        Applies a power-up to a crystal flower.
        Raises UserNotFoundError, FlowerNotFoundError, PowerUpNotFoundError, InsufficientFundsError, DatabaseError.
        """
        if not all(isinstance(arg, int) for arg in [user_id, flower_id]):
            logger.warning(f"apply_power_up: Invalid input type for user_id or flower_id: user_id={user_id}, flower_id={flower_id}")
            raise ServiceError("Invalid input type for user_id or flower_id.", status_code=400, error_code="INVALID_INPUT_TYPE")
        if not isinstance(power_up_type, str):
            logger.warning(f"apply_power_up: Invalid power_up_type: {power_up_type}")
            raise ServiceError("Invalid power_up_type.", status_code=400, error_code="INVALID_INPUT_TYPE")


        user = User.query.get(user_id)
        if not user:
            raise UserNotFoundError(user_id)

        flower = CrystalFlower.query.filter_by(id=flower_id, user_id=user_id).first()
        if not flower:
            raise FlowerNotFoundError(flower_id, user_id)

        cost = POWER_UP_COSTS.get(power_up_type)
        if cost is None:
            raise PowerUpNotFoundError(power_up_type)

        if user.balance < cost:
            logger.info(f"User {user_id} insufficient funds for power-up '{power_up_type}' (cost {cost}, balance {user.balance}) on flower {flower_id}.")
            raise InsufficientFundsError(f"Insufficient funds for power-up '{power_up_type}'.")

        try:
            user.balance -= cost
            if flower.active_power_ups is None: # Ensure list initialization
                flower.active_power_ups = []

            current_power_ups = list(flower.active_power_ups) # Create a mutable copy
            current_power_ups.append(power_up_type)
            flower.active_power_ups = current_power_ups # Assign back to trigger SQLAlchemy change detection

            db.session.commit()
            logger.info(f"Power-up '{power_up_type}' applied to flower {flower_id} for user {user_id}. Cost: {cost}. New balance: {user.balance}")
        except Exception as e:
            db.session.rollback()
            logger.error(f"Database error applying power-up '{power_up_type}' to flower {flower_id} for user {user_id}: {e}", exc_info=True)
            raise DatabaseError(f"Error applying power-up.", original_exception=e)
        return flower

    def _randomize_attribute(self, outcomes, key, power_ups_active=None):
        """Helper to randomize a single attribute based on potential_outcomes."""
        config = outcomes.get(key, {})
        if not config: return None

        power_ups_active = power_ups_active if power_ups_active else []
        distribution_type = config.get("distribution")

        # Handle Azure Dye for colors
        if key == "colors" and 'azure_dye' in power_ups_active:
            return 'blue'

        if distribution_type == "uniform":
            min_val, max_val = config.get("min", 0), config.get("max", 1)
            return random.uniform(min_val, max_val)
        elif distribution_type == "normal":
            mean = config.get("mean", 0.5)
            stddev = config.get("stddev", 0.1)
            min_clip = config.get("min_clip", 0.0)
            max_clip = config.get("max_clip", 1.0)
            value = random.normalvariate(mean, stddev)
            return max(min_clip, min(value, max_clip))
        elif distribution_type == "weighted_ranges":
            ranges_config = config.get("ranges", {})
            if not ranges_config: return None
            range_names = list(ranges_config.keys())
            range_weights = [float(rc.get("weight", 0)) for rc in ranges_config.values()]
            if not range_names or sum(range_weights) == 0: return None
            chosen_range_name = random.choices(range_names, weights=range_weights, k=1)[0]
            chosen_range = ranges_config[chosen_range_name]
            min_val = chosen_range.get("min", 0)
            max_val = chosen_range.get("max", 1)
            return random.uniform(min_val, max_val)

        elif isinstance(config, dict) and not distribution_type: # Weighted choices (color, special_type)
            choices = list(config.keys())
            original_weights = [float(w) for w in config.values()]
            if not choices or sum(original_weights) == 0: return None

            weights = list(original_weights) # Work with a copy

            # Apply Sparkle Infusion or Moon Glow for special_types
            if key == "special_types":
                if 'sparkle_infusion' in power_ups_active: # Dominant effect
                    new_weights = []
                    for i, choice_val in enumerate(choices):
                        current_weight = weights[i]
                        if choice_val == 'none':
                            new_weights.append(max(0.05, current_weight * 0.1)) # Drastically reduce 'none'
                        elif choice_val in ['rare_sparkle', 'celestial_radiance', 'umbral_echo', 'solar_flare', 'ancient_resin', 'water_ripple']: # Example rare/custom types
                            new_weights.append(current_weight * 3.0) # Significantly boost rare
                        elif choice_val == 'common_glow':
                            new_weights.append(current_weight * 1.2) # Slightly boost common
                        else: # Other custom non-rare types
                            new_weights.append(current_weight * 0.5)
                    if sum(new_weights) > 0: weights = new_weights

                elif 'moon_glow' in power_ups_active: # Less dominant, applies if sparkle_infusion is not active
                    new_weights = []
                    for i, choice_val in enumerate(choices):
                        current_weight = weights[i]
                        if choice_val == 'none':
                            new_weights.append(max(0.1, current_weight * 0.5))
                        elif choice_val in ['rare_sparkle', 'common_glow']: # Original moon_glow targets
                            new_weights.append(current_weight * 1.5)
                        else:
                            new_weights.append(current_weight)
                    if sum(new_weights) > 0: weights = new_weights

            if not choices or sum(weights) == 0: return None
            return random.choices(choices, weights=weights, k=1)[0]
        return None

    def process_growth_cycle(self, garden_id: int) -> dict:
        """
        Processes one growth cycle for all flowers in a garden.
        Raises GardenNotFoundError, DatabaseError.
        """
        if not isinstance(garden_id, int):
            logger.warning(f"process_growth_cycle: Invalid garden_id type: {garden_id}")
            raise ServiceError("Invalid garden ID type.", status_code=400, error_code="INVALID_INPUT_TYPE")

        garden = PlayerGarden.query.get(garden_id)
        if not garden:
            raise GardenNotFoundError(garden_id=garden_id)

        # Eager load seeds to prevent N+1 queries inside the loop
        flowers = CrystalFlower.query.filter_by(player_garden_id=garden.id)\
            .options(joinedload(CrystalFlower.seed)).all()

        logger.info(f"Processing growth cycle for garden {garden_id} with {len(flowers)} flowers.")
        summary = {"updated_flowers": 0, "newly_bloomed": 0, "garden_id": garden_id}
        # No longer need power_ups_consumed_this_cycle here, it's managed per flower

        # Pre-fetch all unique seeds needed for these flowers
        # This was the N+1 issue: seed = CrystalSeed.query.get(flower.crystal_seed_id)
        # Now, flower.seed is already loaded due to joinedload.

        for flower in flowers:
            updated = False # Default to false, only set true if a change occurs
            consumed_for_this_flower = []

            # Apply power-up effects
            active_power_ups = list(flower.active_power_ups) if flower.active_power_ups else [] # Work with a copy

            current_stage = flower.growth_stage
            next_stage = current_stage
            size_bonus = 0.0
            clarity_bonus = 0.0

            if 'fertilizer' in active_power_ups:
                if current_stage == 'seeded':
                    next_stage = 'sprouting'
                    consumed_for_this_flower.append('fertilizer')
                    updated = True
                elif current_stage == 'sprouting':
                    next_stage = 'blooming'
                    size_bonus = 0.5 # Fertilizer bonus when blooming this cycle
                    consumed_for_this_flower.append('fertilizer')
                    updated = True

            if 'moon_glow' in active_power_ups and next_stage == 'blooming': # Apply if it will bloom this cycle
                # Clarity bonus will be applied when attributes are set
                # Special type probability will be handled in _randomize_attribute or here
                pass # Mark for consumption later if it blooms


            # Standard growth progression if not overridden by power-up
            if not updated: # if fertilizer didn't cause a change already
                if current_stage == 'seeded':
                    next_stage = 'sprouting'
                    updated = True
                elif current_stage == 'sprouting':
                    next_stage = 'blooming'
                    updated = True

            flower.growth_stage = next_stage

            if flower.growth_stage == 'blooming' and current_stage != 'blooming': # Just bloomed
                summary["newly_bloomed"] += 1
                updated = True # Ensure it's marked as updated

                # seed is now directly accessible via flower.seed due to joinedload
                seed_obj = flower.seed
                outcomes = {}
                if seed_obj and seed_obj.potential_outcomes:
                    outcomes = seed_obj.potential_outcomes if isinstance(seed_obj.potential_outcomes, dict) else {}
                elif not seed_obj:
                    logger.error(f"Flower {flower.id} has missing seed object (seed_id: {flower.crystal_seed_id}) during growth cycle. Skipping attribute randomization for it.")
                    # Decide how to handle this - skip this flower's attribute setting or set defaults
                    # For now, it will fall through to the `if not outcomes:` block and get random defaults.

                # Determine attributes
                flower.color = self._randomize_attribute(outcomes, "colors", active_power_ups) # Azure Dye handled inside
                if 'azure_dye' in active_power_ups and 'azure_dye' not in consumed_for_this_flower:
                    consumed_for_this_flower.append('azure_dye')

                base_size = self._randomize_attribute(outcomes, "sizes", active_power_ups) or 1.0
                flower.size = round(base_size + size_bonus, 2) # Fertilizer size bonus applied here

                # Clarity calculation with power-ups
                current_clarity = self._randomize_attribute(outcomes, "clarities", active_power_ups) or 0.1

                if 'clarity_elixir' in active_power_ups:
                    current_clarity = max(current_clarity, 0.6) # Elixir base effect
                    if 'clarity_elixir' not in consumed_for_this_flower:
                        consumed_for_this_flower.append('clarity_elixir')

                if 'moon_glow' in active_power_ups: # Moon glow adds bonus on top
                    current_clarity += 0.2
                    if 'moon_glow' not in consumed_for_this_flower:
                         consumed_for_this_flower.append('moon_glow')

                flower.clarity = round(min(current_clarity, 1.0), 2) # Cap at 1.0

                # Special type randomization (Sparkle Infusion, Moon Glow handled inside)
                flower.special_type = self._randomize_attribute(outcomes, "special_types", active_power_ups)
                if 'sparkle_infusion' in active_power_ups and 'sparkle_infusion' not in consumed_for_this_flower:
                    consumed_for_this_flower.append('sparkle_infusion')
                # Moon Glow consumption for special_types (if not already consumed for clarity and sparkle_infusion not active)
                if 'moon_glow' in active_power_ups and \
                   'moon_glow' not in consumed_for_this_flower and \
                   'sparkle_infusion' not in active_power_ups: # Sparkle infusion is dominant
                    consumed_for_this_flower.append('moon_glow')


                if not outcomes: # Fallback if no outcomes defined (and no overriding power-ups like Azure Dye)
                    if flower.color is None: flower.color = random.choice(['blue', 'red', 'green'])
                    if flower.size == 0.0 + size_bonus : flower.size = round(random.uniform(1.0, 5.0) + size_bonus, 2) # if not set by outcomes
                    if flower.clarity == 0.0 + clarity_bonus: flower.clarity = round(min(random.uniform(0.1, 1.0) + clarity_bonus, 1.0), 2) # if not set
                    flower.special_type = flower.special_type or 'none'


            #elif flower.growth_stage == 'blooming': # Already blooming, no change unless other logic
                # pass
            #else: # 'withered', or other
                # pass # No change

            if updated:
                summary["updated_flowers"] += 1

            if consumed_for_this_flower:
                new_active_power_ups = [p for p in flower.active_power_ups if p not in consumed_for_this_flower]
                flower.active_power_ups = new_active_power_ups
                # Ensure SQLAlchemy detects the change if active_power_ups was already a list
                if flower.active_power_ups is not None:
                     flower.active_power_ups = list(flower.active_power_ups)


        try:
            garden.last_cycle_time = datetime.now(timezone.utc)
            db.session.commit()
            logger.info(f"Growth cycle for garden {garden_id} completed. Updated: {summary['updated_flowers']}, Bloomed: {summary['newly_bloomed']}.")
        except Exception as e:
            db.session.rollback()
            logger.error(f"Database error finalizing growth cycle for garden {garden_id}: {e}", exc_info=True)
            raise DatabaseError("Error finalizing growth cycle.", original_exception=e)

        summary["last_cycle_time"] = garden.last_cycle_time.isoformat()
        return summary

    def appraise_crystal(self, user_id: int, flower_id: int) -> CrystalFlower:
        """
        Appraises a crystal flower and sets its value.
        Raises UserNotFoundError, FlowerNotFoundError, FlowerNotBloomingError,
               FlowerAlreadyAppraisedError, InsufficientFundsError, DatabaseError.
        """
        if not all(isinstance(arg, int) for arg in [user_id, flower_id]):
            logger.warning(f"appraise_crystal: Invalid input type: user_id={user_id}, flower_id={flower_id}")
            raise ServiceError("Invalid input type for user_id or flower_id.", status_code=400, error_code="INVALID_INPUT_TYPE")

        user = User.query.get(user_id)
        if not user:
            raise UserNotFoundError(user_id)

        flower = CrystalFlower.query.filter_by(id=flower_id, user_id=user_id).first()
        if not flower:
            raise FlowerNotFoundError(flower_id, user_id)

        if flower.growth_stage != 'blooming':
            logger.info(f"Attempt to appraise non-blooming flower {flower_id} (stage: {flower.growth_stage}) for user {user_id}.")
            raise FlowerNotBloomingError("Only blooming flowers can be appraised.")

        if flower.appraised_value is not None:
            logger.info(f"Attempt to re-appraise flower {flower_id} for user {user_id}.")
            raise FlowerAlreadyAppraisedError("Flower has already been appraised.")

        if user.balance < APPRAISAL_COST:
            logger.info(f"User {user_id} insufficient funds for appraisal (cost {APPRAISAL_COST}, balance {user.balance}) of flower {flower_id}.")
            raise InsufficientFundsError("Insufficient funds for appraisal.")

        try:
            user.balance -= APPRAISAL_COST

            value = (flower.size or 0) * 10 # Assuming size/clarity are populated if blooming
            value += (flower.clarity or 0) * 20
            value += COLOR_VALUE_MAP.get(flower.color, 0) if flower.color else 0
            value += SPECIAL_TYPE_BONUS_MAP.get(flower.special_type, 0) if flower.special_type else 0
            flower.appraised_value = int(value)

            db.session.commit()
            logger.info(f"Flower {flower_id} appraised for user {user_id}. Value: {value}. Cost: {APPRAISAL_COST}. New balance: {user.balance}")
        except Exception as e:
            db.session.rollback()
            logger.error(f"Database error during appraisal of flower {flower_id} for user {user_id}: {e}", exc_info=True)
            raise DatabaseError("Error during appraisal.", original_exception=e)
        return flower

    def _get_size_descriptor(self, size_value: float) -> tuple[str, str]:
        if size_value < 1.0: return "Tiny", "tiny"
        if size_value < 2.5: return "Small", "small"
        if size_value < 4.0: return "Medium", "medium"
        if size_value < 6.0: return "Large", "large"
        return "Grand", "grand"

    def _get_clarity_descriptor(self, clarity_value: float) -> tuple[str, str]:
        if clarity_value < 0.3: return "Cloudy", "cloudy"
        if clarity_value < 0.6: return "Slightly Included", "included"
        if clarity_value < 0.9: return "Clear", "clear"
        return "Flawless", "flawless"

    def _get_gem_base_name(self, color: str) -> str:
        color_map = {
            'red': "Ruby", 'blue': "Sapphire", 'green': "Emerald",
            'purple': "Amethyst", 'yellow': "Citrine", 'gold_yellow': "Golden Citrine",
            'clear': "Diamond", 'white': "Quartz", 'grey': "Smoky Quartz",
            'brown': "Topaz", 'orange': "Orange Topaz", 'pink': "Rose Quartz",
            'black': "Onyx",
            # Add more as colors are defined in seeds
        }
        return color_map.get(color.lower() if color else "", "Crystal")

    def _generate_crystal_description_and_signature(self, flower: CrystalFlower) -> dict:
        size_val = flower.size or 0.0
        clarity_val = flower.clarity or 0.0
        color_val = flower.color or "N/A"
        special_val = flower.special_type or "none"

        size_desc, size_sig = self._get_size_descriptor(size_val)
        clarity_desc, clarity_sig = self._get_clarity_descriptor(clarity_val)
        base_gem_name = self._get_gem_base_name(color_val)

        name_parts = []
        if special_val != 'none' and special_val is not None:
            name_parts.append(special_val.replace("_", " ").capitalize()) # "Rare sparkle" -> "Rare Sparkle"

        name_parts.append(clarity_desc)
        name_parts.append(size_desc)
        name_parts.append(color_val.capitalize() if color_val != "N/A" else "")
        name_parts.append(base_gem_name)

        crystal_name = " ".join(filter(None, name_parts)).strip()
        if not crystal_name: # Fallback
            crystal_name = f"{size_desc} {base_gem_name}"


        notes_parts = ["A"]
        if special_val != 'none' and special_val is not None:
            notes_parts.append(special_val.replace("_", " "))
        notes_parts.append(f"{size_desc.lower()} specimen of {color_val.lower()} {base_gem_name}.")
        notes_parts.append(f"It exhibits {clarity_desc.lower()} clarity.")
        generated_notes = " ".join(notes_parts).strip() + "."


        # Signature generation
        # Quantized size, quantized clarity, color string, special type string
        signature_str = f"sz:{size_sig}|clrty:{clarity_sig}|c:{color_val.lower()}|sp:{special_val.lower()}"

        return {
            "crystal_name": crystal_name,
            "notes": generated_notes,
            "signature": signature_str
        }

    def sell_crystal(self, user_id: int, flower_id: int) -> dict:
        """
        Sells an appraised crystal flower and creates or updates a codex entry.
        Raises UserNotFoundError, FlowerNotFoundError, FlowerNotBloomingError,
               FlowerNotAppraisedError, DatabaseError.
        """
        if not all(isinstance(arg, int) for arg in [user_id, flower_id]):
            logger.warning(f"sell_crystal: Invalid input type: user_id={user_id}, flower_id={flower_id}")
            raise ServiceError("Invalid input type for user_id or flower_id.", status_code=400, error_code="INVALID_INPUT_TYPE")

        user = User.query.get(user_id)
        if not user:
            raise UserNotFoundError(user_id)

        flower = CrystalFlower.query.filter_by(id=flower_id, user_id=user_id).first()
        if not flower:
            raise FlowerNotFoundError(flower_id, user_id)

        if flower.growth_stage != 'blooming':
            logger.info(f"Attempt to sell non-blooming flower {flower_id} (stage: {flower.growth_stage}) for user {user_id}.")
            raise FlowerNotBloomingError("Only blooming flowers can be sold.")
        if flower.appraised_value is None:
            logger.info(f"Attempt to sell non-appraised flower {flower_id} for user {user_id}.")
            raise FlowerNotAppraisedError("Flower must be appraised before selling.")

        try:
            sold_value = flower.appraised_value
            user.balance += sold_value

            desc_data = self._generate_crystal_description_and_signature(flower)
            crystal_name = desc_data["crystal_name"]
            notes = desc_data["notes"]
            signature = desc_data["signature"]

            existing_codex_entry = CrystalCodexEntry.query.filter_by(
                user_id=user_id, signature=signature
            ).first()

            if not existing_codex_entry:
                new_codex_entry = CrystalCodexEntry(
                    user_id=user_id, crystal_name=crystal_name,
                    color=flower.color or 'N/A', size=flower.size or 0.0,
                    clarity=flower.clarity or 0.0, special_type=flower.special_type or 'none',
                    first_discovered_at=datetime.now(timezone.utc),
                    notes=notes, signature=signature
                )
                db.session.add(new_codex_entry)
                logger.info(f"New codex entry '{crystal_name}' (sig: {signature}) created for user {user_id}.")
            # else: # Future: Update count or last_sold_at
            #    logger.info(f"Codex entry for sig: {signature} already exists for user {user_id}. Not creating duplicate.")

            db.session.delete(flower)
            db.session.commit()
            logger.info(f"Flower {flower_id} sold by user {user_id} for {sold_value}. New balance: {user.balance}. Codex name: '{crystal_name}'")
        except IntegrityError as e: # Catch specific integrity errors, e.g. if unique constraint on codex fails unexpectedly
            db.session.rollback()
            logger.error(f"Integrity error selling crystal {flower_id} for user {user_id}: {e}", exc_info=True)
            raise DatabaseError("Error saving codex entry during crystal sale.", original_exception=e)
        except Exception as e:
            db.session.rollback()
            logger.error(f"Database error selling crystal {flower_id} for user {user_id}: {e}", exc_info=True)
            raise DatabaseError("Error selling crystal.", original_exception=e)

        return {"sold_value": sold_value, "message": f"Crystal '{crystal_name}' sold."}

# crystal_garden_service = CrystalGardenService()
