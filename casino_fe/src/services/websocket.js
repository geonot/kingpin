import { io } from 'socket.io-client';

class WebSocketService {
  constructor() {
    this.socket = null;
    this.isConnected = false;
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 5;
    this.reconnectInterval = 1000; // Start with 1 second
    this.maxReconnectInterval = 30000; // Max 30 seconds
    this.eventListeners = new Map();
    this.currentRoom = null;
    this.currentUser = null;
  }

  /**
   * Connect to the WebSocket server using cookie authentication
   * @param {Object} user - Current user object
   */
  connect(user) {
    if (this.socket && this.isConnected) {
      console.log('WebSocket already connected');
      return;
    }

    console.log('Connecting to WebSocket server...');
    this.currentUser = user;

    this.socket = io('/', {
      // No auth token needed - cookies will be sent automatically
      withCredentials: true, // Important: this ensures cookies are sent
      autoConnect: true,
      reconnection: true,
      reconnectionDelay: this.reconnectInterval,
      reconnectionAttempts: this.maxReconnectAttempts,
      timeout: 20000,
      transports: ['websocket', 'polling']
    });

    this.setupEventHandlers();
  }

  /**
   * Setup core event handlers for connection management
   */
  setupEventHandlers() {
    if (!this.socket) return;

    this.socket.on('connect', () => {
      console.log('WebSocket connected successfully');
      this.isConnected = true;
      this.reconnectAttempts = 0;
      this.reconnectInterval = 1000; // Reset reconnect interval
      
      // Re-join room if we were in one before reconnection
      if (this.currentRoom) {
        this.joinRoom(this.currentRoom);
      }
      
      this.emit('ws:connected');
    });

    this.socket.on('disconnect', (reason) => {
      console.log('WebSocket disconnected:', reason);
      this.isConnected = false;
      this.emit('ws:disconnected', reason);
    });

    this.socket.on('connect_error', (error) => {
      console.error('WebSocket connection error:', error);
      this.isConnected = false;
      this.reconnectAttempts++;
      
      // Exponential backoff for reconnection
      this.reconnectInterval = Math.min(
        this.reconnectInterval * 2,
        this.maxReconnectInterval
      );
      
      this.emit('ws:error', error);
      
      if (this.reconnectAttempts >= this.maxReconnectAttempts) {
        console.error('Max reconnection attempts reached');
        this.emit('ws:max_reconnect_attempts');
      }
    });

    this.socket.on('authentication_error', (error) => {
      console.error('WebSocket authentication error:', error);
      this.emit('ws:auth_error', error);
    });

    // Game-specific event handlers
    this.socket.on('spacecrash_update', (data) => {
      console.log('Received spacecrash update:', data);
      this.emit('spacecrash:update', data);
    });

    this.socket.on('poker_update', (data) => {
      console.log('Received poker update:', data);
      this.emit('poker:update', data);
    });

    this.socket.on('poker_action', (data) => {
      console.log('Received poker action:', data);
      this.emit('poker:action', data);
    });
  }

  /**
   * Join a specific room (e.g., 'spacecrash' or 'poker_table_1')
   * @param {string} room - Room name to join
   */
  joinRoom(room) {
    if (!this.isConnected || !this.socket) {
      console.warn('Cannot join room: WebSocket not connected');
      return;
    }

    console.log(`Joining room: ${room}`);
    this.currentRoom = room;
    this.socket.emit('join_room', { room });
  }

  /**
   * Leave the current room
   */
  leaveRoom() {
    if (!this.isConnected || !this.socket || !this.currentRoom) {
      return;
    }

    console.log(`Leaving room: ${this.currentRoom}`);
    this.socket.emit('leave_room', { room: this.currentRoom });
    this.currentRoom = null;
  }

  /**
   * Send a message to the server
   * @param {string} event - Event name
   * @param {Object} data - Data to send
   */
  send(event, data = {}) {
    if (!this.isConnected || !this.socket) {
      console.warn('Cannot send message: WebSocket not connected');
      return;
    }

    this.socket.emit(event, data);
  }

  /**
   * Register an event listener
   * @param {string} event - Event name
   * @param {Function} callback - Callback function
   */
  on(event, callback) {
    if (!this.eventListeners.has(event)) {
      this.eventListeners.set(event, []);
    }
    this.eventListeners.get(event).push(callback);
  }

  /**
   * Remove an event listener
   * @param {string} event - Event name
   * @param {Function} callback - Callback function to remove
   */
  off(event, callback) {
    if (!this.eventListeners.has(event)) return;

    const listeners = this.eventListeners.get(event);
    const index = listeners.indexOf(callback);
    if (index > -1) {
      listeners.splice(index, 1);
    }
  }

  /**
   * Emit an event to all registered listeners
   * @param {string} event - Event name
   * @param {*} data - Data to pass to listeners
   */
  emit(event, data) {
    if (!this.eventListeners.has(event)) return;

    this.eventListeners.get(event).forEach(callback => {
      try {
        callback(data);
      } catch (error) {
        console.error(`Error in event listener for ${event}:`, error);
      }
    });
  }

  /**
   * Disconnect from the WebSocket server
   */
  disconnect() {
    if (this.socket) {
      console.log('Disconnecting WebSocket...');
      this.leaveRoom();
      this.socket.disconnect();
      this.socket = null;
    }
    this.isConnected = false;
    this.currentRoom = null;
    this.currentUser = null;
    this.reconnectAttempts = 0;
  }

  /**
   * Get connection status
   * @returns {boolean} - True if connected
   */
  getConnectionStatus() {
    return this.isConnected;
  }

  /**
   * Get current room
   * @returns {string|null} - Current room name
   */
  getCurrentRoom() {
    return this.currentRoom;
  }

  /**
   * Clean up all event listeners
   */
  cleanup() {
    this.eventListeners.clear();
    this.disconnect();
  }
}

// Create and export a singleton instance
const websocketService = new WebSocketService();

export default websocketService;
