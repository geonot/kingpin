from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, current_user
from datetime import datetime, timezone
# import random # No longer needed directly in routes

# Removed direct model imports for business logic, keep User for current_user if needed
# from casino_be.models import db, User, AstroMinerXExpedition, AstroMinerXAsteroid, AstroMinerXResource, Transaction
from casino_be.models import User # For current_user type hinting if strict
from casino_be.schemas import AstroMinerXExpeditionSchema, AstroMinerXAsteroidSchema, AstroMinerXResourceSchema, UserSchema
from casino_be.exceptions import NotFoundException, ValidationException, InsufficientFundsException, GameLogicException
from casino_be.error_codes import ErrorCodes
from casino_be.services import astrominerx_service # Import the service module

astrominerx_bp = Blueprint('astrominerx', __name__, url_prefix='/api/astrominerx')


# --- API Endpoints ---

@astrominerx_bp.route('/launch', methods=['POST'])
@jwt_required()
def launch_expedition_route():
    data = request.get_json()
    if not data or 'bet_amount' not in data:
        raise ValidationException(ErrorCodes.VALIDATION_ERROR, "Missing bet_amount in request body.")

    bet_amount = data.get('bet_amount')

    # Service function will handle validation of bet_amount type and value, and user balance
    expedition, initial_asteroids, new_balance = astrominerx_service.launch_expedition_service(
        user=current_user,
        bet_amount=bet_amount
    )

    expedition_schema = AstroMinerXExpeditionSchema()
    # initial_asteroids from service are already committed model instances
    # The schema for asteroids for the launch response might only need basic info (e.g., id, placeholder_type)
    # For now, using the full schema, but this can be optimized.
    asteroid_schema = AstroMinerXAsteroidSchema(many=True)

    return jsonify({
        "status": True,
        "message": "AstroMiner X expedition launched!",
        "expedition": expedition_schema.dump(expedition),
        "initial_asteroids": asteroid_schema.dump(initial_asteroids),
        "user_balance": new_balance
    }), 201

@astrominerx_bp.route('/scan', methods=['POST'])
@jwt_required()
def scan_asteroid_route():
    data = request.get_json()
    if not data or 'expedition_id' not in data or 'asteroid_id' not in data:
        raise ValidationException(ErrorCodes.VALIDATION_ERROR, "Missing expedition_id or asteroid_id in request body.")

    expedition_id = data.get('expedition_id')
    asteroid_id = data.get('asteroid_id')

    # Retrieve the expedition first (service might also do this, but good to check ownership early)
    expedition = astrominerx_service.get_expedition_state_service(expedition_id, current_user)
    # get_expedition_state_service will raise NotFoundException if not found or not user's

    # Service function will handle actual scan logic
    scanned_asteroid, event_details, new_balance = astrominerx_service.scan_asteroid_service(
        expedition=expedition,
        asteroid_id=asteroid_id
    )

    asteroid_schema = AstroMinerXAsteroidSchema()
    response_data = {
        "status": True,
        "scan_result": asteroid_schema.dump(scanned_asteroid),
        "user_balance": new_balance # Assumes scan_asteroid_service returns updated balance
    }
    if event_details:
        response_data["event_details"] = event_details

    return jsonify(response_data), 200


@astrominerx_bp.route('/collect', methods=['POST'])
@jwt_required()
def collect_resources_route():
    data = request.get_json()
    if not data or 'expedition_id' not in data:
        raise ValidationException(ErrorCodes.VALIDATION_ERROR, "Missing expedition_id in request body.")

    expedition_id = data.get('expedition_id')

    # Retrieve the expedition
    expedition = astrominerx_service.get_expedition_state_service(expedition_id, current_user)

    # Service function will handle collection logic
    final_expedition, collected_resources, new_balance = astrominerx_service.collect_resources_service(
        expedition=expedition
    )

    expedition_schema = AstroMinerXExpeditionSchema()
    resource_schema = AstroMinerXResourceSchema(many=True)

    return jsonify({
        "status": True,
        "message": "Expedition completed and resources collected!",
        "expedition_summary": expedition_schema.dump(final_expedition),
        "collected_resources_detail": resource_schema.dump(collected_resources), # Changed key for clarity
        "user_balance": new_balance
    }), 200

@astrominerx_bp.route('/expedition/<int:expedition_id>', methods=['GET'])
@jwt_required()
def get_expedition_status_route(expedition_id):
    # Service function handles fetching and permission check
    expedition = astrominerx_service.get_expedition_state_service(expedition_id, current_user)

    expedition_schema = AstroMinerXExpeditionSchema()
    # Schemas for asteroids and resources are nested in AstroMinerXExpeditionSchema now
    # and will be included if the relationships are loaded by the service.

    return jsonify({
        "status": True,
        "expedition": expedition_schema.dump(expedition)
    }), 200


# Removed placeholder schemas and TODOs for schema/error code moving, as they are now in their respective files.
# Remaining TODOs for game logic refinement, logging, etc., are still valid for future iterations.
