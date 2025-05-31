import { createStore } from 'vuex';
import axios from 'axios';

// --- API Client Setup ---
const apiClient = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json',
  },
});

// This is tricky because 'store' is not defined yet at this point in the module execution.
// A common solution is to inject the store after it's created.
// For this exercise, we'll attempt a simplified version or note the limitation.
// Let's assume for now we'll handle token injection and refresh more directly in actions
// if direct store access in interceptors here is problematic.

// Request interceptor for API token
apiClient.interceptors.request.use(config => {
  const token = localStorage.getItem('userSession'); // Get token from localStorage directly
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
}, error => {
  return Promise.reject(error);
});

// Response interceptor for handling 401 and token refresh
// This will require access to the store's dispatch method.
// We will define this interceptor more fully after the store is created,
// or simplify its direct usage here and handle refresh more explicitly in actions.
// For now, let's set up a basic one that doesn't immediately try to dispatch.
let storeInstance; // To be set later
export const setStoreForApiClient = (store) => {
  storeInstance = store;
};

apiClient.interceptors.response.use(response => {
  return response;
}, async error => {
  const originalRequest = error.config;
  if (error.response && error.response.status === 401 && !originalRequest._retry && storeInstance) {
    originalRequest._retry = true;
    try {
      const refreshData = await storeInstance.dispatch('refreshToken');
      if (refreshData && refreshData.access_token) {
        // apiClient.defaults.headers.common['Authorization'] = 'Bearer ' + refreshData.access_token; // Update default for subsequent
        originalRequest.headers.Authorization = `Bearer ${refreshData.access_token}`; // Update current request
        return apiClient(originalRequest);
      } else {
        await storeInstance.dispatch('logout');
        // router.push('/login'); // Requires router instance, handle in UI components
        return Promise.reject(error);
      }
    } catch (refreshError) {
      await storeInstance.dispatch('logout');
      // router.push('/login');
      return Promise.reject(refreshError);
    }
  }
  return Promise.reject(error);
});


// const SATOSHI_FACTOR = 100_000_000; // Not used in this file currently

export default createStore({
  state: {
    user: null, // Will hold: { id, username, email, balance, deposit_wallet_address, is_admin, is_active, created_at, last_login_at }
    userSession: localStorage.getItem('userSession') || null, // Access Token (JWT)
    refreshToken: localStorage.getItem('refreshToken') || null, // Refresh Token (JWT)
    slots: [], // Array of slot objects from /api/slots
    slotsLoaded: false,
    currentSlotConfig: null, // Holds configuration for a single slot
    tables: [], // Array of table objects from /api/tables
    tablesLoaded: false,
    currentTableConfig: null, // Holds configuration for a single table
  },
  mutations: {
    setUser(state, userData) {
      state.user = userData;
      // No need to stringify/parse for localStorage if only storing tokens,
      // or if user object is simple and non-sensitive for caching.
      // For this refactor, user object is not stored in localStorage directly, only tokens.
    },
    setAuthTokens(state, { accessToken, refreshToken }) {
      state.userSession = accessToken;
      state.refreshToken = refreshToken;
      if (accessToken) {
        localStorage.setItem('userSession', accessToken);
      } else {
        localStorage.removeItem('userSession');
      }
      if (refreshToken) {
        localStorage.setItem('refreshToken', refreshToken);
      } else {
        localStorage.removeItem('refreshToken');
      }
    },
    clearAuth(state) {
      state.user = null;
      state.userSession = null;
      state.refreshToken = null;
      localStorage.removeItem('userSession');
      localStorage.removeItem('refreshToken');
      // localStorage.removeItem('user'); // Removed as user object isn't directly stored now
    },
    setSlots(state, slots) {
      state.slots = slots;
      state.slotsLoaded = true;
    },
    setCurrentSlotConfig(state, config) {
      state.currentSlotConfig = config;
    },
    setTables(state, tables) {
      state.tables = tables;
      state.tablesLoaded = true;
    },
    setCurrentTableConfig(state, config) {
      state.currentTableConfig = config;
    },
    updateUserBalance(state, newBalanceSats) {
      if (state.user && typeof newBalanceSats === 'number') {
        state.user.balance = newBalanceSats;
      }
    },
  },
  actions: {
    // --- Authentication ---
    async register({ dispatch }, payload) { // Changed: dispatch fetchUserProfile
      try {
        const response = await apiClient.post('/register', payload);
        const data = response.data;
        if (data.status && data.access_token && data.refresh_token) {
          // setUser and setAuthTokens will be handled by fetchUserProfile after this
          // Or, commit tokens here, then fetch user profile
          dispatch('setAuthTokensAndFetchUser', { accessToken: data.access_token, refreshToken: data.refresh_token });
        }
        return data;
      } catch (error) {
        console.error("Registration Error:", error.response?.data || error.message);
        return error.response?.data || { status: false, status_message: "Network error during registration." };
      }
    },
    async login({ dispatch }, payload) { // Changed: dispatch fetchUserProfile
      try {
        const response = await apiClient.post('/login', payload);
        const data = response.data;
        if (data.status && data.access_token && data.refresh_token) {
          dispatch('setAuthTokensAndFetchUser', { accessToken: data.access_token, refreshToken: data.refresh_token });
        }
        return data;
      } catch (error) {
        console.error("Login Error:", error.response?.data || error.message);
        return error.response?.data || { status: false, status_message: "Network error during login." };
      }
    },
    // Helper action
    async setAuthTokensAndFetchUser({ commit, dispatch }, { accessToken, refreshToken }) {
        commit('setAuthTokens', { accessToken, refreshToken });
        if (accessToken) {
            await dispatch('fetchUserProfile');
        }
    },
    async refreshToken({ commit, state, dispatch }) {
      if (!state.refreshToken) {
        await dispatch('logout'); // Ensure full logout if no refresh token
        return { status: false, status_message: "No refresh token available. Logged out." };
      }
      try {
        // Temporarily remove the Authorization header for the refresh token request if it's automatically added
        // Or ensure the request interceptor doesn't add it for '/refresh' path.
        // For simplicity, create a new axios instance or use a clean config for refresh.
        const refreshApiClient = axios.create({ baseURL: '/api' });
        const response = await refreshApiClient.post('/refresh', {}, {
          headers: { Authorization: `Bearer ${state.refreshToken}` }
        });

        const data = response.data;
        if (data.status && data.access_token) {
          commit('setAuthTokens', { accessToken: data.access_token, refreshToken: state.refreshToken }); // Keep old refresh token
          return { status: true, access_token: data.access_token };
        } else {
          await dispatch('logout'); // Refresh failed, token likely invalid
          return { status: false, status_message: data.status_message || "Session refresh failed. Logged out." };
        }
      } catch (error) {
        console.error("Token Refresh Error:", error.response?.data || error.message);
        await dispatch('logout'); // Critical error on refresh
        return { status: false, status_message: "Session expired. Please log in again." };
      }
    },
    async logout({ commit, state }) {
      const accessToken = state.userSession;
      const refreshToken = state.refreshToken;

      // Perform local logout immediately
      commit('clearAuth');

      try {
        if (accessToken) {
          await apiClient.post('/logout', {}); // Access token invalidated by interceptor adding it
        }
        if (refreshToken) {
          // logout2 needs its own token, so create a temporary client or set header manually
          const tempApiClient = axios.create({ baseURL: '/api' });
          await tempApiClient.post('/logout2', {}, { headers: { Authorization: `Bearer ${refreshToken}` } });
        }
        return { status: true, status_message: "Logged out successfully from server." };
      } catch (error) {
        console.warn("Server Logout Error:", error.response?.data || error.message);
        // Local logout already performed, this is best effort.
        return { status: true, status_message: "Logged out locally. Server session might still be active." };
      }
    },
    async loadSession({ dispatch }) { // Changed: always dispatch fetchUserProfile
      const accessToken = localStorage.getItem('userSession');
      if (accessToken) {
        // Tokens are already set by the 'setAuthTokens' mutation if they exist in localStorage.
        // We just need to fetch the user profile.
        // The request interceptor will add the token.
        await dispatch('fetchUserProfile');
      } else {
        // No token, ensure state is clean (though clearAuth on logout should handle this)
        dispatch('logout'); // This will also clear any potentially stale refresh token from state
      }
    },
    async fetchUserProfile({ commit }) { // Removed state from params, token comes from interceptor
      try {
        const response = await apiClient.get('/me'); // Endpoint changed from /api/me to /me due to baseURL
        if (response.data.status) {
          commit('setUser', response.data.user);
          return response.data.user;
        } else {
          console.warn("Failed to fetch user profile:", response.data.status_message);
          // Do not logout here, let 401 interceptor handle it if it's an auth issue
          return null;
        }
      } catch (error) {
        console.error("Error fetching user profile:", error.response?.data || error.message);
        // If 401, interceptor should handle. Otherwise, it's a network or server error.
        // No automatic logout here unless it's confirmed an auth failure not handled by interceptor.
        return null;
      }
    },

    // --- Game Data ---
    async fetchSlots({ commit, state }) {
      // if (state.slotsLoaded && !forceRefresh) return state.slots; // Keep loaded data unless forced
      try {
        const response = await apiClient.get('/slots'); // Auth might not be needed for public slot list
        if (response.data.status && Array.isArray(response.data.slots)) {
          commit('setSlots', response.data.slots);
          return response.data; // Return the whole response object {status, slots}
        } else {
          console.error('Error fetching slots:', response.data.status_message || 'API returned non-status-true or invalid data');
          return { status: false, status_message: response.data.status_message || 'Failed to parse slots data.' };
        }
      } catch (error) {
        console.error('Network error fetching slots:', error.response?.data || error.message);
        return { status: false, status_message: error.response?.data?.status_message || "Network error fetching slots." };
      }
    },
    async fetchSlotConfig({ commit, state, dispatch }, slotId) {
      if (!state.slotsLoaded) {
        const fetchResult = await dispatch('fetchSlots');
        // Check if fetchSlots returned an error object or actual data
        if (fetchResult.status === false || !fetchResult.slots) {
            console.error("fetchSlots failed, cannot filter for slot config");
            return null;
        }
      }
      const slot = state.slots.find(s => s.id === Number(slotId));
      if (slot) {
        commit('setCurrentSlotConfig', slot);
        return slot;
      } else {
        console.error(`Slot config for ID ${slotId} not found in loaded slots.`);
        // Optional: If backend supports fetching a single slot by ID:
        // try {
        //   const response = await apiClient.get(`/slots/${slotId}`);
        //   if (response.data.status && response.data.slot) {
        //     commit('setCurrentSlotConfig', response.data.slot);
        //     return response.data.slot;
        //   }
        // } catch (error) {
        //   console.error(`Direct fetch for slot ID ${slotId} failed:`, error.response?.data || error.message);
        // }
        return null;
      }
    },
    async fetchTables({ commit, state }) {
      // if (state.tablesLoaded && !forceRefresh) return state.tables;
      try {
        const response = await apiClient.get('/tables'); // Auth might not be needed
        if (response.data.status && Array.isArray(response.data.tables)) {
          commit('setTables', response.data.tables);
          return response.data; // Return {status, tables}
        } else {
           console.error('Error fetching tables:', response.data.status_message || 'API returned non-status-true or invalid data');
           return { status: false, status_message: response.data.status_message || 'Failed to parse tables data.' };
        }
      } catch (error) {
        console.error('Network error fetching tables:', error.response?.data || error.message);
        return { status: false, status_message: error.response?.data?.status_message || "Network error fetching tables." };
      }
    },
    async fetchTableConfig({ commit, state, dispatch }, tableId) {
      if (!state.tablesLoaded) {
        const fetchResult = await dispatch('fetchTables');
        if (fetchResult.status === false || !fetchResult.tables) {
            console.error("fetchTables failed, cannot filter for table config");
            return null;
        }
      }
      const table = state.tables.find(t => t.id === Number(tableId));
      if (table) {
        commit('setCurrentTableConfig', table);
        return table;
      } else {
        console.error(`Table config for ID ${tableId} not found in loaded tables.`);
        return null;
      }
    },

    // --- Gameplay Actions ---
    async endSession() {
      try {
        const response = await apiClient.post('/end_session', {});
        // Backend only returns status and message, no user/balance update needed here.
        return response.data;
      } catch (error) {
        console.error("End Session Error:", error.response?.data || error.message);
        return error.response?.data || { status: false, status_message: "Network error ending game session." };
      }
    },
    async joinGame({ commit }, payload) {
      try {
        // Ensure game_type is present, defaulting if necessary (though backend might also default)
        payload.game_type = payload.game_type || (payload.slot_id ? 'slot' : (payload.table_id ? 'blackjack' : 'unknown'));
        const response = await apiClient.post('/join', payload);
        // Backend's /join endpoint currently returns { status, game_session, session_id }
        // It does not return the user object or balance.
        // If user balance is affected by join (e.g. theoretical entry fee), backend should handle & return new balance.
        // For now, no direct user balance mutation here based on current backend spec.
        return response.data;
      } catch (error) {
        console.error("Join Game Error:", error.response?.data || error.message);
        return error.response?.data || { status: false, status_message: "Network error joining game." };
      }
    },
    async spin({ commit }, payload) {
      try {
        const betAmount = parseInt(payload.bet_amount, 10);
        if (isNaN(betAmount) || betAmount <= 0) {
            return { status: false, status_message: "Invalid bet amount."};
        }
        const response = await apiClient.post('/spin', { bet_amount: betAmount }); // Send only bet_amount
        if (response.data.status && response.data.user) {
          commit('updateUserBalance', response.data.user.balance);
          // The spin response also contains game_session data, could update that if needed.
          // commit('setCurrentGameSessionDetails', response.data.game_session); // Example
        }
        return response.data; // Full response: { result, win_amount, winning_lines, bonus_*, game_session, user }
      } catch (error) {
        console.error("Spin Error:", error.response?.data || error.message);
        return error.response?.data || { status: false, status_message: "Network error during spin." };
      }
    },
    async joinBlackjack({ commit }, payload) {
      try {
        const betAmount = parseInt(payload.bet_amount, 10);
        const tableId = parseInt(payload.table_id, 10);
        if (isNaN(betAmount) || betAmount <= 0) {
            return { status: false, status_message: "Invalid bet amount."};
        }
        if (isNaN(tableId) || tableId <= 0) {
            return { status: false, status_message: "Invalid table ID."};
        }
        const response = await apiClient.post('/join_blackjack', { table_id: tableId, bet_amount: betAmount });
        if (response.data.status && response.data.user) {
          commit('updateUserBalance', response.data.user.balance);
          // The response also contains 'hand' data which might be stored.
          // commit('setCurrentBlackjackHand', response.data.hand); // Example
        }
        return response.data; // Full response: { hand, user }
      } catch (error) {
        console.error("Join Blackjack Error:", error.response?.data || error.message);
        return error.response?.data || { status: false, status_message: "Network error joining blackjack." };
      }
    },
    async blackjackAction({ commit }, payload) {
      try {
        // hand_id, action_type, hand_index (optional)
        const response = await apiClient.post('/blackjack_action', payload);
        if (response.data.status && response.data.user) {
          commit('updateUserBalance', response.data.user.balance);
          // The response also contains 'action_result' (updated hand state)
          // commit('updateCurrentBlackjackHand', response.data.action_result); // Example
        }
        return response.data; // Full response: { action_result, user }
      } catch (error) {
        console.error("Blackjack Action Error:", error.response?.data || error.message);
        return error.response?.data || { status: false, status_message: "Network error during blackjack action." };
      }
    },

    // --- User Account Actions ---
    async withdraw({ commit }, payload) {
      try {
        const amountSats = parseInt(payload.amount_sats || payload.amount, 10);
        if (isNaN(amountSats) || amountSats <= 0) {
            return { status: false, status_message: "Invalid withdrawal amount."};
        }
        const response = await apiClient.post('/withdraw', {
            amount_sats: amountSats,
            withdraw_wallet_address: payload.withdraw_wallet_address
        });
        if (response.data.status && response.data.user) {
          commit('updateUserBalance', response.data.user.balance);
        }
        return response.data; // { status, withdraw_id, user, status_message }
      } catch (error) {
        console.error("Withdraw Error:", error.response?.data || error.message);
        return error.response?.data || { status: false, status_message: "Network error during withdrawal." };
      }
    },
    async updateSettings({ commit }, payload) {
      try {
        const response = await apiClient.post('/settings', payload);
        if (response.data.status && response.data.user) {
          commit('setUser', response.data.user); // Update full user object
        }
        return response.data; // { status, user, status_message? }
      } catch (error) {
        console.error("Update Settings Error:", error.response?.data || error.message);
        return error.response?.data || { status: false, status_message: "Network error updating settings." };
      }
    },
    async applyBonusCode({ commit }, payload) {
      try {
        const response = await apiClient.post('/deposit', payload); // Backend uses /deposit for bonus codes
        if (response.data.status && response.data.user) {
          commit('updateUserBalance', response.data.user.balance);
        }
        return response.data; // { status, user, status_message }
      } catch (error) {
        console.error("Apply Bonus Code Error:", error.response?.data || error.message);
        return error.response?.data || { status: false, status_message: "Network error applying bonus code." };
      }
    },
  },
  getters: {
    isAuthenticated: (state) => !!state.userSession,
    currentUser: (state) => state.user,
    isAdmin: (state) => state.user?.is_admin === true, // Explicitly check for true
    getSlots: (state) => state.slots,
    getSlotById: (state) => (id) => {
      return state.slots.find(slot => slot.id === Number(id));
    },
    getTables: (state) => state.tables,
    getTableById: (state) => (id) => {
      return state.tables.find(table => table.id === Number(table.id)); // Corrected: table.id
    },
  },
  modules: {},
});
