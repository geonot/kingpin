import { ref, watch } from 'vue';
import websocketService from '@/services/websocket';

// Global reactive state
const isConnected = ref(false);
const connectionError = ref(null);
const currentRoom = ref(null);

export function useWebSocket() {
  /**
   * Initialize WebSocket connection with user authentication
   * @param {Object} user - Current authenticated user
   */
  const connect = (user) => {
    if (!user) {
      console.warn('Cannot connect WebSocket: no user provided');
      return;
    }

    console.log('Initializing WebSocket connection for user:', user.username);
    websocketService.connect(user);
  };

  /**
   * Disconnect WebSocket
   */
  const disconnect = () => {
    console.log('Disconnecting WebSocket');
    websocketService.disconnect();
    isConnected.value = false;
    connectionError.value = null;
    currentRoom.value = null;
  };

  /**
   * Join a specific room (e.g., 'spacecrash' or 'poker_table_1')
   * @param {string} room - Room name
   */
  const joinRoom = (room) => {
    if (!isConnected.value) {
      console.warn('Cannot join room: WebSocket not connected');
      return;
    }
    
    console.log(`Joining room: ${room}`);
    websocketService.joinRoom(room);
    currentRoom.value = room;
  };

  /**
   * Leave current room
   */
  const leaveRoom = () => {
    if (currentRoom.value) {
      console.log(`Leaving room: ${currentRoom.value}`);
      websocketService.leaveRoom();
      currentRoom.value = null;
    }
  };

  /**
   * Subscribe to WebSocket events
   * @param {string} event - Event name
   * @param {Function} callback - Event handler
   */
  const on = (event, callback) => {
    websocketService.on(event, callback);
  };

  /**
   * Unsubscribe from WebSocket events
   * @param {string} event - Event name
   * @param {Function} callback - Event handler to remove
   */
  const off = (event, callback) => {
    websocketService.off(event, callback);
  };

  /**
   * Send a message via WebSocket
   * @param {string} event - Event name
   * @param {Object} data - Data to send
   */
  const send = (event, data) => {
    websocketService.send(event, data);
  };

  // Set up core event listeners
  websocketService.on('ws:connected', () => {
    console.log('WebSocket connected successfully');
    isConnected.value = true;
    connectionError.value = null;
  });

  websocketService.on('ws:disconnected', (reason) => {
    console.log('WebSocket disconnected:', reason);
    isConnected.value = false;
    currentRoom.value = null;
  });

  websocketService.on('ws:error', (error) => {
    console.error('WebSocket error:', error);
    connectionError.value = error;
    isConnected.value = false;
  });

  websocketService.on('ws:auth_error', (error) => {
    console.error('WebSocket authentication error:', error);
    connectionError.value = 'Authentication failed';
    isConnected.value = false;
  });

  websocketService.on('ws:max_reconnect_attempts', () => {
    console.error('Max WebSocket reconnection attempts reached');
    connectionError.value = 'Connection failed - please refresh the page';
    isConnected.value = false;
  });

  return {
    // State
    isConnected,
    connectionError,
    currentRoom,
    
    // Methods
    connect,
    disconnect,
    joinRoom,
    leaveRoom,
    on,
    off,
    send,
    
    // Direct access to service for advanced usage
    websocketService
  };
}

// Create a global instance for shared state
export const globalWebSocket = useWebSocket();
