import { createApp } from 'vue';
import App from './App.vue';
import router from './router';
import store from './store';
import './assets/tailwind.css'; // Tailwind directives
import './assets/styles.css'; // Custom global styles
import mitt from 'mitt'; // Import mitt

// Create event emitter instance
const emitter = mitt();

// Create Vue app instance
const app = createApp(App);

// Make event bus available globally (alternative to provide/inject)
// Use provide/inject for better Composition API integration if preferred
app.config.globalProperties.$bus = emitter;

// Use plugins
app.use(store);
app.use(router);

// Mount the app
app.mount('#app');

// Optionally, dispatch initial actions after app is mounted or created
// Example: Check authentication status or load initial data
store.dispatch('loadSession'); // Load user session from localStorage

