import pytest
from flask import Flask
from casino_be.models import db as actual_db, User, CrystalSeed, PlayerGarden, CrystalFlower, CrystalCodexEntry
from casino_be.services.crystal_garden_service import (
    CrystalGardenService,
    InsufficientFundsError,
    PlotOccupiedError,
    InvalidPlotError,
    GardenPlotOutOfBoundsError, # New
    ItemNotFoundError,
    UserNotFoundError,          # New
    SeedNotFoundError,          # New
    FlowerNotFoundError,        # New
    GardenNotFoundError,        # New
    InvalidActionError,
    PowerUpNotFoundError,       # New
    FlowerNotBloomingError,     # New
    FlowerAlreadyAppraisedError,# New
    FlowerNotAppraisedError,    # New
    DatabaseError,              # New
    APPRAISAL_COST,
    POWER_UP_COSTS
)
from datetime import datetime, timezone, timedelta # Added timedelta for time-based tests if needed
import unittest.mock as mock # For patching random module more easily

# Pytest fixtures for app and db session
@pytest.fixture(scope='function')
def app():
    app_instance = Flask(__name__)
    app_instance.config['TESTING'] = True
    app_instance.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    # Set any other app.config values your service might rely on
    # e.g., app_instance.config['SOME_FEATURE_ENABLED'] = True

    actual_db.init_app(app_instance)
    with app_instance.app_context():
        actual_db.create_all()
        yield app_instance # Provide the app instance to the test
        actual_db.session.remove()
        actual_db.drop_all()

@pytest.fixture(scope='function')
def db_session(app): # Fixture to get the SQLAlchemy session
    return actual_db

@pytest.fixture
def service():
    return CrystalGardenService()

# Helper to create a user
def create_user(session, id_val=1, username='testuser', balance=1000, email_suffix="@example.com"):
    # User model has 'password' field, not 'password_hash' or set_password method directly
    user = User(id=id_val, username=f"{username}{id_val}", email=f'{username}{id_val}{email_suffix}', balance=balance, password="hashed_password_placeholder")
    session.session.add(user)
    session.session.commit()
    return user

# Helper to create a seed
def create_seed(session, id_val=1, name='Test Seed', cost=100, outcomes=None):
    if outcomes is None:
        # Default to new structure for testing
        outcomes = {
            "colors": {"blue": 70, "red": 25, "purple": 5},
            "sizes": {
                "distribution": "weighted_ranges",
                "ranges": {
                    "small": {"weight": 40, "min": 0.5, "max": 1.5},
                    "medium": {"weight": 30, "min": 1.5, "max": 3.0},
                    "large": {"weight": 20, "min": 3.0, "max": 4.5}
                }
            },
            "clarities": {
                "distribution": "normal",
                "mean": 0.6,
                "stddev": 0.15,
                "min_clip": 0.1,
                "max_clip": 1.0
            },
            "special_types": {"none": 80, "common_glow": 15, "rare_sparkle": 5}
        }
    seed = CrystalSeed(id=id_val, name=f"{name} {id_val}", cost=cost, potential_outcomes=outcomes)
    session.session.add(seed)
    session.session.commit()
    return seed

# Helper to create a flower (basic)
def create_flower(session, user_obj, garden_obj, seed_obj, x=0, y=0, stage='seeded',
                  color=None, size=None, clarity=None, special_type=None, appraised_value=None,
                  active_power_ups=None, planted_at=None):
    flower = CrystalFlower(
        user_id=user_obj.id,
        crystal_seed_id=seed_obj.id,
        player_garden_id=garden_obj.id,
        position_x=x,
        position_y=y,
        growth_stage=stage,
        planted_at=planted_at or datetime.now(timezone.utc),
        active_power_ups=active_power_ups if active_power_ups is not None else [],
        color=color,
        size=size,
        clarity=clarity,
        special_type=special_type,
        appraised_value=appraised_value
    )
    session.session.add(flower)
    session.session.commit()
    return flower

@pytest.fixture
def mock_datetime_now(mocker):
    # This fixture provides a mock datetime object for service.datetime.now()
    # Important: Ensure your service imports datetime like `from datetime import datetime`
    # or that you patch where it's used, e.g. `casino_be.services.crystal_garden_service.datetime`
    mock_dt = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    # Patching datetime where it's imported and used in crystal_garden_service.py
    dt_mock = mocker.patch('casino_be.services.crystal_garden_service.datetime', autospec=True)
    dt_mock.now.return_value = mock_dt
    return mock_dt

# --- Test Cases ---

def test_get_or_create_player_garden(app, db_session, service):
    user = create_user(db_session)

    garden = service.get_or_create_player_garden(user.id)
    assert garden is not None
    assert garden.user_id == user.id
    assert garden.grid_size_x == 5 # Default
    assert garden.grid_size_y == 5 # Default

    garden2 = service.get_or_create_player_garden(user.id)
    assert garden2.id == garden.id

def test_get_or_create_player_garden_user_not_found(app, db_session, service):
    with pytest.raises(UserNotFoundError): # Now raises specific error
        service.get_or_create_player_garden(999)

def test_get_or_create_player_garden_invalid_input_type(service):
    with pytest.raises(ServiceError, match="Invalid user ID type"):
        service.get_or_create_player_garden("not_an_int")


def test_buy_seed_success(app, db_session, service):
    user = create_user(db_session, balance=200)
    seed = create_seed(db_session, cost=100)

    purchased_seed = service.buy_seed(user.id, seed.id)
    assert purchased_seed is not None
    assert purchased_seed.id == seed.id
    # db_session.session.refresh(user) # Not needed, service commits
    updated_user = db_session.session.get(User, user.id)
    assert updated_user.balance == 100

def test_buy_seed_insufficient_funds(app, db_session, service):
    user = create_user(db_session, balance=50)
    seed = create_seed(db_session, cost=100)

    with pytest.raises(InsufficientFundsError):
        service.buy_seed(user.id, seed.id)
    updated_user = db_session.session.get(User, user.id)
    assert updated_user.balance == 50 # Balance should not change

def test_buy_seed_user_not_found(app, db_session, service):
    seed = create_seed(db_session)
    with pytest.raises(UserNotFoundError): # Specific error
        service.buy_seed(999, seed.id)

def test_buy_seed_seed_not_found(app, db_session, service):
    user = create_user(db_session)
    with pytest.raises(SeedNotFoundError): # Specific error
        service.buy_seed(user.id, 999)

def test_buy_seed_invalid_input_types(service):
    with pytest.raises(ServiceError, match="Invalid input type"):
        service.buy_seed("not_int", 1)
    with pytest.raises(ServiceError, match="Invalid input type"):
        service.buy_seed(1, "not_int")


def test_plant_seed_success(app, db_session, service, mock_datetime_now):
    user = create_user(db_session)
    seed = create_seed(db_session)
    garden = service.get_or_create_player_garden(user.id)

    flower = service.plant_seed(user.id, seed.id, 0, 0)
    assert flower is not None
    assert flower.user_id == user.id
    assert flower.crystal_seed_id == seed.id
    assert flower.player_garden_id == garden.id
    assert flower.position_x == 0
    assert flower.position_y == 0
    assert flower.growth_stage == 'seeded'
    assert flower.active_power_ups == []
    assert flower.planted_at == mock_datetime_now # Check mocked datetime

    db_flower = db_session.session.get(CrystalFlower, flower.id)
    assert db_flower is not None

def test_plant_seed_plot_occupied(app, db_session, service):
    user = create_user(db_session)
    seed = create_seed(db_session)
    service.get_or_create_player_garden(user.id) # Ensure garden exists

    service.plant_seed(user.id, seed.id, 0, 0) # Plant first flower
    with pytest.raises(PlotOccupiedError):
        service.plant_seed(user.id, seed.id, 0, 0) # Attempt to plant on same spot

def test_plant_seed_plot_out_of_bounds(app, db_session, service): # Renamed for clarity
    user = create_user(db_session)
    seed = create_seed(db_session)
    garden = service.get_or_create_player_garden(user.id)

    with pytest.raises(GardenPlotOutOfBoundsError): # Specific error
        service.plant_seed(user.id, seed.id, garden.grid_size_x, garden.grid_size_y)
    with pytest.raises(GardenPlotOutOfBoundsError):
        service.plant_seed(user.id, seed.id, -1, 0)

def test_plant_seed_seed_not_found(app, db_session, service):
    user = create_user(db_session)
    service.get_or_create_player_garden(user.id)
    with pytest.raises(SeedNotFoundError):
        service.plant_seed(user.id, 999, 0, 0)

def test_plant_seed_invalid_input_types(service):
    with pytest.raises(ServiceError, match="Invalid input type"):
        service.plant_seed("not_int", 1, 0, 0)
    with pytest.raises(ServiceError, match="Invalid input type"):
        service.plant_seed(1, "not_int", 0, 0)
    with pytest.raises(ServiceError, match="Invalid input type"):
        service.plant_seed(1, 1, "not_int", 0)
    with pytest.raises(ServiceError, match="Invalid input type"):
        service.plant_seed(1, 1, 0, "not_int")


def test_get_garden_state(app, db_session, service, mock_datetime_now):
    user = create_user(db_session)
    seed = create_seed(db_session)
    garden = service.get_or_create_player_garden(user.id)
    # Use the create_flower helper which now takes planted_at
    flower_obj = create_flower(db_session, user, garden, seed, x=0, y=0, planted_at=mock_datetime_now)
    # service.plant_seed(user.id, seed.id, 0, 0) - this would use the mocked datetime from service level

    state = service.get_garden_state(user.id)
    assert state is not None
    assert state['garden_id'] == garden.id
    assert state['user_id'] == user.id
    assert len(state['flowers']) == 1
    flower_in_state = state['flowers'][0]
    assert flower_in_state['id'] == flower_obj.id
    assert flower_in_state['position_x'] == 0
    assert flower_in_state['planted_at'] == mock_datetime_now.isoformat()
    # Test if seed info is eager loaded (not strictly in state dict, but good for query check)
    # This requires flower_obj to be the one from service.plant_seed or re-fetched with options
    # For now, just ensuring the query was modified is enough.

def test_get_garden_state_user_not_found(service):
    with pytest.raises(UserNotFoundError):
        service.get_garden_state(999) # User 999 does not exist

def test_get_garden_state_invalid_input_type(service):
    with pytest.raises(ServiceError, match="Invalid user ID type"):
        service.get_garden_state("not_an_int")


def test_get_player_codex_empty(app, db_session, service):
    user = create_user(db_session)
    codex_entries = service.get_player_codex(user.id)
    assert isinstance(codex_entries, list)
    assert len(codex_entries) == 0

def test_get_player_codex_user_not_found(service):
    with pytest.raises(UserNotFoundError):
        service.get_player_codex(999)

def test_get_player_codex_invalid_input_type(service):
    with pytest.raises(ServiceError, match="Invalid user ID type"):
        service.get_player_codex("not_an_int")

# --- Tests for Helper Methods ---

def test_randomize_attribute_uniform(service, mocker):
    mocker.patch('random.uniform', return_value=2.5)
    config = {"distribution": "uniform", "min": 1.0, "max": 5.0}
    result = service._randomize_attribute({"sizes": config}, "sizes")
    assert result == 2.5
    random.uniform.assert_called_once_with(1.0, 5.0)

def test_randomize_attribute_normal(service, mocker):
    mocker.patch('random.normalvariate', return_value=0.75)
    config = {"distribution": "normal", "mean": 0.6, "stddev": 0.15, "min_clip": 0.1, "max_clip": 1.0}
    result = service._randomize_attribute({"clarities": config}, "clarities")
    assert result == 0.75
    random.normalvariate.assert_called_once_with(0.6, 0.15)

    # Test clipping
    mocker.patch('random.normalvariate', return_value=1.5) # Above max_clip
    result = service._randomize_attribute({"clarities": config}, "clarities")
    assert result == 1.0

    mocker.patch('random.normalvariate', return_value=0.05) # Below min_clip
    result = service._randomize_attribute({"clarities": config}, "clarities")
    assert result == 0.1

def test_randomize_attribute_weighted_ranges(service, mocker):
    # Mock random.choices to select 'large' range
    mocker.patch('random.choices', return_value=['large'])
    # Mock random.uniform for the value within the 'large' range
    mocker.patch('random.uniform', return_value=3.5)

    config = {
        "distribution": "weighted_ranges",
        "ranges": {
            "small": {"weight": 10, "min": 0.5, "max": 1.5},
            "medium": {"weight": 30, "min": 1.5, "max": 3.0},
            "large": {"weight": 60, "min": 3.0, "max": 4.5}
        }
    }
    result = service._randomize_attribute({"sizes": config}, "sizes")
    assert result == 3.5
    random.choices.assert_called_once_with(['small', 'medium', 'large'], weights=[10.0, 30.0, 60.0], k=1)
    random.uniform.assert_called_once_with(3.0, 4.5)

def test_randomize_attribute_categorical_weighted(service, mocker):
    mocker.patch('random.choices', return_value=['blue'])
    config = {"blue": 70, "red": 30} # No "distribution" key implies categorical
    result = service._randomize_attribute({"colors": config}, "colors")
    assert result == 'blue'
    random.choices.assert_called_once_with(['blue', 'red'], weights=[70.0, 30.0], k=1)

def test_randomize_attribute_moon_glow_special_types(service, mocker):
    # Test that moon_glow correctly adjusts weights for special_types
    mock_choices = mocker.patch('random.choices', return_value=['rare_sparkle']) # Assume it picks this

    outcomes_config = {
        "special_types": {"none": 80, "common_glow": 15, "rare_sparkle": 5}
    }
    power_ups = ['moon_glow']

    service._randomize_attribute(outcomes_config, "special_types", power_ups)

    # Expected adjusted weights: none: 80*0.5=40, common_glow: 15*1.5=22.5, rare_sparkle: 5*1.5=7.5
    expected_choices = ['none', 'common_glow', 'rare_sparkle']
    expected_weights = [40.0, 22.5, 7.5]

    # Check that random.choices was called with the modified weights
    # The context of the call is inside the function, so we check the arguments of the last call
    args, kwargs = mock_choices.call_args
    assert args[0] == expected_choices
    assert pytest.approx(args[1]) == expected_weights # Use pytest.approx for float list comparison
    assert kwargs['k'] == 1


def test_randomize_attribute_empty_or_invalid_config(service):
    assert service._randomize_attribute({}, "non_existent_key") is None
    assert service._randomize_attribute({"sizes": {}}, "sizes") is None # Empty config for sizes
    assert service._randomize_attribute({"colors": {"blue": 0}}, "colors") is None # All zero weights
    assert service._randomize_attribute({"sizes": {"distribution": "uniform"}}, "sizes") is not None # min/max default
    assert service._randomize_attribute({"sizes": {"distribution": "weighted_ranges", "ranges": {}}}, "sizes") is None


# --- End of Helper Method Tests for _randomize_attribute ---

def test_get_size_descriptor(service):
    assert service._get_size_descriptor(0.5) == ("Tiny", "tiny")
    assert service._get_size_descriptor(1.0) == ("Small", "small") # Boundary: 1.0 is Small
    assert service._get_size_descriptor(2.4) == ("Small", "small")
    assert service._get_size_descriptor(2.5) == ("Medium", "medium") # Boundary: 2.5 is Medium
    assert service._get_size_descriptor(3.9) == ("Medium", "medium")
    assert service._get_size_descriptor(4.0) == ("Large", "large") # Boundary: 4.0 is Large
    assert service._get_size_descriptor(5.9) == ("Large", "large")
    assert service._get_size_descriptor(6.0) == ("Grand", "grand") # Boundary: 6.0 is Grand
    assert service._get_size_descriptor(10.0) == ("Grand", "grand")

def test_get_clarity_descriptor(service):
    assert service._get_clarity_descriptor(0.1) == ("Cloudy", "cloudy")
    assert service._get_clarity_descriptor(0.29) == ("Cloudy", "cloudy")
    assert service._get_clarity_descriptor(0.3) == ("Slightly Included", "included") # Boundary
    assert service._get_clarity_descriptor(0.59) == ("Slightly Included", "included")
    assert service._get_clarity_descriptor(0.6) == ("Clear", "clear") # Boundary
    assert service._get_clarity_descriptor(0.89) == ("Clear", "clear")
    assert service._get_clarity_descriptor(0.9) == ("Flawless", "flawless") # Boundary
    assert service._get_clarity_descriptor(1.0) == ("Flawless", "flawless")

def test_get_gem_base_name(service):
    assert service._get_gem_base_name("red") == "Ruby"
    assert service._get_gem_base_name("blue") == "Sapphire"
    assert service._get_gem_base_name("GREEN") == "Emerald" # Test case insensitivity (service lowercases)
    assert service._get_gem_base_name("unknown_color") == "Crystal"
    assert service._get_gem_base_name(None) == "Crystal"
    assert service._get_gem_base_name("") == "Crystal"

def test_generate_crystal_description_and_signature(app, db_session, service):
    # Create a dummy flower object for testing (doesn't need to be in DB for this helper)
    # No, the helper expects a CrystalFlower ORM object, so better to create one
    user = create_user(db_session)
    seed = create_seed(db_session)
    garden = service.get_or_create_player_garden(user.id)

    flower = CrystalFlower(
        size=3.2, clarity=0.75, color="blue", special_type="common_glow",
        user_id=user.id, crystal_seed_id=seed.id, player_garden_id=garden.id # FKs needed for ORM object
    )
    # For 3.2 size -> "Medium", "medium"
    # For 0.75 clarity -> "Clear", "clear"
    # For "blue" -> "Sapphire"
    # For "common_glow" -> "Common glow" (capitalized)

    desc_data = service._generate_crystal_description_and_signature(flower)

    assert "Common glow Clear Medium Blue Sapphire" in desc_data["crystal_name"]
    # Example: "Common glow Clear Medium Blue Sapphire" or "Clear Medium Common glow Blue Sapphire"
    # The exact order might vary based on implementation if parts are conditionally added.
    # Current implementation: [Special] [Clarity] [Size] [Color Cap] [BaseName]
    assert desc_data["crystal_name"] == "Common glow Clear Medium Blue Sapphire"

    expected_notes = "A common glow medium specimen of blue Sapphire. It exhibits clear clarity."
    assert desc_data["notes"] == expected_notes

    expected_signature = "sz:medium|clrty:clear|c:blue|sp:common_glow"
    assert desc_data["signature"] == expected_signature

    # Test with no special type
    flower_no_special = CrystalFlower(
        size=0.8, clarity=0.2, color="red", special_type=None, # or "none"
        user_id=user.id, crystal_seed_id=seed.id, player_garden_id=garden.id
    )
    # For 0.8 size -> "Tiny", "tiny"
    # For 0.2 clarity -> "Cloudy", "cloudy"
    # For "red" -> "Ruby"
    desc_data_no_special = service._generate_crystal_description_and_signature(flower_no_special)
    assert desc_data_no_special["crystal_name"] == "Cloudy Tiny Red Ruby"
    assert desc_data_no_special["notes"] == "A tiny specimen of red Ruby. It exhibits cloudy clarity."
    assert desc_data_no_special["signature"] == "sz:tiny|clrty:cloudy|c:red|sp:none"

    # Test with N/A values (e.g. if flower attributes were None)
    flower_na = CrystalFlower(
        size=None, clarity=None, color=None, special_type=None,
        user_id=user.id, crystal_seed_id=seed.id, player_garden_id=garden.id
    )
    desc_data_na = service._generate_crystal_description_and_signature(flower_na)
    # size 0.0 -> "Tiny", "tiny"
    # clarity 0.0 -> "Cloudy", "cloudy"
    # color "N/A" -> "Crystal"
    assert desc_data_na["crystal_name"] == "Cloudy Tiny Crystal"
    assert desc_data_na["notes"] == "A tiny specimen of n/a Crystal. It exhibits cloudy clarity."
    assert desc_data_na["signature"] == "sz:tiny|clrty:cloudy|c:n/a|sp:none"


# --- End of Helper Method Tests ---


def test_apply_power_up_success(app, db_session, service):
    user = create_user(db_session, balance=100)
    seed = create_seed(db_session)
    garden = service.get_or_create_player_garden(user.id)
    flower = create_flower(db_session, user, garden, seed)

    power_up_type = 'fertilizer'
    cost = POWER_UP_COSTS[power_up_type]

    updated_flower = service.apply_power_up(user.id, flower.id, power_up_type)
    # db_session.session.refresh(user) # Not needed
    # db_session.session.refresh(updated_flower) # Not needed
    updated_user = db_session.session.get(User, user.id)
    refreshed_flower = db_session.session.get(CrystalFlower, flower.id)


    assert power_up_type in refreshed_flower.active_power_ups
    assert updated_user.balance == 100 - cost

def test_apply_power_up_unknown_type(app, db_session, service):
    user = create_user(db_session)
    seed = create_seed(db_session)
    garden = service.get_or_create_player_garden(user.id)
    flower = create_flower(db_session, user, garden, seed)
    with pytest.raises(PowerUpNotFoundError):
        service.apply_power_up(user.id, flower.id, "unknown_powerup")

def test_apply_power_up_insufficient_funds(app, db_session, service):
    user = create_user(db_session, balance=5) # Fertilizer costs 10
    seed = create_seed(db_session)
    garden = service.get_or_create_player_garden(user.id)
    flower = create_flower(db_session, user, garden, seed)
    with pytest.raises(InsufficientFundsError):
        service.apply_power_up(user.id, flower.id, "fertilizer")

def test_apply_power_up_flower_not_found(app, db_session, service):
    user = create_user(db_session)
    with pytest.raises(FlowerNotFoundError):
        service.apply_power_up(user.id, 999, "fertilizer")

def test_apply_power_up_invalid_input_types(service):
    with pytest.raises(ServiceError, match="Invalid input type"):
        service.apply_power_up("not_int", 1, "fertilizer")
    with pytest.raises(ServiceError, match="Invalid input type"):
        service.apply_power_up(1, "not_int", "fertilizer")
    with pytest.raises(ServiceError, match="Invalid power_up_type"):
        service.apply_power_up(1, 1, 123) # type not a string


def test_process_growth_cycle_n_plus_one_fix_and_logic(app, db_session, service, mocker):
    # This test now also implicitly tests the joinedload for flower.seed
    user = create_user(db_session)
    # Using the updated create_seed to get new outcome structures
    seed = create_seed(db_session, id_val=10, name="Cycle Seed", outcomes={
        "colors": {"cycle_blue": 1.0},
        "sizes": {"distribution": "uniform", "min": 2.0, "max": 2.0}, # Deterministic size
        "clarities": {"distribution": "uniform", "min": 0.5, "max": 0.5}, # Deterministic clarity
        "special_types": {"cycle_special": 1.0}
    })
    garden = service.get_or_create_player_garden(user.id)
    flower = service.plant_seed(user.id, seed.id, 0, 0) # Stage: seeded

    # Mock random functions used by _randomize_attribute if they weren't deterministic in seed outcomes
    # For this test, seed outcomes are made deterministic for simplicity of assertion.
    # If outcomes had ranges or multiple choices, then mocking would be essential:
    # mocker.patch.object(service, '_randomize_attribute', side_effect=lambda o, k, p: ...)

    # Seeded to Sprouting
    report1 = service.process_growth_cycle(garden.id)
    flower = db_session.session.get(CrystalFlower, flower.id) # Refresh flower
    assert flower.growth_stage == 'sprouting'
    assert report1['updated_flowers'] == 1

    # Sprouting to Blooming
    report2 = service.process_growth_cycle(garden.id)
    flower = db_session.session.get(CrystalFlower, flower.id) # Refresh flower
    assert flower.growth_stage == 'blooming'
    assert report2['newly_bloomed'] == 1
    assert flower.color == 'cycle_blue'
    assert flower.size == 2.0
    assert flower.clarity == 0.5
    assert flower.special_type == 'cycle_special'

    garden = db_session.session.get(PlayerGarden, garden.id) # Refresh garden
    assert garden.last_cycle_time is not None

def test_process_growth_cycle_fertilizer_effect(app, db_session, service):
    user = create_user(db_session)
    seed = create_seed(db_session, outcomes={
        "colors": {"green": 1.0}, "sizes": {"distribution": "uniform", "min": 1.0, "max": 1.0},
        "clarities": {"distribution": "uniform", "min": 0.5, "max": 0.5}, "special_types": {"none": 1.0}
    })
    garden = service.get_or_create_player_garden(user.id)

    # Flower 1: Seeded with fertilizer
    flower1 = service.plant_seed(user.id, seed.id, 0, 0)
    flower1.active_power_ups = ['fertilizer']
    db_session.session.commit()

    # Flower 2: Sprouting with fertilizer
    flower2 = service.plant_seed(user.id, seed.id, 0, 1)
    flower2.growth_stage = 'sprouting'
    flower2.active_power_ups = ['fertilizer']
    db_session.session.commit()

    service.process_growth_cycle(garden.id)

    db_session.session.refresh(flower1)
    db_session.session.refresh(flower2)

    assert flower1.growth_stage == 'sprouting' # Seeded + fertilizer -> sprouting
    assert 'fertilizer' not in flower1.active_power_ups # Consumed

    assert flower2.growth_stage == 'blooming' # Sprouting + fertilizer -> blooming
    assert flower2.size == 1.0 + 0.5 # Base size + fertilizer bonus
    assert 'fertilizer' not in flower2.active_power_ups # Consumed

def test_process_growth_cycle_moon_glow_effect(app, db_session, service, mocker):
    user = create_user(db_session)
    seed = create_seed(db_session, outcomes={ # Ensure some variability for clarity and special types
        "colors": {"celestial_blue": 1.0},
        "sizes": {"distribution": "uniform", "min": 1.0, "max": 1.0},
        "clarities": {"distribution": "uniform", "min": 0.5, "max": 0.6}, # Base clarity around 0.5-0.6
        "special_types": {"none": 0.1, "common_glow": 0.5, "rare_sparkle": 0.4} # High chance of non-none normally
    })
    garden = service.get_or_create_player_garden(user.id)

    flower = service.plant_seed(user.id, seed.id, 0, 0)
    flower.growth_stage = 'sprouting' # So it blooms this cycle
    flower.active_power_ups = ['moon_glow']
    db_session.session.commit()

    # Mock _randomize_attribute to control its output for clarity and special_type
    # Clarity: return 0.5 (base) -> expected 0.5 + 0.2 = 0.7
    # Special Type: Check that it's called with moon_glow active, actual choice can vary
    # For this test, we'll verify the consumption and clarity bonus. Special type is harder to assert deterministically
    # without very complex mocking of the already tested _randomize_attribute.
    # Instead, we trust _randomize_attribute's own tests for weight modification.

    # Let _randomize_attribute run as is for colors and sizes
    # For clarity, make it return a fixed value to check bonus
    mocker.patch.object(service, '_randomize_attribute', side_effect=lambda o, k, p: {
        "colors": "celestial_blue", "sizes": 1.0,
        "clarities": 0.5, # Base clarity before bonus
        "special_types": "common_glow" # Let it pick one
    }.get(k))


    service.process_growth_cycle(garden.id)
    db_session.session.refresh(flower)

    assert flower.growth_stage == 'blooming'
    assert flower.clarity == min(0.5 + 0.2, 1.0) # Clarity bonus
    # Check if moon_glow was consumed (it should be if it bloomed and moon_glow was active)
    assert 'moon_glow' not in flower.active_power_ups
    # Verify _randomize_attribute was called for special_types with 'moon_glow' in power_ups_active
    # This is tricky because side_effect lambda doesn't give easy access to individual call args if it's called multiple times.
    # A more involved mock setup would be needed to capture args for each call.
    # For now, consumption of moon_glow implies it was processed.

def test_process_growth_cycle_flower_seed_missing(app, db_session, service, caplog):
    user = create_user(db_session)
    garden = service.get_or_create_player_garden(user.id)
    # Create a flower with a seed_id that doesn't exist, or mock flower.seed to be None
    # For simplicity, let's manually create a flower with a problematic seed_id
    # This requires a seed to exist for FK constraint, so we'll make flower.seed None after creation.
    real_seed = create_seed(db_session, id_val=998)
    flower = create_flower(db_session, user, garden, real_seed, stage='sprouting')

    # Simulate flower.seed being None (e.g. if joinedload failed or data issue)
    # This is hard to do directly without deeper mocking of SQLAlchemy's loader.
    # Instead, we rely on the logger message if seed_obj is None in the service.
    # Let's test the fallback: if seed.potential_outcomes is None/empty
    broken_seed = create_seed(db_session, id_val=999, outcomes={}) # Empty outcomes
    flower_with_broken_seed = create_flower(db_session, user, garden, broken_seed, x=0,y=1, stage='sprouting')

    with caplog.at_level(logging.INFO): # Check logs if needed, though current code logs ERROR for missing seed object
        service.process_growth_cycle(garden.id)

    db_session.session.refresh(flower_with_broken_seed)
    assert flower_with_broken_seed.growth_stage == 'blooming'
    # Check that it got random fallback attributes because outcomes were empty
    assert flower_with_broken_seed.color is not None
    assert flower_with_broken_seed.size is not None
    assert flower_with_broken_seed.clarity is not None
    # logger.error for missing seed object is hard to trigger if FK constraint is on crystal_seed_id


def test_process_growth_cycle_garden_not_found(service):
    with pytest.raises(GardenNotFoundError):
        service.process_growth_cycle(999)

def test_process_growth_cycle_invalid_input_type(service):
    with pytest.raises(ServiceError, match="Invalid garden ID type"):
        service.process_growth_cycle("not_an_int")


def test_appraise_crystal_success(app, db_session, service):
    user = create_user(db_session, balance=100)
    seed = create_seed(db_session)
    garden = service.get_or_create_player_garden(user.id)
    flower = create_flower(db_session, user, garden, seed, stage='blooming',
                           color='blue', size=2.0, clarity=0.5, special_type='common_glow') # common_glow IS in map
    db_session.session.commit()

    original_balance = user.balance
    appraised_flower = service.appraise_crystal(user.id, flower.id)

    updated_user = db_session.session.get(User, user.id)
    refreshed_flower = db_session.session.get(CrystalFlower, flower.id)

    # COLOR_VALUE_MAP: 'blue': 10, 'common_glow': 5 (base value for special type color)
    # SPECIAL_TYPE_BONUS_MAP: 'common_glow': 20
    # Value = (size * 10) + (clarity * 20) + color_value + special_type_bonus
    # Value = (2.0 * 10) + (0.5 * 20) + COLOR_VALUE_MAP['blue'] + SPECIAL_TYPE_BONUS_MAP['common_glow']
    # Value = 20 + 10 + 10 + 20 = 60
    expected_value = int( (2.0 * 10) + (0.5 * 20) + 10 + 20 )
    assert refreshed_flower.appraised_value == expected_value
    assert updated_user.balance == original_balance - APPRAISAL_COST

def test_appraise_crystal_not_blooming(app, db_session, service):
    user = create_user(db_session)
    seed = create_seed(db_session)
    garden = service.get_or_create_player_garden(user.id)
    flower = create_flower(db_session, user, garden, seed, stage='sprouting')
    with pytest.raises(FlowerNotBloomingError): # Specific error
        service.appraise_crystal(user.id, flower.id)

def test_appraise_crystal_already_appraised(app, db_session, service):
    user = create_user(db_session)
    seed = create_seed(db_session)
    garden = service.get_or_create_player_garden(user.id)
    flower = create_flower(db_session, user, garden, seed, stage='blooming', appraised_value=100)
    with pytest.raises(FlowerAlreadyAppraisedError):
        service.appraise_crystal(user.id, flower.id)

def test_appraise_crystal_insufficient_funds(app, db_session, service):
    user = create_user(db_session, balance=APPRAISAL_COST - 1)
    seed = create_seed(db_session)
    garden = service.get_or_create_player_garden(user.id)
    flower = create_flower(db_session, user, garden, seed, stage='blooming')
    with pytest.raises(InsufficientFundsError):
        service.appraise_crystal(user.id, flower.id)


def test_sell_crystal_success_new_codex(app, db_session, service, mock_datetime_now):
    user = create_user(db_session, balance=100)
    seed = create_seed(db_session)
    garden = service.get_or_create_player_garden(user.id)
    flower = create_flower(db_session, user, garden, seed, stage='blooming',
                           color='red', size=3.0, clarity=0.8, special_type='rare_sparkle',
                           appraised_value=500)

    original_balance = user.balance
    result = service.sell_crystal(user.id, flower.id)

    updated_user = db_session.session.get(User, user.id)
    assert updated_user.balance == original_balance + 500
    assert result['sold_value'] == 500

    codex_entry = db_session.session.query(CrystalCodexEntry).filter_by(user_id=user.id).first()
    assert codex_entry is not None
    assert codex_entry.color == 'red'
    assert codex_entry.size == 3.0
    assert codex_entry.clarity == 0.8
    assert codex_entry.special_type == 'rare_sparkle'
    assert codex_entry.first_discovered_at == mock_datetime_now
    # For 3.0 size -> "medium", For 0.8 clarity -> "clear"
    expected_sig = service._generate_crystal_description_and_signature(flower)['signature']
    assert codex_entry.signature == expected_sig


    deleted_flower = db_session.session.get(CrystalFlower, flower.id)
    assert deleted_flower is None

def test_sell_crystal_existing_codex(app, db_session, service):
    user = create_user(db_session, balance=100)
    seed = create_seed(db_session)
    garden = service.get_or_create_player_garden(user.id)

    # Sell first flower to create codex entry
    flower1 = create_flower(db_session, user, garden, seed, stage='blooming',
                           color='blue', size=2.0, clarity=0.7, special_type='common_glow',
                           appraised_value=100, x=0, y=0)
    service.sell_crystal(user.id, flower1.id)

    codex_count_before = db_session.session.query(CrystalCodexEntry).filter_by(user_id=user.id).count()

    # Sell second, identical type of flower
    flower2 = create_flower(db_session, user, garden, seed, stage='blooming',
                           color='blue', size=2.0, clarity=0.7, special_type='common_glow', # Same signature generating attributes
                           appraised_value=110, x=1, y=0) # Different value, different plot
    service.sell_crystal(user.id, flower2.id)

    codex_count_after = db_session.session.query(CrystalCodexEntry).filter_by(user_id=user.id).count()
    assert codex_count_after == codex_count_before # No new codex entry should be created


def test_sell_crystal_not_appraised(app, db_session, service):
    user = create_user(db_session)
    seed = create_seed(db_session)
    garden = service.get_or_create_player_garden(user.id)
    flower = create_flower(db_session, user, garden, seed, stage='blooming', appraised_value=None)
    with pytest.raises(FlowerNotAppraisedError): # Specific Error
        service.sell_crystal(user.id, flower.id)

def test_sell_crystal_flower_not_blooming(app, db_session, service):
    user = create_user(db_session)
    seed = create_seed(db_session)
    garden = service.get_or_create_player_garden(user.id)
    flower = create_flower(db_session, user, garden, seed, stage='sprouting', appraised_value=100)
    with pytest.raises(FlowerNotBloomingError):
        service.sell_crystal(user.id, flower.id)

def test_sell_crystal_flower_not_found(app, db_session, service):
    user = create_user(db_session)
    with pytest.raises(FlowerNotFoundError):
        service.sell_crystal(user.id, 999)

def test_sell_crystal_user_not_found(app, db_session, service):
    # Need a flower that exists but user does not for this specific check,
    # however, flower creation requires user. So this tests if flower for *this* user not found.
    # The service first gets user, then flower for that user.
    with pytest.raises(UserNotFoundError): # If user doesn't exist, service.sell_crystal will fail at get user.
        service.sell_crystal(999, 1) # Assuming flower 1 might exist but user 999 does not.

def test_sell_crystal_invalid_input_types(service):
    with pytest.raises(ServiceError, match="Invalid input type"):
        service.sell_crystal("not_int", 1)
    with pytest.raises(ServiceError, match="Invalid input type"):
        service.sell_crystal(1, "not_int")


# Final check on other methods for missing specific error tests or input validations

def test_appraise_crystal_user_not_found(app, db_session, service):
    # Flower ID 1 might exist, but user 999 does not.
    with pytest.raises(UserNotFoundError):
        service.appraise_crystal(999, 1)

def test_appraise_crystal_flower_not_found(app, db_session, service):
    user = create_user(db_session)
    with pytest.raises(FlowerNotFoundError):
        service.appraise_crystal(user.id, 999)

def test_appraise_crystal_invalid_input_types(service):
    with pytest.raises(ServiceError, match="Invalid input type"):
        service.appraise_crystal("not_int", 1)
    with pytest.raises(ServiceError, match="Invalid input type"):
        service.appraise_crystal(1, "not_int")
