import { createStore } from 'vuex';
import axios from 'axios';

// --- API Client Setup ---
const apiClient = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json',
  },
});

let storeInstance; // To be set later
export const setStoreForApiClient = (store) => {
  storeInstance = store;
};

// Request interceptor for API token
apiClient.interceptors.request.use(config => {
  const token = localStorage.getItem('userSession');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
}, error => {
  return Promise.reject(error);
});

// Response interceptor for handling 401 and token refresh
apiClient.interceptors.response.use(response => {
  return response;
}, async error => {
  const originalRequest = error.config;
  if (error.response && error.response.status === 401 && !originalRequest._retry && storeInstance) {
    originalRequest._retry = true;
    try {
      const refreshData = await storeInstance.dispatch('refreshToken');
      if (refreshData && refreshData.access_token) {
        originalRequest.headers.Authorization = `Bearer ${refreshData.access_token}`;
        return apiClient(originalRequest);
      } else {
        await storeInstance.dispatch('logout');
        return Promise.reject(error);
      }
    } catch (refreshError) {
      await storeInstance.dispatch('logout');
      return Promise.reject(refreshError);
    }
  }
  return Promise.reject(error);
});

export default createStore({
  state: {
    user: null,
    userSession: localStorage.getItem('userSession') || null,
    refreshToken: localStorage.getItem('refreshToken') || null,
    slots: [],
    slotsLoaded: false,
    currentSlotConfig: null,
    tables: [],
    tablesLoaded: false,
    currentTableConfig: null,
    globalError: null, // For global error notifications
  },
  mutations: {
    setGlobalError(state, errorMessage) {
      state.globalError = errorMessage;
      // Optionally, set a timer to clear it
      // setTimeout(() => { state.globalError = null; }, 5000);
    },
    clearGlobalError(state) {
      state.globalError = null;
    },
    setUser(state, userData) {
      state.user = userData;
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
    async register({ dispatch }, payload) {
      try {
        const response = await apiClient.post('/register', payload);
        const data = response.data;
        if (data.status && data.access_token && data.refresh_token) {
          dispatch('setAuthTokensAndFetchUser', { accessToken: data.access_token, refreshToken: data.refresh_token });
        }
        return data;
      } catch (error) {
        // Assuming specific error messages for registration are handled by the component
        console.error("Registration Error:", error.response?.data || error.message);
        return error.response?.data || { status: false, status_message: "Network error during registration." };
      }
    },
    async login({ dispatch, commit }, payload) { // Added commit
      try {
        const response = await apiClient.post('/login', payload);
        const data = response.data;
        if (data.status && data.access_token && data.refresh_token) {
          dispatch('setAuthTokensAndFetchUser', { accessToken: data.access_token, refreshToken: data.refresh_token });
        }
        return data;
      } catch (error) {
        const errData = error.response?.data;
        const defaultMessage = "Login failed. Please try again later.";
        if (error.response?.status !== 401) {
            commit('setGlobalError', errData?.status_message || defaultMessage);
        }
        console.error("Login Error:", errData || error.message);
        return errData || { status: false, status_message: defaultMessage };
      }
    },
    async setAuthTokensAndFetchUser({ commit, dispatch }, { accessToken, refreshToken }) {
        commit('setAuthTokens', { accessToken, refreshToken });
        if (accessToken) {
            await dispatch('fetchUserProfile');
        }
    },
    async refreshToken({ commit, state, dispatch }) {
      if (!state.refreshToken) {
        await dispatch('logout');
        return { status: false, status_message: "No refresh token available. Logged out." };
      }
      try {
        const refreshApiClient = axios.create({ baseURL: '/api' });
        const response = await refreshApiClient.post('/refresh', {}, {
          headers: { Authorization: `Bearer ${state.refreshToken}` }
        });
        const data = response.data;
        if (data.status && data.access_token) {
          commit('setAuthTokens', { accessToken: data.access_token, refreshToken: state.refreshToken });
          return { status: true, access_token: data.access_token };
        } else {
          await dispatch('logout');
          return { status: false, status_message: data.status_message || "Session refresh failed. Logged out." };
        }
      } catch (error) {
        console.error("Token Refresh Error:", error.response?.data || error.message);
        await dispatch('logout');
        return { status: false, status_message: "Session expired. Please log in again." };
      }
    },
    async logout({ commit, state }) {
      const accessToken = state.userSession;
      const refreshToken = state.refreshToken;
      commit('clearAuth');
      try {
        if (accessToken) {
          await apiClient.post('/logout', {});
        }
        if (refreshToken) {
          const tempApiClient = axios.create({ baseURL: '/api' });
          await tempApiClient.post('/logout2', {}, { headers: { Authorization: `Bearer ${refreshToken}` } });
        }
        return { status: true, status_message: "Logged out successfully from server." };
      } catch (error) {
        console.warn("Server Logout Error:", error.response?.data || error.message);
        return { status: true, status_message: "Logged out locally. Server session might still be active." };
      }
    },
    async loadSession({ dispatch }) {
      const accessToken = localStorage.getItem('userSession');
      if (accessToken) {
        await dispatch('fetchUserProfile');
      } else {
        dispatch('logout');
      }
    },
    async fetchUserProfile({ commit }) {
      try {
        const response = await apiClient.get('/me');
        if (response.data.status) {
          commit('setUser', response.data.user);
          return response.data.user;
        } else {
          console.warn("Failed to fetch user profile:", response.data.status_message);
          return null;
        }
      } catch (error) {
        console.error("Error fetching user profile:", error.response?.data || error.message);
        return null;
      }
    },

    // --- Game Data ---
    async fetchSlots({ commit }) { // Removed state from params as it's not used directly before try
      try {
        const response = await apiClient.get('/slots');
        if (response.data.status && Array.isArray(response.data.slots)) {
          commit('setSlots', response.data.slots);
          return response.data;
        } else {
          const errorMessage = response.data.status_message || 'Failed to parse slots data.';
          commit('setGlobalError', errorMessage);
          console.error('Error fetching slots:', errorMessage);
          return { status: false, status_message: errorMessage };
        }
      } catch (error) {
        const errData = error.response?.data;
        const defaultMessage = "Failed to load slot machines. Please try again.";
        if (error.response?.status !== 401) {
          commit('setGlobalError', errData?.status_message || defaultMessage);
        }
        console.error('Network error fetching slots:', errData || error.message);
        return { status: false, status_message: errData?.status_message || defaultMessage };
      }
    },
    async fetchSlotConfig({ commit, state, dispatch }, slotId) {
      if (!state.slotsLoaded) {
        const fetchResult = await dispatch('fetchSlots');
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
        return null;
      }
    },
    async fetchTables({ commit }) { // Removed state from params
      try {
        const response = await apiClient.get('/tables');
        if (response.data.status && Array.isArray(response.data.tables)) {
          commit('setTables', response.data.tables);
          return response.data;
        } else {
           const errorMessage = response.data.status_message || 'Failed to parse tables data.';
           // Consider if this specific error should be global or handled by component
           // commit('setGlobalError', errorMessage);
           console.error('Error fetching tables:', errorMessage);
           return { status: false, status_message: errorMessage };
        }
      } catch (error) {
        const errData = error.response?.data;
        const defaultMessage = "Failed to load tables. Please try again.";
        // if (error.response?.status !== 401) { // Example if global error is desired here too
        //   commit('setGlobalError', errData?.status_message || defaultMessage);
        // }
        console.error('Network error fetching tables:', errData || error.message);
        return { status: false, status_message: errData?.status_message || defaultMessage };
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
    async endSession({commit}) { // Added commit (not used yet, but good practice if global errors needed)
      try {
        const response = await apiClient.post('/end_session', {});
        return response.data;
      } catch (error) {
        const errData = error.response?.data;
        const defaultMessage = "Network error ending game session.";
        if (error.response?.status !== 401) {
            commit('setGlobalError', errData?.status_message || defaultMessage);
        }
        console.error("End Session Error:", errData || error.message);
        return errData || { status: false, status_message: defaultMessage };
      }
    },
    async joinGame({ commit }, payload) {
      try {
        payload.game_type = payload.game_type || (payload.slot_id ? 'slot' : (payload.table_id ? 'blackjack' : 'unknown'));
        const response = await apiClient.post('/join', payload);
        return response.data;
      } catch (error) {
        const errData = error.response?.data;
        const defaultMessage = "Network error joining game.";
        if (error.response?.status !== 401) {
            commit('setGlobalError', errData?.status_message || defaultMessage);
        }
        console.error("Join Game Error:", errData || error.message);
        return errData || { status: false, status_message: defaultMessage };
      }
    },
    async spin({ commit }, payload) {
      try {
        const betAmount = parseInt(payload.bet_amount, 10);
        if (isNaN(betAmount) || betAmount <= 0) {
            return { status: false, status_message: "Invalid bet amount."};
        }
        const response = await apiClient.post('/spin', { bet_amount: betAmount });
        if (response.data.status && response.data.user) {
          commit('updateUserBalance', response.data.user.balance);
        }
        return response.data;
      } catch (error) {
        const errData = error.response?.data;
        const defaultMessage = "Network error during spin.";
         if (error.response?.status !== 400 && error.response?.status !== 401 ) { // 400 might be "insufficient balance"
            commit('setGlobalError', errData?.status_message || defaultMessage);
        }
        console.error("Spin Error:", errData || error.message);
        return errData || { status: false, status_message: defaultMessage };
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
        }
        return response.data;
      } catch (error) {
        const errData = error.response?.data;
        const defaultMessage = "Network error joining blackjack.";
        if (error.response?.status !== 400 && error.response?.status !== 401) { // 400 might be validation error
            commit('setGlobalError', errData?.status_message || defaultMessage);
        }
        console.error("Join Blackjack Error:", errData || error.message);
        return errData || { status: false, status_message: defaultMessage };
      }
    },
    async blackjackAction({ commit }, payload) {
      try {
        const response = await apiClient.post('/blackjack_action', payload);
        if (response.data.status && response.data.user) {
          commit('updateUserBalance', response.data.user.balance);
        }
        return response.data;
      } catch (error) {
        const errData = error.response?.data;
        const defaultMessage = "Network error during blackjack action.";
        if (error.response?.status !== 400 && error.response?.status !== 401) { // 400 might be validation error
            commit('setGlobalError', errData?.status_message || defaultMessage);
        }
        console.error("Blackjack Action Error:", errData || error.message);
        return errData || { status: false, status_message: defaultMessage };
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
        return response.data;
      } catch (error) {
        const errData = error.response?.data;
        const defaultMessage = "Network error during withdrawal.";
        if (error.response?.status !== 400 && error.response?.status !== 401) { // 400 insufficient funds
            commit('setGlobalError', errData?.status_message || defaultMessage);
        }
        console.error("Withdraw Error:", errData || error.message);
        return errData || { status: false, status_message: defaultMessage };
      }
    },
    async updateSettings({ commit }, payload) {
      try {
        const response = await apiClient.post('/settings', payload);
        if (response.data.status && response.data.user) {
          commit('setUser', response.data.user);
        }
        return response.data;
      } catch (error)_ { // Typo here, should be (error)
        const errData = error.response?.data;
        const defaultMessage = "Network error updating settings.";
        if (error.response?.status !== 400 && error.response?.status !== 401 && error.response?.status !== 409) { // 409 email exists
            commit('setGlobalError', errData?.status_message || defaultMessage);
        }
        console.error("Update Settings Error:", errData || error.message);
        return errData || { status: false, status_message: defaultMessage };
      }
    },
    async applyBonusCode({ commit }, payload) {
      try {
        const response = await apiClient.post('/deposit', payload);
        if (response.data.status && response.data.user) {
          commit('updateUserBalance', response.data.user.balance);
        }
        return response.data;
      } catch (error) {
        const errData = error.response?.data;
        const defaultMessage = "Network error applying bonus code.";
        if (error.response?.status !== 400 && error.response?.status !== 401) { // 400 invalid code
            commit('setGlobalError', errData?.status_message || defaultMessage);
        }
        console.error("Apply Bonus Code Error:", errData || error.message);
        return errData || { status: false, status_message: defaultMessage };
      }
    },
  },
  getters: {
    isAuthenticated: (state) => !!state.userSession,
    currentUser: (state) => state.user,
    isAdmin: (state) => state.user?.is_admin === true,
    getSlots: (state) => state.slots,
    getSlotById: (state) => (id) => {
      return state.slots.find(slot => slot.id === Number(id));
    },
    getTables: (state) => state.tables,
    getTableById: (state) => (id) => {
      return state.tables.find(table => table.id === Number(table.id));
    },
  },
  modules: {},
});
