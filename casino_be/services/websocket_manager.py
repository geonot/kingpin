"""
WebSocket Manager for Real-time Game Communications
Handles WebSocket connections for Spacecrash and Poker games
"""

from flask_socketio import SocketIO, emit, join_room, leave_room, disconnect
from flask_jwt_extended import decode_token, jwt_required, get_jwt_identity
from flask import current_app, request
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

class WebSocketManager:
    def __init__(self, app=None, socketio=None):
        self.socketio = socketio
        self.connected_users = {}  # user_id -> {socket_id, rooms}
        self.game_rooms = {
            'spacecrash': set(),  # Connected users for spacecrash
            'poker': {}  # table_id -> set of connected users
        }
        
        if app and socketio:
            self.init_app(app)
    
    def init_app(self, app):
        """Initialize WebSocket handlers"""
        self.socketio.on_event('connect', self.handle_connect)
        self.socketio.on_event('disconnect', self.handle_disconnect)
        self.socketio.on_event('join_room', self.handle_join_room)
        self.socketio.on_event('leave_room', self.handle_leave_room)
        
        # Legacy handlers for backward compatibility
        self.socketio.on_event('join_spacecrash', self.handle_join_spacecrash_legacy)
        self.socketio.on_event('leave_spacecrash', self.handle_leave_spacecrash_legacy)
        self.socketio.on_event('join_poker_table', self.handle_join_poker_table)
        self.socketio.on_event('leave_poker_table', self.handle_leave_poker_table)
    
    def authenticate_user(self, auth_token=None):
        """Authenticate user from JWT token or cookies"""
        try:
            # First try to get token from auth parameter (direct token)
            if auth_token:
                # Remove 'Bearer ' prefix if present
                if auth_token.startswith('Bearer '):
                    auth_token = auth_token[7:]
                
                # Decode the JWT token
                token_data = decode_token(auth_token)
                user_id = token_data.get('sub')
                
                if user_id:
                    return int(user_id)
            
            # If no direct token, try to get from cookies (HTTP-only cookies)
            # Flask-SocketIO should have access to cookies in the request context
            from flask import request
            access_token_cookie = request.cookies.get('access_token_cookie')
            
            if access_token_cookie:
                # Decode the JWT token from cookie
                token_data = decode_token(access_token_cookie)
                user_id = token_data.get('sub')
                
                if user_id:
                    return int(user_id)
            
            return None
        except Exception as e:
            logger.warning(f"WebSocket authentication failed: {str(e)}")
            return None
    
    def handle_connect(self, auth=None, namespace=None):
        """Handle WebSocket connection"""
        auth_token = request.args.get('token') or (auth.get('token') if auth else None)
        user_id = self.authenticate_user(auth_token)
        
        if not user_id:
            logger.warning(f"WebSocket connection refused - invalid authentication")
            disconnect()
            return False
        
        socket_id = request.sid
        self.connected_users[user_id] = {
            'socket_id': socket_id,
            'rooms': set(),
            'connected_at': datetime.now(timezone.utc)
        }
        
        logger.info(f"User {user_id} connected via WebSocket (socket: {socket_id})")
        emit('connection_status', {'status': 'connected', 'user_id': user_id})
        return True
    
    def handle_disconnect(self, namespace=None):
        """Handle WebSocket disconnection"""
        socket_id = request.sid
        user_id = None
        
        # Find user by socket_id
        for uid, data in self.connected_users.items():
            if data['socket_id'] == socket_id:
                user_id = uid
                break
        
        if user_id:
            # Remove from all game rooms
            user_data = self.connected_users[user_id]
            for room in user_data['rooms']:
                if room == 'spacecrash':
                    self.game_rooms['spacecrash'].discard(user_id)
                elif room.startswith('poker_'):
                    table_id = int(room.split('_')[1])
                    if table_id in self.game_rooms['poker']:
                        self.game_rooms['poker'][table_id].discard(user_id)
            
            del self.connected_users[user_id]
            logger.info(f"User {user_id} disconnected from WebSocket")
    
    def handle_join_room(self, data):
        """Handle joining any game room"""
        user_id = self._get_authenticated_user()
        if not user_id:
            emit('error', {'message': 'Authentication required'})
            return
            
        room_name = data.get('room')
        if not room_name:
            emit('error', {'message': 'Room name is required'})
            return
            
        # Join the room
        join_room(room_name)
        
        # Update our tracking
        if room_name == 'spacecrash':
            self.game_rooms['spacecrash'].add(user_id)
        elif room_name.startswith('poker_'):
            table_id = room_name.split('_')[1]
            try:
                table_id = int(table_id)
                if table_id not in self.game_rooms['poker']:
                    self.game_rooms['poker'][table_id] = set()
                self.game_rooms['poker'][table_id].add(user_id)
            except ValueError:
                emit('error', {'message': 'Invalid poker table ID'})
                return
                
        self.connected_users[user_id]['rooms'].add(room_name)
        
        logger.info(f"User {user_id} joined room: {room_name}")
        emit('room_joined', {'room': room_name, 'success': True})
        
    def handle_leave_room(self, data=None):
        """Handle leaving a game room"""
        user_id = self._get_authenticated_user()
        if not user_id:
            return
            
        room_name = data.get('room') if data else None
        
        if room_name:
            # Leave specific room
            leave_room(room_name)
            self._remove_user_from_room(user_id, room_name)
            logger.info(f"User {user_id} left room: {room_name}")
            emit('room_left', {'room': room_name})
        else:
            # Leave all rooms
            user_rooms = self.connected_users[user_id]['rooms'].copy()
            for room in user_rooms:
                leave_room(room)
                self._remove_user_from_room(user_id, room)
            logger.info(f"User {user_id} left all rooms")
            emit('rooms_left', {'rooms': list(user_rooms)})
            
    def _remove_user_from_room(self, user_id, room_name):
        """Remove user from room tracking"""
        if room_name == 'spacecrash':
            self.game_rooms['spacecrash'].discard(user_id)
        elif room_name.startswith('poker_'):
            table_id = room_name.split('_')[1]
            try:
                table_id = int(table_id)
                if table_id in self.game_rooms['poker']:
                    self.game_rooms['poker'][table_id].discard(user_id)
            except ValueError:
                pass
                
        if user_id in self.connected_users:
            self.connected_users[user_id]['rooms'].discard(room_name)
    
    # Legacy handlers for backward compatibility
    def handle_join_spacecrash_legacy(self, data=None):
        """Legacy handler for joining Spacecrash - redirects to new handler"""
        self.handle_join_room({'room': 'spacecrash'})
        
    def handle_leave_spacecrash_legacy(self, data=None):
        """Legacy handler for leaving Spacecrash - redirects to new handler"""
        self.handle_leave_room({'room': 'spacecrash'})
        """Handle joining Poker table room"""
        user_id = self._get_authenticated_user()
        if not user_id:
            return
        
    def handle_join_poker_table(self, data):
        """Handle joining Poker table room"""
        user_id = self._get_authenticated_user()
        if not user_id:
            return
        
        table_id = data.get('table_id')
        if not table_id:
            emit('error', {'message': 'table_id is required'})
            return
            
        # Use new room handler
        self.handle_join_room({'room': f'poker_{table_id}'})
    
    def handle_leave_poker_table(self, data):
        """Handle leaving Poker table room"""
        table_id = data.get('table_id')
        if not table_id:
            emit('error', {'message': 'table_id is required'})
            return
            
        # Use new room handler  
        self.handle_leave_room({'room': f'poker_{table_id}'})
    
    def _get_authenticated_user(self):
        """Get authenticated user ID for current request"""
        socket_id = request.sid
        for user_id, data in self.connected_users.items():
            if data['socket_id'] == socket_id:
                return user_id
        return None
    
    # Event Broadcasting Methods
    def broadcast_spacecrash_update(self, game_data):
        """Broadcast Spacecrash game state update to all connected users"""
        if not self.socketio:
            return
        
        self.socketio.emit(
            'spacecrash_update',
            {
                'type': 'spacecrash_update',
                'game': game_data,
                'timestamp': datetime.now(timezone.utc).isoformat()
            },
            room='spacecrash'
        )
        logger.debug(f"Broadcasted Spacecrash update to {len(self.game_rooms['spacecrash'])} users")
    
    def broadcast_poker_update(self, table_id, game_data):
        """Broadcast Poker game state update to all users at a table"""
        if not self.socketio:
            return
        
        room_name = f'poker_{table_id}'
        self.socketio.emit(
            'game_state_update',
            {
                'type': 'game_state_update',
                'table_id': table_id,
                'game_state': game_data,
                'timestamp': datetime.now(timezone.utc).isoformat()
            },
            room=room_name,
            namespace='/poker'
        )
        
        connected_count = len(self.game_rooms['poker'].get(table_id, set()))
        logger.debug(f"Broadcasted Poker table {table_id} update to {connected_count} users")
    
    def broadcast_poker_action(self, table_id, action_data):
        """Broadcast player action to all users at a poker table"""
        if not self.socketio:
            return
        
        room_name = f'poker_{table_id}'
        self.socketio.emit(
            'player_action',
            {
                'type': 'player_action',
                'table_id': table_id,
                'action': action_data,
                'timestamp': datetime.now(timezone.utc).isoformat()
            },
            room=room_name,
            namespace='/poker'
        )
    
    def broadcast_poker_hand_started(self, table_id, hand_data):
        """Broadcast new hand started to poker table"""
        if not self.socketio:
            return
        
        room_name = f'poker_{table_id}'
        self.socketio.emit(
            'hand_started',
            {
                'type': 'hand_started',
                'table_id': table_id,
                'hand': hand_data,
                'timestamp': datetime.now(timezone.utc).isoformat()
            },
            room=room_name,
            namespace='/poker'
        )
    
    def broadcast_poker_hand_ended(self, table_id, hand_result):
        """Broadcast hand ended to poker table"""
        if not self.socketio:
            return
        
        room_name = f'poker_{table_id}'
        self.socketio.emit(
            'hand_ended',
            {
                'type': 'hand_ended',
                'table_id': table_id,
                'result': hand_result,
                'timestamp': datetime.now(timezone.utc).isoformat()
            },
            room=room_name,
            namespace='/poker'
        )
    
    def get_connected_users_count(self):
        """Get total number of connected users"""
        return len(self.connected_users)
    
    def get_room_users_count(self, room_type, table_id=None):
        """Get number of users in a specific room"""
        if room_type == 'spacecrash':
            return len(self.game_rooms['spacecrash'])
        elif room_type == 'poker' and table_id:
            return len(self.game_rooms['poker'].get(table_id, set()))
        return 0

# Global instance
websocket_manager = WebSocketManager()
