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

    if (error.response && error.response.data && error.response.data.error_code) {
      // New structured error from backend
      const { error_code, status_message, details, action_button } = error.response.data;
      const request_id = error.response.data.request_id; // Assuming request_id is also part of the response
      
      console.error(`Structured error received: Code ${error_code}, Message: ${status_message}, RequestID: ${request_id}, Details:`, details);

      // Handle specific error codes
      if (error_code === 'BE_GEN_003') { // UNAUTHENTICATED
        if (!originalRequest._retry && store) {
          originalRequest._retry = true;
          console.log('Attempting to refresh token due to UNAUTHENTICATED error (BE_GEN_003)');
          try {
            const refreshData = await store.dispatch('refreshToken'); // Assuming this action exists
            if (refreshData && refreshData.status) { // Check if refreshData itself and its status are valid
              return apiClient(originalRequest); // Retry original request
            } else {
              console.log('Token refresh failed, logging out');
              await store.dispatch('logout'); // Assuming this action exists
              // No need to reject here, logout might redirect or Vuex state change handles UI
            }
          } catch (refreshError) {
            console.error('Error during token refresh:', refreshError);
            await store.dispatch('logout');
            // We might want to propagate a specific error about refresh failure
          }
        } else if (originalRequest._retry) {
            // Refresh already attempted, logout
            console.log('Token refresh already attempted or store not available, logging out');
            if (store) await store.dispatch('logout');
        }
         // If logout doesn't redirect, we still need to reject an error for the calling code
        return Promise.reject({
          isStructuredError: true,
          errorCode: error_code,
          message: status_message || 'Authentication failed after refresh attempt.',
          details: details,
          actionButton: action_button,
          originalError: error
        });
      }

      if (error_code === 'BE_GEN_010') { // CSRF_TOKEN_INVALID
        if (!originalRequest._retryCSRF && store) {
          originalRequest._retryCSRF = true;
          console.log('Attempting to refresh CSRF token due to CSRF_TOKEN_INVALID error (BE_GEN_010)');
          try {
            await store.dispatch('getCsrfToken'); // Assuming this action exists
            return apiClient(originalRequest); // Retry original request
          } catch (csrfError) {
            console.error('Failed to refresh CSRF token:', csrfError);
            // Propagate a specific error about CSRF refresh failure
             return Promise.reject({
                isStructuredError: true,
                errorCode: error_code, // Or a new local code like 'CSRF_REFRESH_FAILED'
                message: 'CSRF token refresh failed. Please try again.',
                details: csrfError.message ? { error: csrfError.message } : null,
                actionButton: null, // Or a specific action if applicable
                originalError: error
             });
          }
        }
      }

      // For all other structured errors, propagate them
      return Promise.reject({
        isStructuredError: true,
        errorCode: error_code,
        message: status_message,
        details: details,
        actionButton: action_button,
        originalError: error
      });

    } else if (error.response) {
      // It's an HTTP error but not in our new structured format
      // This could be from an older part of the API or a proxy error
      console.error('Non-structured HTTP error:', error.response.status, error.response.data);
      const message = (error.response.data && error.response.data.status_message) ||
                      (error.response.data && error.response.data.message) ||
                      error.response.statusText ||
                      'An unexpected server error occurred.';
      return Promise.reject({
        isStructuredError: false,
        message: message,
        statusCode: error.response.status,
        originalError: error
      });
    } else {
      // Network error or other issues where error.response is not set
      console.error('Network or other non-HTTP error:', error.message);
      return Promise.reject({
        isStructuredError: false,
        message: error.message || 'A network error occurred. Please check your connection.',
        originalError: error
      });
    }
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
