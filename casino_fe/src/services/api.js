import axios from 'axios';

let store; // To be injected

export function injectStore(_store) {
  store = _store;
}

const apiClient = axios.create({
  baseURL: '/api', // Assuming backend is served on the same domain or proxied to /api
  headers: { 'Content-Type': 'application/json' },
});

apiClient.interceptors.request.use(config => {
  // Try to get token from store first, then localStorage as a fallback
  let token = null;
  if (store && store.state && store.state.userSession) { // Corrected path to token
    token = store.state.userSession;
  } else {
    // Fallback to localStorage if store or token in store is not available
    const userSessionFromLocalStorage = localStorage.getItem('userSession');
    if (userSessionFromLocalStorage) {
      // Note: The current api.js stores the raw token string in localStorage, not a JSON object.
      // If it were an object like { accessToken: '...' }, parsing would be needed.
      // Based on store/index.js, userSession is the token itself.
      token = userSessionFromLocalStorage;
    }
  }

  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
}, error => Promise.reject(error));

apiClient.interceptors.response.use(response => response, async error => {
  const originalRequest = error.config;
  if (error.response && error.response.status === 401 && !originalRequest._retry && store) {
    originalRequest._retry = true;
    try {
      // Check if refreshToken action exists (now global)
      if (store && store._actions['refreshToken']) {
        const refreshData = await store.dispatch('refreshToken');
        if (refreshData && refreshData.access_token) {
          // Update Authorization header for the original request
          // Also update the token in the store via mutation if not already done by refreshToken action
          if (store.state.userSession !== refreshData.access_token) {
             store.commit('setAuthTokens', { accessToken: refreshData.access_token, refreshToken: store.state.refreshToken });
          }
          originalRequest.headers.Authorization = `Bearer ${refreshData.access_token}`;
          return apiClient(originalRequest); // Retry original request
        } else {
          if (store && store._actions['logout']) { // Check if logout action exists
            await store.dispatch('logout');
          }
          return Promise.reject(error);
        }
      } else {
         if (store && store._actions['logout']) { // Check if logout action exists
            await store.dispatch('logout');
         }
         return Promise.reject(error);
      }
    } catch (refreshError) {
      if (store && store._actions['logout']) { // Check if logout action exists
        await store.dispatch('logout');
      }
      return Promise.reject(refreshError);
    }
  }
  return Promise.reject(error);
});

export default {
  login(credentials) {
    return apiClient.post('/login', credentials);
  },
  register(userData) {
    return apiClient.post('/register', userData);
  },
  logout() {
    // This logout is for invalidating the access token on the backend.
    // The Vuex action will handle clearing local storage and state.
    return apiClient.post('/logout');
  },
  refreshToken(refreshTokenValue) {
    // Use a temporary client for refresh to avoid interceptor loop if refresh itself fails with 401
    // and to ensure the correct refresh token is sent.
    const refreshApiClient = axios.create({
        baseURL: '/api',
        headers: { 'Content-Type': 'application/json' },
    });
    return refreshApiClient.post('/refresh', {}, { // Sending empty body for refresh
      headers: { Authorization: `Bearer ${refreshTokenValue}` }
    });
  },
  fetchUserProfile() {
    return apiClient.get('/me'); // Assuming '/me' is the endpoint for user profile
  },

  // Game Data
  getSlots() {
    return apiClient.get('/slots');
  },
  getTables() {
    return apiClient.get('/tables');
  },

  // Gameplay Actions
  endSession(payload = {}) { // Added default empty object for payload if not provided
    return apiClient.post('/end_session', payload);
  },
  joinGame(payload) {
    // Route to the correct game-specific join endpoint based on game type
    if (payload.game_type === 'slot' || payload.slot_id) {
      return apiClient.post('/slots/join', payload);
    } else if (payload.game_type === 'blackjack' || payload.table_id) {
      return apiClient.post('/blackjack/join', payload);
    } else {
      // Fallback to generic join if game type is unclear
      return apiClient.post('/slots/join', payload);
    }
  },
  spin(payload) {
    return apiClient.post('/slots/spin', payload);
  },
  joinBlackjack(payload) {
    return apiClient.post('/join_blackjack', payload);
  },
  blackjackAction(payload) {
    return apiClient.post('/blackjack_action', payload);
  },

  // User Account Actions
  withdraw(payload) {
    return apiClient.post('/withdraw', payload);
  },
  updateSettings(payload) {
    return apiClient.post('/settings', payload);
  },
  applyBonusCode(payload) { // Endpoint is /deposit
    return apiClient.post('/deposit', payload);
  },

  // Admin Actions
  fetchAdminDashboardData() {
    return apiClient.get('/admin/dashboard');
  },
  fetchAdminUsers(page = 1, perPage = 20) { // Default values match store
    return apiClient.get(`/admin/users?page=${page}&per_page=${perPage}`);
  },

  // Crystal Garden API Methods
  getGardenState() {
    return apiClient.get('/crystal-garden/garden-state');
  },
  buyCrystalSeed(seedId) {
    return apiClient.post('/crystal-garden/buy-seed', { seed_id: seedId });
  },
  plantCrystalSeed(payload) { // { seed_id, position_x, position_y }
    return apiClient.post('/crystal-garden/plant-seed', payload);
  },
  processGardenCycle(gardenId) { // Backend expects garden_id in payload for POST, but GET might be more RESTful if no body needed. Sticking to current POST.
    // The backend route for process-cycle in crystal_garden_bp doesn't explicitly take garden_id from payload.
    // It uses current_user.id to find the garden. So, an empty POST or specific user garden ID might be intended.
    // For now, assuming the backend can derive garden_id from user or a default garden_id if not passed.
    // Let's send an empty payload as the current route doesn't specify one.
    // The backend route for /process-cycle in this project actually gets garden_id from current_user.
    // So, this API method does not need to send garden_id.
    return apiClient.post('/crystal-garden/process-cycle', {});
  },
  appraiseCrystal(flowerId) {
    return apiClient.post('/crystal-garden/appraise-crystal', { flower_id: flowerId });
  },
  sellCrystal(flowerId) {
    return apiClient.post('/crystal-garden/sell-crystal', { flower_id: flowerId });
  },
  activatePowerUp(payload) { // { flower_id, power_up_type }
    return apiClient.post('/crystal-garden/activate-powerup', payload);
  }
};
