import { createApp } from 'vue';
import App from './App.vue';
import router from './router';
import store from './store';
import './assets/tailwind.css'; // Tailwind directives
import './assets/styles.css'; // Custom global styles
import mitt from 'mitt'; // Import mitt
import { globalWebSocket } from '@/composables/useWebSocket';

// Create event emitter instance
const emitter = mitt();

// Create Vue app instance
const app = createApp(App);

// Make event bus available globally (alternative to provide/inject)
// Use provide/inject for better Composition API integration if preferred
app.config.globalProperties.$bus = emitter;

// Use plugins
app.use(store);

// Inject the store instance into the apiService.
// This allows the apiService to access the Vuex store, for example,
// to read authentication tokens or dispatch actions upon API call events (e.g., session expiry).
import { injectStore } from '@/services/api';
injectStore(store);

app.use(router);

// Initialize WebSocket connection when user is authenticated
store.watch(
  (state) => ({ isAuthenticated: state.isAuthenticated, user: state.user }),
  ({ isAuthenticated, user }) => {
    if (isAuthenticated && user && !globalWebSocket.isConnected.value) {
      console.log('User authenticated, connecting WebSocket...');
      globalWebSocket.connect(user);
    } else if (!isAuthenticated && globalWebSocket.isConnected.value) {
      console.log('User logged out, disconnecting WebSocket...');
      globalWebSocket.disconnect();
    }
  },
  { immediate: true }
);

// For testing: Connect WebSocket immediately (remove in production)
setTimeout(() => {
  if (!globalWebSocket.isConnected.value) {
    console.log('Testing WebSocket connection...');
    globalWebSocket.connect({ id: 'test', username: 'test' });
  }
}, 2000);

// Global error handler for Vue
app.config.errorHandler = (err, instance, info) => {
  console.error("Vue error:", err);
  console.error("Vue error instance:", instance);
  console.error("Vue error info:", info);
  // Depending on requirements, you might send this error to a logging service
  // For example: Sentry.captureException(err);
  // Or display a generic error message to the user via the event bus or store
  // emitter.emit('global-error', 'An unexpected error occurred in the application.');
};

// Mount the app
app.mount('#app');

// Global handler for unhandled promise rejections
window.addEventListener('unhandledrejection', event => {
  console.error('Unhandled promise rejection:', event.reason);
  // Again, consider sending to a logging service
  // For example: Sentry.captureException(event.reason);
  // Or display a generic error message
  // emitter.emit('global-error', 'An unexpected error occurred (async).');
});

// Global handler for unhandled promise rejections
window.addEventListener('unhandledrejection', event => {
  console.error('Unhandled promise rejection:', event.reason);
  // Again, consider sending to a logging service
  // For example: Sentry.captureException(event.reason);
  // Or display a generic error message
  // emitter.emit('global-error', 'An unexpected error occurred (async).');
});

// Optionally, dispatch initial actions after app is mounted or created
// Example: Check authentication status or load initial data
store.dispatch('loadSession'); // Load user session from localStorage

