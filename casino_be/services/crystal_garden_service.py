from sqlalchemy.exc import IntegrityError
from datetime import datetime, timezone
import random
import json # Though direct dict access for JSON field is usually fine with SQLAlchemy

from casino_be.models import db, User, CrystalSeed, CrystalFlower, PlayerGarden, CrystalCodexEntry

# --- Custom Exceptions ---
class ServiceError(Exception):
    """Base class for service layer errors."""
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
    'fertilizer': 10,
    'moon_glow': 15,
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
        Raises ItemNotFoundError if user does not exist.
        """
        garden = PlayerGarden.query.filter_by(user_id=user_id).first()
        if not garden:
            user = User.query.get(user_id)
            if not user:
                raise ItemNotFoundError(f"User with ID {user_id} not found.")
            try:
                garden = PlayerGarden(user_id=user_id)
                db.session.add(garden)
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                garden = PlayerGarden.query.filter_by(user_id=user_id).first()
                if not garden: # Should not happen if IntegrityError was due to garden creation race
                    raise ServiceError("Failed to retrieve or create garden after race condition.")
            except Exception as e:
                db.session.rollback()
                # Log e
                raise ServiceError(f"Error creating garden: {str(e)}")
        return garden

    def buy_seed(self, user_id: int, seed_id: int) -> CrystalSeed:
        """
        Allows a user to buy a crystal seed.
        Raises ItemNotFoundError, InsufficientFundsError.
        """
        user = User.query.get(user_id)
        if not user:
            raise ItemNotFoundError(f"User with ID {user_id} not found.")

        seed = CrystalSeed.query.get(seed_id)
        if not seed:
            raise ItemNotFoundError(f"CrystalSeed with ID {seed_id} not found.")

        if user.balance < seed.cost:
            raise InsufficientFundsError(f"User {user_id} has insufficient funds for seed {seed_id}.")

        try:
            user.balance -= seed.cost
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            # Log e
            raise ServiceError(f"Error processing seed purchase: {str(e)}")

        return seed

    def plant_seed(self, user_id: int, seed_id: int, garden_plot_x: int, garden_plot_y: int) -> CrystalFlower:
        """
        Plants a seed in the player's garden.
        Raises ItemNotFoundError, InvalidPlotError, PlotOccupiedError.
        """
        garden = self.get_or_create_player_garden(user_id) # Ensures garden exists or raises if user not found

        seed = CrystalSeed.query.get(seed_id) # Assuming buy_seed was called prior, so seed should exist
        if not seed:
            raise ItemNotFoundError(f"CrystalSeed with ID {seed_id} not found.")

        if not (0 <= garden_plot_x < garden.grid_size_x and 0 <= garden_plot_y < garden.grid_size_y):
            raise InvalidPlotError(f"Plot ({garden_plot_x}, {garden_plot_y}) is outside garden boundaries.")

        existing_flower = CrystalFlower.query.filter_by(
            player_garden_id=garden.id,
            position_x=garden_plot_x,
            position_y=garden_plot_y
        ).first()
        if existing_flower:
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
                active_power_ups=[] # Initialize as empty list for JSON field
            )
            db.session.add(new_flower)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            # Log e
            raise ServiceError(f"Error planting seed: {str(e)}")
        return new_flower

    def get_garden_state(self, user_id: int) -> dict:
        """
        Retrieves the state of the player's garden.
        """
        garden = self.get_or_create_player_garden(user_id)

        flowers = CrystalFlower.query.filter_by(player_garden_id=garden.id).all()

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
        """
        user = User.query.get(user_id)
        if not user: # Should not happen if user_id comes from auth
            raise ItemNotFoundError(f"User with ID {user_id} not found.")
        return CrystalCodexEntry.query.filter_by(user_id=user_id).all()

    def apply_power_up(self, user_id: int, flower_id: int, power_up_type: str) -> CrystalFlower:
        """
        Applies a power-up to a crystal flower.
        Raises ItemNotFoundError, InsufficientFundsError.
        """
        user = User.query.get(user_id)
        if not user:
            raise ItemNotFoundError(f"User {user_id} not found.")

        flower = CrystalFlower.query.filter_by(id=flower_id, user_id=user_id).first()
        if not flower:
            raise ItemNotFoundError(f"CrystalFlower {flower_id} not found for user {user_id}.")

        cost = POWER_UP_COSTS.get(power_up_type)
        if cost is None:
            raise InvalidActionError(f"Unknown power-up type: {power_up_type}")

        if user.balance < cost:
            raise InsufficientFundsError(f"Insufficient funds for power-up '{power_up_type}'.")

        try:
            user.balance -= cost

            # Ensure active_power_ups is a list
            if flower.active_power_ups is None:
                flower.active_power_ups = []

            # Add power-up (could store more info, like timestamp)
            flower.active_power_ups.append(power_up_type)
            # For SQLAlchemy to detect change in JSON mutable type
            flower.active_power_ups = list(flower.active_power_ups)

            if flower.details is None:
                flower.details = {}

            if power_up_type == 'fertilizer':
                current_growth_mod = flower.details.get('growth_modifier', 1.0)
                flower.details['growth_modifier'] = round(current_growth_mod + 0.1, 3) # Using round for float precision
            elif power_up_type == 'moon_glow':
                current_clarity_mod = flower.details.get('clarity_modifier', 1.0)
                flower.details['clarity_modifier'] = round(current_clarity_mod + 0.05, 3) # Using round

            # Mark 'details' as modified for SQLAlchemy if it's a JSON field
            # This is often handled automatically if the top-level assignment flower.details = new_dict occurs,
            # but explicit marking is safer with nested modifications if not reassigning the whole dict.
            # However, since we are potentially reassigning (if flower.details was None) or directly setting keys
            # on an existing dict, SQLAlchemy's default tracking should detect this.
            # If issues arise, uncomment:
            # from sqlalchemy.orm.attributes import flag_modified
            # flag_modified(flower, "details")

            db.session.commit()
        except Exception as e:
            db.session.rollback()
            # Log e
            raise ServiceError(f"Error applying power-up: {str(e)}")
        return flower

    def _randomize_attribute(self, outcomes, key, power_ups_active=None):
        """Helper to randomize a single attribute based on potential_outcomes."""
        # power_ups_active is not used yet, but could be for biasing
        config = outcomes.get(key, {})
        if not config: return None

        if "distribution" in config and config["distribution"] == "uniform":
            min_val, max_val = config.get("min", 0), config.get("max", 1)
            return random.uniform(min_val, max_val)
        elif isinstance(config, dict): # Weighted choices for things like color, special_type
            choices = list(config.keys())
            weights = [float(w) for w in config.values()] # Ensure weights are float
            if not choices or sum(weights) == 0: return None # Avoid error with empty choices or all zero weights
            return random.choices(choices, weights=weights, k=1)[0]
        return None

    def process_growth_cycle(self, garden_id: int) -> dict:
        """
        Processes one growth cycle for all flowers in a garden.
        """
        garden = PlayerGarden.query.get(garden_id)
        if not garden:
            raise ItemNotFoundError(f"PlayerGarden {garden_id} not found.")

        flowers = CrystalFlower.query.filter_by(player_garden_id=garden.id).all()
        summary = {"updated_flowers": 0, "newly_bloomed": 0}

        for flower in flowers:
            updated = True
            if flower.growth_stage == 'seeded':
                flower.growth_stage = 'sprouting'
            elif flower.growth_stage == 'sprouting':
                flower.growth_stage = 'blooming'
                summary["newly_bloomed"] += 1

                seed = CrystalSeed.query.get(flower.crystal_seed_id)
                if seed and seed.potential_outcomes:
                    # Ensure potential_outcomes is a dict
                    outcomes = seed.potential_outcomes if isinstance(seed.potential_outcomes, dict) else {}

                    flower.color = self._randomize_attribute(outcomes, "colors", flower.active_power_ups)
                    flower.size = round(self._randomize_attribute(outcomes, "sizes", flower.active_power_ups) or 1.0, 2)
                    flower.clarity = round(self._randomize_attribute(outcomes, "clarities", flower.active_power_ups) or 0.1, 2)
                    flower.special_type = self._randomize_attribute(outcomes, "special_types", flower.active_power_ups)
                else: # Fallback if no outcomes defined
                    flower.color = random.choice(['blue', 'red', 'green'])
                    flower.size = round(random.uniform(1.0, 5.0), 2)
                    flower.clarity = round(random.uniform(0.1, 1.0), 2)
                    flower.special_type = 'none'

            #elif flower.growth_stage == 'blooming':
                # Future: Could transition to 'withered' here based on time or cycles
                # updated = False
            else: # 'blooming', 'withered', or other
                updated = False

            if updated:
                summary["updated_flowers"] += 1

        try:
            garden.last_cycle_time = datetime.now(timezone.utc)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            # Log e
            raise ServiceError(f"Error finalizing growth cycle: {str(e)}")

        summary["garden_id"] = garden_id
        summary["last_cycle_time"] = garden.last_cycle_time.isoformat()
        return summary

    def appraise_crystal(self, user_id: int, flower_id: int) -> CrystalFlower:
        """
        Appraises a crystal flower and sets its value.
        """
        user = User.query.get(user_id)
        if not user:
            raise ItemNotFoundError(f"User {user_id} not found.")

        flower = CrystalFlower.query.filter_by(id=flower_id, user_id=user_id).first()
        if not flower:
            raise ItemNotFoundError(f"CrystalFlower {flower_id} not found for user {user_id}.")

        if flower.growth_stage != 'blooming':
            raise InvalidActionError("Only blooming flowers can be appraised.")

        if user.balance < APPRAISAL_COST:
            raise InsufficientFundsError("Insufficient funds for appraisal.")

        try:
            user.balance -= APPRAISAL_COST

            value = (flower.size or 0) * 10
            value += (flower.clarity or 0) * 20
            value += COLOR_VALUE_MAP.get(flower.color, 0) if flower.color else 0
            value += SPECIAL_TYPE_BONUS_MAP.get(flower.special_type, 0) if flower.special_type else 0
            flower.appraised_value = int(value)

            db.session.commit()
        except Exception as e:
            db.session.rollback()
            # Log e
            raise ServiceError(f"Error during appraisal: {str(e)}")
        return flower

    def sell_crystal(self, user_id: int, flower_id: int) -> dict:
        """
        Sells an appraised crystal flower.
        """
        user = User.query.get(user_id)
        if not user:
            raise ItemNotFoundError(f"User {user_id} not found.")

        flower = CrystalFlower.query.filter_by(id=flower_id, user_id=user_id).first()
        if not flower:
            raise ItemNotFoundError(f"CrystalFlower {flower_id} not found for user {user_id}.")

        if flower.growth_stage != 'blooming':
            raise InvalidActionError("Only blooming flowers can be sold.")
        if flower.appraised_value is None:
            raise InvalidActionError("Flower must be appraised before selling.")

        try:
            sold_value = flower.appraised_value
            user.balance += sold_value

            # Create Codex Entry
            crystal_name = f"{flower.size:.1f} {flower.color or 'Unknown Color'} Crystal ({flower.special_type or 'Standard'})"

            existing_codex_entry = CrystalCodexEntry.query.filter_by(
                user_id=user_id,
                crystal_name=crystal_name
            ).first()

            current_time = datetime.now(timezone.utc)
            if existing_codex_entry:
                # Update existing entry
                existing_codex_entry.discovery_count = (existing_codex_entry.discovery_count or 1) + 1
                existing_codex_entry.last_discovered_at = current_time
                # existing_codex_entry.notes = "Discovered again." # Optional: update notes
                db.session.add(existing_codex_entry)
            else:
                # Create new entry
                new_codex_entry = CrystalCodexEntry(
                    user_id=user_id,
                    crystal_name=crystal_name,
                    color=flower.color or 'N/A',
                    size=flower.size or 0.0,
                    clarity=flower.clarity or 0.0, # Include clarity
                    special_type=flower.special_type or 'N/A',
                    first_discovered_at=current_time,
                    last_discovered_at=current_time,
                    discovery_count=1
                    # notes field can be used for player notes or game lore
                )
                db.session.add(new_codex_entry)

            db.session.delete(flower)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            # Log e
            raise ServiceError(f"Error selling crystal: {str(e)}")

        return {"sold_value": sold_value, "message": f"Crystal {crystal_name} sold."}

# crystal_garden_service = CrystalGardenService()
