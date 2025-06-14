import pytest
from flask import Flask
from casino_be.models import db as actual_db, User, CrystalSeed, PlayerGarden, CrystalFlower, CrystalCodexEntry
from casino_be.services.crystal_garden_service import (
    CrystalGardenService,
    InsufficientFundsError,
    PlotOccupiedError,
    InvalidPlotError,
    ItemNotFoundError,
    InvalidActionError, # Added from service file
    APPRAISAL_COST, # Import from service
    POWER_UP_COSTS # Import from service
)
from datetime import datetime, timezone

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
        outcomes = {
            "colors": {"blue": 0.5, "red": 0.3, "green": 0.2},
            "sizes": {"min": 1.0, "max": 5.0, "distribution": "uniform"},
            "clarities": {"min": 0.1, "max": 1.0, "distribution": "uniform"},
            "special_types": {"common": 0.9, "rare_sparkle": 0.1} # Ensure 'none' isn't the only option if used in tests
        }
    seed = CrystalSeed(id=id_val, name=f"{name} {id_val}", cost=cost, potential_outcomes=outcomes)
    session.session.add(seed)
    session.session.commit()
    return seed

# Helper to create a flower (basic)
def create_flower(session, user_obj, garden_obj, seed_obj, x=0, y=0, stage='seeded'):
    flower = CrystalFlower(
        user_id=user_obj.id,
        crystal_seed_id=seed_obj.id,
        player_garden_id=garden_obj.id,
        position_x=x,
        position_y=y,
        growth_stage=stage,
        planted_at=datetime.now(timezone.utc),
        active_power_ups=[]
    )
    session.session.add(flower)
    session.session.commit()
    return flower

# --- Test Cases ---

def test_get_or_create_player_garden(app, db_session, service):
    user = create_user(db_session)

    garden = service.get_or_create_player_garden(user.id)
    assert garden is not None
    assert garden.user_id == user.id
    assert garden.grid_size_x == 5
    assert garden.grid_size_y == 5

    garden2 = service.get_or_create_player_garden(user.id)
    assert garden2.id == garden.id

def test_get_or_create_player_garden_user_not_found(app, db_session, service):
    with pytest.raises(ItemNotFoundError): # Service raises this if user not found
        service.get_or_create_player_garden(999)

def test_buy_seed_success(app, db_session, service):
    user = create_user(db_session, balance=200)
    seed = create_seed(db_session, cost=100)

    purchased_seed = service.buy_seed(user.id, seed.id)
    assert purchased_seed is not None
    assert purchased_seed.id == seed.id
    db_session.session.refresh(user)
    assert user.balance == 100

def test_buy_seed_insufficient_funds(app, db_session, service):
    user = create_user(db_session, balance=50)
    seed = create_seed(db_session, cost=100)

    with pytest.raises(InsufficientFundsError):
        service.buy_seed(user.id, seed.id)
    db_session.session.refresh(user)
    assert user.balance == 50

def test_buy_seed_user_not_found(app, db_session, service):
    seed = create_seed(db_session)
    with pytest.raises(ItemNotFoundError):
        service.buy_seed(999, seed.id)

def test_buy_seed_seed_not_found(app, db_session, service):
    user = create_user(db_session)
    with pytest.raises(ItemNotFoundError):
        service.buy_seed(user.id, 999)

def test_plant_seed_success(app, db_session, service):
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

    db_flower = db_session.session.get(CrystalFlower, flower.id)
    assert db_flower is not None

def test_plant_seed_plot_occupied(app, db_session, service):
    user = create_user(db_session)
    seed = create_seed(db_session)
    service.get_or_create_player_garden(user.id)

    service.plant_seed(user.id, seed.id, 0, 0)
    with pytest.raises(PlotOccupiedError):
        service.plant_seed(user.id, seed.id, 0, 0)

def test_plant_seed_invalid_plot(app, db_session, service):
    user = create_user(db_session)
    seed = create_seed(db_session)
    garden = service.get_or_create_player_garden(user.id)

    with pytest.raises(InvalidPlotError): # Plot outside 0 to grid_size-1
        service.plant_seed(user.id, seed.id, garden.grid_size_x, garden.grid_size_y)

def test_get_garden_state(app, db_session, service):
    user = create_user(db_session)
    seed = create_seed(db_session)
    garden = service.get_or_create_player_garden(user.id)
    flower_obj = service.plant_seed(user.id, seed.id, 0, 0)

    state = service.get_garden_state(user.id)
    assert state is not None
    assert state['garden_id'] == garden.id
    assert state['user_id'] == user.id
    assert len(state['flowers']) == 1
    assert state['flowers'][0]['id'] == flower_obj.id
    assert state['flowers'][0]['position_x'] == 0

def test_get_garden_state_no_garden_yet(app, db_session, service):
    user = create_user(db_session) # User exists, but no garden interaction yet
    # The service's get_garden_state calls get_or_create_player_garden
    state = service.get_garden_state(user.id)
    assert state is not None
    assert state['garden_id'] is not None # Garden is created
    assert state['user_id'] == user.id
    assert len(state['flowers']) == 0


def test_get_player_codex_empty(app, db_session, service):
    user = create_user(db_session)
    codex_entries = service.get_player_codex(user.id)
    assert isinstance(codex_entries, list)
    assert len(codex_entries) == 0

def test_apply_power_up_success(app, db_session, service):
    user = create_user(db_session, balance=100)
    seed = create_seed(db_session)
    garden = service.get_or_create_player_garden(user.id)
    flower = create_flower(db_session, user, garden, seed)

    power_up_type = 'fertilizer' # Assumes 'fertilizer' is in POWER_UP_COSTS
    cost = POWER_UP_COSTS[power_up_type]

    updated_flower = service.apply_power_up(user.id, flower.id, power_up_type)
    db_session.session.refresh(user)
    db_session.session.refresh(updated_flower)

    assert power_up_type in updated_flower.active_power_ups
    assert user.balance == 100 - cost

def test_process_growth_cycle(app, db_session, service, mocker):
    user = create_user(db_session)
    outcomes = {
        "colors": {"blue": 1.0}, "sizes": {"min": 2.0, "max": 2.0, "distribution": "uniform"},
        "clarities": {"min": 0.5, "max": 0.5, "distribution": "uniform"},
        "special_types": {"test_special": 1.0}
    }
    seed = create_seed(db_session, outcomes=outcomes)
    garden = service.get_or_create_player_garden(user.id)
    flower = service.plant_seed(user.id, seed.id, 0, 0)

    # Mock random functions used by _randomize_attribute
    mocker.patch('random.choices', side_effect=lambda choices, weights, k: [choices[0]]) # Pick first choice
    mocker.patch('random.uniform', side_effect=lambda a, b: a) # Pick min value

    # Seeded to Sprouting
    report1 = service.process_growth_cycle(garden.id)
    db_session.session.refresh(flower)
    assert flower.growth_stage == 'sprouting'
    assert report1['updated_flowers'] == 1

    # Sprouting to Blooming
    report2 = service.process_growth_cycle(garden.id)
    db_session.session.refresh(flower)
    assert flower.growth_stage == 'blooming'
    assert report2['newly_bloomed'] == 1
    assert flower.color == 'blue' # From mocked random.choices
    assert flower.size == 2.0     # From mocked random.uniform
    assert flower.clarity == 0.5  # From mocked random.uniform
    assert flower.special_type == 'test_special'

    db_session.session.refresh(garden)
    assert garden.last_cycle_time is not None

def test_appraise_crystal_success(app, db_session, service):
    user = create_user(db_session, balance=100)
    seed = create_seed(db_session)
    garden = service.get_or_create_player_garden(user.id)
    flower = create_flower(db_session, user, garden, seed, stage='blooming')
    flower.color = 'blue'; flower.size = 2.0; flower.clarity = 0.5; flower.special_type = 'common' # common is not in map, gets 0
    db_session.session.commit()

    original_balance = user.balance
    appraised_flower = service.appraise_crystal(user.id, flower.id)

    db_session.session.refresh(user)
    db_session.session.refresh(appraised_flower)

    expected_value = (2.0 * 10) + (0.5 * 20) + 10 + 0 # size*10 + clarity*20 + blue_value + common_value(0)
    assert appraised_flower.appraised_value == int(expected_value)
    assert user.balance == original_balance - APPRAISAL_COST

def test_appraise_crystal_not_blooming(app, db_session, service):
    user = create_user(db_session)
    seed = create_seed(db_session)
    garden = service.get_or_create_player_garden(user.id)
    flower = create_flower(db_session, user, garden, seed, stage='sprouting')
    with pytest.raises(InvalidActionError):
        service.appraise_crystal(user.id, flower.id)

def test_sell_crystal_success(app, db_session, service):
    user = create_user(db_session, balance=100)
    seed = create_seed(db_session)
    garden = service.get_or_create_player_garden(user.id)
    flower = create_flower(db_session, user, garden, seed, stage='blooming')
    flower.color = 'red'; flower.size = 3.0; flower.clarity = 0.8; flower.special_type = 'rare_sparkle'
    flower.appraised_value = 500
    db_session.session.commit()

    original_balance = user.balance
    result = service.sell_crystal(user.id, flower.id)

    db_session.session.refresh(user)
    assert user.balance == original_balance + 500
    assert result['sold_value'] == 500

    codex_entry = db_session.session.query(CrystalCodexEntry).filter_by(user_id=user.id).first()
    assert codex_entry is not None
    assert codex_entry.color == 'red'
    assert codex_entry.size == 3.0

    deleted_flower = db_session.session.get(CrystalFlower, flower.id)
    assert deleted_flower is None

def test_sell_crystal_not_appraised(app, db_session, service):
    user = create_user(db_session)
    seed = create_seed(db_session)
    garden = service.get_or_create_player_garden(user.id)
    flower = create_flower(db_session, user, garden, seed, stage='blooming')
    # flower.appraised_value is None
    with pytest.raises(InvalidActionError):
        service.sell_crystal(user.id, flower.id)
