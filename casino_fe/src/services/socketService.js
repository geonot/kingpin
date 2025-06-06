import { io } from 'socket.io-client';

// Ensure the URL matches your backend WebSocket server
// For development, if frontend is on :8080 and backend on :5000 (default Flask)
const SOCKET_URL = process.env.VUE_APP_SOCKET_URL || 'http://localhost:5000'; // Make sure your Flask backend SocketIO is accessible

export const socket = io(SOCKET_URL, {
  autoConnect: false, // We will connect manually when needed
  transports: ['websocket'], // Optional: force websockets if polling fallback is not desired
  // Add any other necessary configurations, like auth tokens if your backend socket connection requires it
  // For example, if you use JWT and need to pass it:
  // auth: {
  //   token: localStorage.getItem('access_token') // Example: retrieve token from localStorage
  // }
  // Ensure 'withCredentials: true' is used if relying on cookies for cross-origin requests,
  // though this might be default or handled by same-origin policy if applicable.
  withCredentials: true, // Important for cookie-based auth like Flask-JWT-Extended sessions
});

// Optional: Add generic listeners for common events like connect, disconnect, connect_error
socket.on('connect', () => {
  console.log('Socket connected:', socket.id);
});

socket.on('disconnect', (reason) => {
  console.log('Socket disconnected:', reason);
  // Handle potential reconnection logic or UI updates if necessary
});

socket.on('connect_error', (error) => {
  console.error('Socket connection error:', error);
  // Handle UI updates or retry mechanisms if necessary
});

// Expose methods to connect/disconnect if needed globally, or handle in components
export const connectSocket = () => {
  if (!socket.connected) {
    console.log('Attempting to connect socket...');
    socket.connect();
  }
};

export const disconnectSocket = () => {
  if (socket.connected) {
    console.log('Attempting to disconnect socket...');
    socket.disconnect();
  }
};

// Listener for backend's general 'response' messages (often used for success/error feedback)
socket.on('response', (data) => {
    console.log('General socket server response:', data);
});

// Specific listener for room join errors, if backend emits such an event
socket.on('room_join_error', (data) => {
    console.error('Socket room join error:', data);
});

// Specific listener for room leave errors
socket.on('room_leave_error', (data) => {
    console.error('Socket room leave error:', data);
});

// Specific listener for successful room join confirmation
socket.on('room_joined', (data) => {
    console.log('Socket room joined:', data);
});

// Specific listener for successful room leave confirmation
socket.on('room_left', (data) => {
    console.log('Socket room left:', data);
});

// Specific listener for errors during poker table updates, if backend emits such an event
socket.on('poker_table_update_error', (data) => {
    console.error('Poker table update error from socket:', data);
});
