from flask import Blueprint, request, jsonify, current_app # Added current_app for logging if needed
from flask_jwt_extended import jwt_required, current_user

# models import was missing from the previous read, but error trace shows it's needed
from casino_be.models import db, User, CrystalSeed, PlayerGarden, CrystalFlower, CrystalCodexEntry # Ensure all needed models are here
from casino_be.services.crystal_garden_service import CrystalGardenService, ServiceError, ItemNotFoundError
from casino_be.utils.decorators import feature_flag_required

crystal_garden_bp = Blueprint('crystal_garden_bp', __name__, url_prefix='/api/crystal-garden')
service = CrystalGardenService()

# Helper to convert ServiceError to a JSON response
# This is needed because the ServiceError class itself might not have a to_dict() method
# that Flask's jsonify can directly use.
def jsonify_service_error(error: ServiceError):
    return jsonify({'message': str(error)}), error.status_code

@crystal_garden_bp.errorhandler(ServiceError)
def handle_service_error(error: ServiceError):
    # Log the error if needed: current_app.logger.error(f"ServiceError: {str(error)}")
    return jsonify_service_error(error)


@crystal_garden_bp.route('/buy-seed', methods=['POST'])
@jwt_required()
@feature_flag_required('CRYSTAL_GARDEN_ENABLED')
def buy_seed_route(): # Renamed to avoid conflict with service method name
    data = request.get_json()
    if not data or 'seed_id' not in data:
        return jsonify({'message': 'Seed ID is required'}), 400

    try:
        seed_id = int(data['seed_id'])
        seed = service.buy_seed(user_id=current_user.id, seed_id=seed_id)
        # Fetch user again to get updated balance, or service could return it
        updated_user = db.session.get(type(current_user), current_user.id)
        return jsonify({
            'message': 'Seed purchased successfully',
            'seed': seed.to_dict() if seed else None, # Assuming to_dict on CrystalSeed
            'new_balance': updated_user.balance
        }), 200
    except ServiceError as e:
        return handle_service_error(e)
    except ValueError:
        return jsonify({'message': 'Invalid Seed ID format'}), 400
    except Exception as e:
        # Log e
        return jsonify({'message': 'An unexpected error occurred purchasing seed.'}), 500


@crystal_garden_bp.route('/plant-seed', methods=['POST'])
@jwt_required()
@feature_flag_required('CRYSTAL_GARDEN_ENABLED')
def plant_seed_route(): # Renamed
    data = request.get_json()
    required_fields = ['seed_id', 'position_x', 'position_y']
    if not data or not all(field in data for field in required_fields):
        return jsonify({'message': 'Missing required fields: seed_id, position_x, position_y'}), 400

    try:
        seed_id = int(data['seed_id'])
        position_x = int(data['position_x'])
        position_y = int(data['position_y'])

        flower = service.plant_seed(user_id=current_user.id,
                                    seed_id=seed_id,
                                    garden_plot_x=position_x,
                                    garden_plot_y=position_y)
        return jsonify({
            'message': 'Seed planted successfully',
            'flower': flower.to_dict() if flower else None # Assuming to_dict on CrystalFlower
        }), 201
    except ServiceError as e:
        return handle_service_error(e)
    except ValueError:
        return jsonify({'message': 'Invalid data format for seed_id, position_x, or position_y'}), 400
    except Exception as e:
        # Log e
        return jsonify({'message': 'An unexpected error occurred planting seed.'}), 500

@crystal_garden_bp.route('/garden-state', methods=['GET'])
@jwt_required()
@feature_flag_required('CRYSTAL_GARDEN_ENABLED')
def get_garden_state_route(): # Renamed
    try:
        garden_state = service.get_garden_state(user_id=current_user.id)
        return jsonify(garden_state), 200
    except ServiceError as e:
        return handle_service_error(e)
    except Exception as e:
        # Log e
        return jsonify({'message': 'An unexpected error occurred fetching garden state.'}), 500

@crystal_garden_bp.route('/codex', methods=['GET'])
@jwt_required()
@feature_flag_required('CRYSTAL_GARDEN_ENABLED')
def get_codex_route(): # Renamed
    try:
        codex_entries = service.get_player_codex(user_id=current_user.id)
        return jsonify([entry.to_dict() for entry in codex_entries]), 200
    except ServiceError as e:
        return handle_service_error(e)
    except Exception as e:
        # Log e
        return jsonify({'message': 'An unexpected error occurred fetching codex.'}), 500

@crystal_garden_bp.route('/activate-powerup', methods=['POST'])
@jwt_required()
@feature_flag_required('CRYSTAL_GARDEN_ENABLED')
def activate_powerup_route(): # Renamed
    data = request.get_json()
    required_fields = ['flower_id', 'power_up_type']
    if not data or not all(field in data for field in required_fields):
        return jsonify({'message': 'Missing required fields: flower_id, power_up_type'}), 400

    try:
        flower_id = int(data['flower_id'])
        power_up_type = str(data['power_up_type'])

        flower = service.apply_power_up(user_id=current_user.id,
                                        flower_id=flower_id,
                                        power_up_type=power_up_type)
        return jsonify({
            'message': 'Power-up activated',
            'flower': flower.to_dict() if flower else None, # Assuming to_dict
            'new_balance': current_user.balance
        }), 200
    except ServiceError as e:
        return handle_service_error(e)
    except ValueError:
        return jsonify({'message': 'Invalid flower_id format'}), 400
    except Exception as e:
        # Log e
        return jsonify({'message': 'An unexpected error occurred activating power-up.'}), 500

@crystal_garden_bp.route('/appraise-crystal', methods=['POST'])
@jwt_required()
@feature_flag_required('CRYSTAL_GARDEN_ENABLED')
def appraise_crystal_route(): # Renamed
    data = request.get_json()
    if not data or 'flower_id' not in data:
        return jsonify({'message': 'Flower ID is required'}), 400

    try:
        flower_id = int(data['flower_id'])
        flower = service.appraise_crystal(user_id=current_user.id, flower_id=flower_id)
        return jsonify({
            'message': 'Crystal appraised',
            'flower': flower.to_dict() if flower else None, # Assuming to_dict
            'new_balance': current_user.balance
        }), 200
    except ServiceError as e:
        return handle_service_error(e)
    except ValueError:
        return jsonify({'message': 'Invalid flower_id format'}), 400
    except Exception as e:
        # Log e
        return jsonify({'message': 'An unexpected error occurred appraising crystal.'}), 500

@crystal_garden_bp.route('/sell-crystal', methods=['POST'])
@jwt_required()
@feature_flag_required('CRYSTAL_GARDEN_ENABLED')
def sell_crystal_route(): # Renamed
    data = request.get_json()
    if not data or 'flower_id' not in data:
        return jsonify({'message': 'Flower ID is required'}), 400

    try:
        flower_id = int(data['flower_id'])
        result = service.sell_crystal(user_id=current_user.id, flower_id=flower_id)
        updated_user = db.session.get(type(current_user), current_user.id)
        return jsonify({
            'message': 'Crystal sold successfully',
            'details': result,
            'new_balance': updated_user.balance
        }), 200
    except ServiceError as e:
        return handle_service_error(e)
    except ValueError:
        return jsonify({'message': 'Invalid flower_id format'}), 400
    except Exception as e:
        # Log e
        return jsonify({'message': 'An unexpected error occurred selling crystal.'}), 500

@crystal_garden_bp.route('/process-cycle', methods=['POST'])
@jwt_required()
@feature_flag_required('CRYSTAL_GARDEN_ENABLED')
# Potentially an admin-only or rate-limited endpoint in a real scenario
def process_cycle_route(): # Renamed
    try:
        # The service should get the garden associated with current_user.id
        player_garden = service.get_or_create_player_garden(user_id=current_user.id)
        if not player_garden:
             # This case should ideally be handled by get_or_create_player_garden raising an error if user not found
            raise ItemNotFoundError(f"Garden for user {current_user.id} not found and could not be created.")

        report = service.process_growth_cycle(garden_id=player_garden.id)
        return jsonify({'message': 'Growth cycle processed for your garden', 'report': report}), 200
    except ServiceError as e:
        return handle_service_error(e)
    except Exception as e:
        # Log e
        return jsonify({'message': 'An unexpected error occurred processing cycle.'}), 500
