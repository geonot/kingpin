from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, current_user
from datetime import datetime, timezone

from ..models import db, GameSession, BlackjackTable, BaccaratTable, PokerTable # Relative import
from ..schemas import BlackjackTableSchema, BaccaratTableSchema, PokerTableSchema # Relative import

meta_game_bp = Blueprint('meta_game', __name__, url_prefix='/api')

@meta_game_bp.route('/end_session', methods=['POST'])
@jwt_required()
def end_session():
    user_id = current_user.id
    now = datetime.now(timezone.utc)
    try:
        active_sessions = GameSession.query.filter_by(user_id=user_id, session_end=None).all()
        if not active_sessions:
            return jsonify({'status': True, 'status_message': 'No active session to end'}), 200

        for session in active_sessions:
            session.session_end = now

        db.session.commit()
        current_app.logger.info(f"Ended active sessions for user {user_id}")
        return jsonify({'status': True, 'status_message': 'Session ended successfully'}), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Failed to end session: {str(e)}", exc_info=True)
        return jsonify({'status': False, 'status_message': 'Failed to end session.'}), 500

@meta_game_bp.route('/tables', methods=['GET'])
@jwt_required()
def get_all_tables():
    """Get all active tables across all game types"""
    try:
        # Get all active tables from different games
        blackjack_tables = BlackjackTable.query.filter_by(is_active=True).order_by(BlackjackTable.id).all()
        baccarat_tables = BaccaratTable.query.filter_by(is_active=True).order_by(BaccaratTable.id).all()
        poker_tables = PokerTable.query.filter_by(is_active=True).order_by(PokerTable.id).all()
        
        # Serialize tables with their game type
        tables = []
        
        # Add blackjack tables
        for table in blackjack_tables:
            table_data = BlackjackTableSchema().dump(table)
            table_data['game_type'] = 'blackjack'
            tables.append(table_data)
        
        # Add baccarat tables
        for table in baccarat_tables:
            table_data = BaccaratTableSchema().dump(table)
            table_data['game_type'] = 'baccarat'
            tables.append(table_data)
            
        # Add poker tables
        for table in poker_tables:
            table_data = PokerTableSchema().dump(table)
            table_data['game_type'] = 'poker'
            tables.append(table_data)
        
        return jsonify({'status': True, 'tables': tables}), 200
    except Exception as e:
        current_app.logger.error(f"Failed to retrieve tables list: {str(e)}", exc_info=True)
        return jsonify({'status': False, 'status_message': 'Could not retrieve table information.'}), 500
