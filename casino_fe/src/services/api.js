import axios from 'axios';

let store; // To be injected

export function injectStore(_store) {
  store = _store;
}

const apiClient = axios.create({
  baseURL: '/api',
  headers: { 'Content-Type': 'application/json' },
  withCredentials: true, // Essential for HTTP-only cookies
});

// Enhanced request interceptor for CSRF protection
apiClient.interceptors.request.use(config => {
  // Add CSRF token to headers for state-changing requests
  if (['post', 'put', 'delete', 'patch'].includes(config.method?.toLowerCase())) {
    if (store && store.state.csrfToken) {
      config.headers['X-CSRF-Token'] = store.state.csrfToken;
    }
  }
  return config;
}, error => Promise.reject(error));

// Enhanced response interceptor with improved error handling
apiClient.interceptors.response.use(
  response => response,
  async error => {
    const originalRequest = error.config;
    
    if (error.response?.status === 401 && !originalRequest._retry && store) {
      originalRequest._retry = true;
      console.log('Attempting to refresh token due to 401 error');
      
      try {
        const refreshData = await store.dispatch('refreshToken');
        if (refreshData?.status) {
          // Retry original request
          return apiClient(originalRequest);
        } else {
          console.log('Token refresh failed, logging out');
          await store.dispatch('logout');
          return Promise.reject(error);
        }
      } catch (refreshError) {
        console.error('Error during token refresh:', refreshError);
        await store.dispatch('logout');
        return Promise.reject(refreshError);
      }
    }
    
    if (error.response?.status === 403 && error.response?.data?.status_message?.includes('CSRF')) {
      // CSRF token expired, try to get a new one
      console.log('CSRF token validation failed, refreshing token');
      try {
        await store.dispatch('getCsrfToken');
        if (!originalRequest._retryCSRF) {
          originalRequest._retryCSRF = true;
          return apiClient(originalRequest);
        }
      } catch (csrfError) {
        console.error('Failed to refresh CSRF token:', csrfError);
      }
    }
    
    return Promise.reject(error);
  }
);

export default {
  // Authentication endpoints
  login(credentials) {
    return apiClient.post('/login', credentials);
  },
  
  register(userData) {
    return apiClient.post('/register', userData);
  },
  
  logout() {
    return apiClient.post('/logout');
  },
  
  refreshToken() {
    // With HTTP-only cookies, no need to pass token manually
    return apiClient.post('/refresh');
  },
  
  getCsrfToken() {
    return apiClient.get('/csrf-token');
  },
  
  getUserProfile() {
    return apiClient.get('/me');
  },
  
  // Game endpoints
  getSlots() {
    return apiClient.get('/slots');
  },
  
  getTables() {
    return apiClient.get('/tables');
  },

  // Gameplay Actions
  endSession(payload = {}) {
    return apiClient.post('/end_session', payload);
  },
  
  joinGame(payload) {
    if (payload.game_type === 'slot' || payload.slot_id) {
      return apiClient.post('/slots/join', payload);
    } else if (payload.game_type === 'blackjack' || payload.table_id) {
      return apiClient.post('/blackjack/join', payload);
    } else {
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

  // User Account Actions (with CSRF protection)
  withdraw(payload) {
    return apiClient.post('/withdraw', payload);
  },
  
  updateSettings(payload) {
    return apiClient.post('/settings', payload);
  },
  
  deposit(payload) {
    return apiClient.post('/deposit', payload);
  },
  
  transferFunds(payload) {
    return apiClient.post('/transfer', payload);
  },
  
  getBalance() {
    return apiClient.get('/balance');
  },
  
  getTransactions(page = 1, perPage = 20) {
    return apiClient.get(`/transactions?page=${page}&per_page=${perPage}`);
  },

  // Admin Actions
  fetchAdminDashboardData() {
    return apiClient.get('/admin/dashboard');
  },
  
  fetchAdminUsers(page = 1, perPage = 20) {
    return apiClient.get(`/admin/users?page=${page}&per_page=${perPage}`);
  }
};
