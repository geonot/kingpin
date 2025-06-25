#!/usr/bin/env python3
"""
Simple WebSocket test server for testing the implementation
without SQLAlchemy dependencies
"""

from flask import Flask
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['SECRET_KEY'] = 'test-secret'

# Enable CORS
CORS(app, origins=['http://localhost:8080', 'http://127.0.0.1:8080'])

# Initialize SocketIO
socketio = SocketIO(app, 
                   cors_allowed_origins=['http://localhost:8080', 'http://127.0.0.1:8080'],
                   async_mode='threading',
                   logger=True,
                   engineio_logger=True)

@socketio.on('connect')
def handle_connect():
    logger.info(f'Client connected: {request.sid}')
    emit('connection_status', {'status': 'connected', 'message': 'WebSocket connection successful!'})

@socketio.on('disconnect')
def handle_disconnect():
    logger.info(f'Client disconnected: {request.sid}')

@socketio.on('test_message')
def handle_test_message(data):
    logger.info(f'Received test message: {data}')
    emit('test_response', {'message': 'Test message received!', 'echo': data})

@socketio.on('join_spacecrash')
def handle_join_spacecrash():
    logger.info('Client joined spacecrash room')
    emit('room_joined', {'room': 'spacecrash'})

@socketio.on('join_poker_table')
def handle_join_poker_table(data):
    table_id = data.get('table_id', 1)
    logger.info(f'Client joined poker table: {table_id}')
    emit('room_joined', {'room': f'poker_{table_id}'})

@app.route('/')
def index():
    return '''
    <h1>WebSocket Test Server</h1>
    <p>WebSocket test server is running!</p>
    <p>Connect from frontend at: ws://localhost:5000</p>
    '''

if __name__ == '__main__':
    logger.info('Starting WebSocket test server...')
    socketio.run(app, host='127.0.0.1', port=5000, debug=True, allow_unsafe_werkzeug=True)
