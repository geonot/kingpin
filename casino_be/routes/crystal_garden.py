from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required, current_user # Assuming flask_login for current_user
import logging

from casino_be.models import db # For db session if service doesn't handle all commits
from casino_be.services.crystal_garden_service import (
    CrystalGardenService, ServiceError, ItemNotFoundError, UserNotFoundError,
    SeedNotFoundError, FlowerNotFoundError, GardenNotFoundError, InsufficientFundsError,
    PlotOccupiedError, InvalidPlotError, GardenPlotOutOfBoundsError, InvalidActionError,
    PowerUpNotFoundError, FlowerNotBloomingError, FlowerAlreadyAppraisedError,
    FlowerNotAppraisedError, DatabaseError
)
from casino_be.utils.decorators import feature_flag_required

logger = logging.getLogger(__name__)
crystal_garden_bp = Blueprint('crystal_garden_bp', __name__, url_prefix='/api/crystal-garden')
service = CrystalGardenService()


@crystal_garden_bp.errorhandler(ServiceError)
def handle_service_error(error: ServiceError):
    error_payload = {
        'message': str(error),
        'error_code': error.error_code if hasattr(error, 'error_code') and error.error_code else "UNKNOWN_SERVICE_ERROR"
    }
    # Log full error details for service errors
    logger.error(f"ServiceError caught in route: {error.__class__.__name__} - Code: {error_payload['error_code']} - Msg: {str(error)} - Path: {request.path}", exc_info=True if error.status_code >= 500 else False)
    return jsonify({'error': error_payload}), error.status_code

@crystal_garden_bp.errorhandler(Exception)
def handle_generic_exception(error: Exception):
    # Log any other unhandled exceptions
    logger.error(f"Unhandled exception caught in route: {error.__class__.__name__} - Msg: {str(error)} - Path: {request.path}", exc_info=True)
    return jsonify({'error': {'message': 'An unexpected internal server error occurred.', 'error_code': 'INTERNAL_SERVER_ERROR'}}), 500


@crystal_garden_bp.route('/buy-seed', methods=['POST'])
@login_required
@feature_flag_required('CRYSTAL_GARDEN_ENABLED')
def buy_seed_route(): # Renamed to avoid conflict with service method name
    data = request.get_json()
    logger.info(f"Buy seed request for user {current_user.id}: {data}")
    if not data or 'seed_id' not in data:
        logger.warning(f"Missing seed_id in request from user {current_user.id}")
        return jsonify({'error': {'message': 'Seed ID is required', 'error_code': 'MISSING_FIELD_SEED_ID'}}), 400

    try:
        seed_id = int(data['seed_id'])
        if seed_id <= 0:
             raise ValueError("Seed ID must be positive.")
        seed = service.buy_seed(user_id=current_user.id, seed_id=seed_id)
        # User object in current_user might be stale regarding balance. Refetch.
        # Alternatively, service could return new balance.
        updated_user = db.session.get(type(current_user._get_current_object()), current_user.id)

        logger.info(f"Seed {seed_id} purchased successfully by user {current_user.id}")
        return jsonify({
            'message': 'Seed purchased successfully',
            'data': {
                'seed': seed.to_dict(),
                'new_balance': updated_user.balance
            }
        }), 200
    except ValueError as ve:
        logger.warning(f"Invalid Seed ID format for user {current_user.id}: {data.get('seed_id')}. Error: {ve}", exc_info=True)
        return jsonify({'error': {'message': f'Invalid Seed ID format: {ve}', 'error_code': 'INVALID_SEED_ID_FORMAT'}}), 400
    # ServiceError is handled by the blueprint error handler
    # Generic Exception is handled by the blueprint error handler


@crystal_garden_bp.route('/plant-seed', methods=['POST'])
@login_required
@feature_flag_required('CRYSTAL_GARDEN_ENABLED')
def plant_seed_route(): # Renamed
    data = request.get_json()
    logger.info(f"Plant seed request for user {current_user.id}: {data}")
    required_fields = ['seed_id', 'position_x', 'position_y']
    if not data or not all(field in data for field in required_fields):
        missing = [field for field in required_fields if field not in data]
        logger.warning(f"Missing fields {missing} in plant seed request from user {current_user.id}")
        return jsonify({'error': {'message': f'Missing required fields: {", ".join(missing)}', 'error_code': 'MISSING_FIELDS'}}), 400

    try:
        seed_id = int(data['seed_id'])
        position_x = int(data['position_x'])
        position_y = int(data['position_y'])
        if seed_id <= 0: raise ValueError("Seed ID must be positive.")
        # Position validation (e.g. non-negative) could be here or rely on service layer's boundary check
        if position_x < 0 or position_y < 0: raise ValueError("Position coordinates must be non-negative.")


        flower = service.plant_seed(user_id=current_user.id,
                                    seed_id=seed_id,
                                    garden_plot_x=position_x,
                                    garden_plot_y=position_y)
        logger.info(f"Seed {seed_id} planted successfully by user {current_user.id} at ({position_x},{position_y}). Flower ID: {flower.id}")
        return jsonify({
            'message': 'Seed planted successfully',
            'data': {'flower': flower.to_dict()}
        }), 201
    except ValueError as ve:
        logger.warning(f"Invalid data format in plant seed request for user {current_user.id}. Data: {data}. Error: {ve}", exc_info=True)
        return jsonify({'error': {'message': f'Invalid data format: {ve}', 'error_code': 'INVALID_DATA_FORMAT'}}), 400
    # ServiceError is handled by the blueprint error handler
    # Generic Exception is handled by the blueprint error handler

@crystal_garden_bp.route('/garden-state', methods=['GET'])
@login_required
@feature_flag_required('CRYSTAL_GARDEN_ENABLED')
def get_garden_state_route(): # Renamed
    logger.info(f"Garden state request for user {current_user.id}")
    # try/except for ServiceError and general Exception handled by blueprint error handlers
    garden_state = service.get_garden_state(user_id=current_user.id)
    logger.info(f"Garden state retrieved for user {current_user.id}")
    return jsonify({'data': garden_state}), 200

@crystal_garden_bp.route('/codex', methods=['GET'])
@login_required
@feature_flag_required('CRYSTAL_GARDEN_ENABLED')
def get_codex_route(): # Renamed
    logger.info(f"Codex request for user {current_user.id}")
    codex_entries = service.get_player_codex(user_id=current_user.id)
    logger.info(f"Codex entries ({len(codex_entries)}) retrieved for user {current_user.id}")
    return jsonify({'data': [entry.to_dict() for entry in codex_entries]}), 200

@crystal_garden_bp.route('/activate-powerup', methods=['POST'])
@login_required
@feature_flag_required('CRYSTAL_GARDEN_ENABLED')
def activate_powerup_route(): # Renamed
    data = request.get_json()
    logger.info(f"Activate power-up request for user {current_user.id}: {data}")
    required_fields = ['flower_id', 'power_up_type']
    if not data or not all(field in data for field in required_fields):
        missing = [field for field in required_fields if field not in data]
        logger.warning(f"Missing fields {missing} in activate powerup request from user {current_user.id}")
        return jsonify({'error': {'message': f'Missing required fields: {", ".join(missing)}', 'error_code': 'MISSING_FIELDS'}}), 400

    try:
        flower_id = int(data['flower_id'])
        power_up_type = str(data['power_up_type']).strip() # Ensure it's a string and strip whitespace
        if flower_id <= 0: raise ValueError("Flower ID must be positive.")
        if not power_up_type: raise ValueError("Power-up type cannot be empty.")


        flower = service.apply_power_up(user_id=current_user.id,
                                        flower_id=flower_id,
                                        power_up_type=power_up_type)
        updated_user = db.session.get(type(current_user._get_current_object()), current_user.id)
        logger.info(f"Power-up '{power_up_type}' activated for flower {flower_id} by user {current_user.id}")
        return jsonify({
            'message': 'Power-up activated',
            'data': {
                'flower': flower.to_dict(),
                'new_balance': updated_user.balance
            }
        }), 200
    except ValueError as ve:
        logger.warning(f"Invalid data format in activate powerup request for user {current_user.id}. Data: {data}. Error: {ve}", exc_info=True)
        return jsonify({'error': {'message': f'Invalid data format: {ve}', 'error_code': 'INVALID_DATA_FORMAT'}}), 400
    # ServiceError is handled by the blueprint error handler
    # Generic Exception is handled by the blueprint error handler

@crystal_garden_bp.route('/appraise-crystal', methods=['POST'])
@login_required
@feature_flag_required('CRYSTAL_GARDEN_ENABLED')
def appraise_crystal_route(): # Renamed
    data = request.get_json()
    logger.info(f"Appraise crystal request for user {current_user.id}: {data}")
    if not data or 'flower_id' not in data:
        logger.warning(f"Missing flower_id in appraise request from user {current_user.id}")
        return jsonify({'error': {'message': 'Flower ID is required', 'error_code': 'MISSING_FIELD_FLOWER_ID'}}), 400

    try:
        flower_id = int(data['flower_id'])
        if flower_id <= 0: raise ValueError("Flower ID must be positive.")

        flower = service.appraise_crystal(user_id=current_user.id, flower_id=flower_id)
        updated_user = db.session.get(type(current_user._get_current_object()), current_user.id)
        logger.info(f"Crystal {flower_id} appraised for user {current_user.id}. Appraised value: {flower.appraised_value}")
        return jsonify({
            'message': 'Crystal appraised',
            'data':{
                'flower': flower.to_dict(),
                'new_balance': updated_user.balance
            }
        }), 200
    except ValueError as ve:
        logger.warning(f"Invalid flower_id format in appraise request for user {current_user.id}. Data: {data}. Error: {ve}", exc_info=True)
        return jsonify({'error': {'message': f'Invalid flower_id format: {ve}', 'error_code': 'INVALID_FLOWER_ID_FORMAT'}}), 400
    # ServiceError is handled by the blueprint error handler
    # Generic Exception is handled by the blueprint error handler

@crystal_garden_bp.route('/sell-crystal', methods=['POST'])
@login_required
@feature_flag_required('CRYSTAL_GARDEN_ENABLED')
def sell_crystal_route(): # Renamed
    data = request.get_json()
    logger.info(f"Sell crystal request for user {current_user.id}: {data}")
    if not data or 'flower_id' not in data:
        logger.warning(f"Missing flower_id in sell crystal request from user {current_user.id}")
        return jsonify({'error': {'message': 'Flower ID is required', 'error_code': 'MISSING_FIELD_FLOWER_ID'}}), 400

    try:
        flower_id = int(data['flower_id'])
        if flower_id <= 0: raise ValueError("Flower ID must be positive.")

        result = service.sell_crystal(user_id=current_user.id, flower_id=flower_id)
        updated_user = db.session.get(type(current_user._get_current_object()), current_user.id) # Refresh user for balance
        logger.info(f"Crystal {flower_id} sold by user {current_user.id}. Sold value: {result.get('sold_value')}")
        return jsonify({
            'message': result.get('message', 'Crystal sold successfully'), # Use message from service if available
            'data': {
                'sold_value': result.get('sold_value'),
                'new_balance': updated_user.balance
            }
        }), 200
    except ValueError as ve:
        logger.warning(f"Invalid flower_id format in sell crystal request for user {current_user.id}. Data: {data}. Error: {ve}", exc_info=True)
        return jsonify({'error': {'message': f'Invalid flower_id format: {ve}', 'error_code': 'INVALID_FLOWER_ID_FORMAT'}}), 400
    # ServiceError is handled by the blueprint error handler
    # Generic Exception is handled by the blueprint error handler

@crystal_garden_bp.route('/process-cycle', methods=['POST'])
@login_required
@feature_flag_required('CRYSTAL_GARDEN_ENABLED')
# Potentially an admin-only or rate-limited endpoint in a real scenario
def process_cycle_route(): # Renamed
    logger.info(f"Process cycle request for user {current_user.id}")
    # try/except for ServiceError and general Exception handled by blueprint error handlers
    player_garden = service.get_or_create_player_garden(user_id=current_user.id)
    # Service raises GardenNotFoundError if something goes wrong finding/creating garden for user

    report = service.process_growth_cycle(garden_id=player_garden.id)
    logger.info(f"Growth cycle processed for garden {player_garden.id} (user {current_user.id})")
    return jsonify({
        'message': 'Growth cycle processed for your garden',
        'data': {'report': report}
    }), 200
