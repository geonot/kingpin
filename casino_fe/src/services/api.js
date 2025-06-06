import axios from 'axios';

let store; // To be injected

export function injectStore(_store) {
  store = _store;
}

const apiClient = axios.create({
  baseURL: '/api', // Assuming backend is served on the same domain or proxied to /api
  headers: { 'Content-Type': 'application/json' },
  withCredentials: true, // Ensure cookies (like HttpOnly refresh token) are sent
});

apiClient.interceptors.request.use(config => {
  let token = null;
  if (store && store.state && store.state.accessToken) { // Changed to accessToken
    token = store.state.accessToken;
  }
  // Removed localStorage fallback for access token

  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
}, error => Promise.reject(error));

apiClient.interceptors.response.use(response => response, async error => {
  const originalRequest = error.config;
  if (error.response && error.response.status === 401 && !originalRequest._retry && store) {
    originalRequest._retry = true;
    console.log('Attempting to refresh token due to 401 error');
    try {
      // Check if refreshToken action exists
      if (store && store._actions['refreshToken']) {
        const refreshData = await store.dispatch('refreshToken'); // Vuex action refreshToken
        if (refreshData && refreshData.access_token) {
          // Vuex action 'refreshToken' should have updated store.state.accessToken via 'setAuthTokens'
          // The request interceptor will pick up the new accessToken for the retried request.
          originalRequest.headers.Authorization = `Bearer ${refreshData.access_token}`;
          return apiClient(originalRequest); // Retry original request
        } else {
          console.log('Refresh token Vuex action did not return new access token, or failed. Logout should have been dispatched by refreshToken action.');
          // store.dispatch('logout') should have been called by the refreshToken action if it failed.
          return Promise.reject(error); // Reject, as refresh failed.
        }
      } else {
         console.error('refreshToken action does not exist in the store. Cannot refresh token.');
         // If no refresh action, logout or handle error appropriately.
         if (store && store._actions['logout']) {
            await store.dispatch('logout');
         }
         return Promise.reject(error);
      }
    } catch (refreshError) {
      console.error('Error during token refresh dispatch, or subsequent error. Logout should have been dispatched.', refreshError);
      // store.dispatch('logout') should have been called by the refreshToken action if it failed.
      return Promise.reject(refreshError); // Reject, as refresh process failed.
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
    // The Vuex action will handle clearing local state.
    return apiClient.post('/logout');
    // If backend needs to invalidate HttpOnly refresh token, it can do so here,
    // or a separate logout2 call can be made from Vuex store if necessary.
  },
  refreshToken() {
    // The HttpOnly refresh_token cookie is sent automatically by the browser with withCredentials: true.
    // The backend @jwt_required(refresh=True) decorator will use it.
    // No need to send token in body or headers from frontend for this specific call.
    // The main request interceptor might still add an Authorization header with the *access* token,
    // but the backend's refresh logic should ignore it and use the cookie.
    return apiClient.post('/refresh', {}); // Sending empty body for refresh
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
    return apiClient.post('/join', payload);
  },
  spin(payload) {
    return apiClient.post('/spin', payload);
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
  }
};
