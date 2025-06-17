import { createStore } from 'vuex';
import axios from 'axios';
import apiService from '@/services/api';

export default createStore({
  state: {
    user: null,
    userSession: null, // Access token
    refreshToken: null, // Refresh token
    csrfToken: null,
    slots: [],
    slotsLoaded: false,
    currentSlotConfig: null,
    tables: [],
    tablesLoaded: false,
    currentTableConfig: null,
    globalError: null, // For global error notifications
    adminDashboardData: null,
    adminDashboardError: null,
    isAdminDataLoading: false, // For loading state
    isLoadingGlobal: false, // For global loading indicator
    adminUsers: [],
    adminUsersCurrentPage: 1,
    adminUsersTotalPages: 1,
    adminUsersPerPage: 20,
    adminUsersTotalCount: 0,
    isAdminUsersLoading: false,
    adminUsersError: null,
    isAuthenticated: false,
  },
  mutations: {
    setGlobalError(state, errorMessage) {
      state.globalError = errorMessage;
    },
    clearGlobalError(state) {
      state.globalError = null;
    },
    setUser(state, userData) {
      state.user = userData;
      state.isAuthenticated = !!userData;
    },
    setCsrfToken(state, token) {
      state.csrfToken = token;
    },
    setAuthTokens(state, tokens) {
      if (tokens && (tokens.accessToken || tokens.access_token)) {
        // Handle both naming conventions
        const accessToken = tokens.accessToken || tokens.access_token;
        const refreshToken = tokens.refreshToken || tokens.refresh_token;
        
        // Store in state
        state.userSession = accessToken;
        state.refreshToken = refreshToken;
        
        // Store in localStorage for persistence
        localStorage.setItem('userSession', accessToken);
        if (refreshToken) {
          localStorage.setItem('refreshToken', refreshToken);
        }
        
        // Also store with backend naming for compatibility
        localStorage.setItem('access_token', accessToken);
        if (refreshToken) {
          localStorage.setItem('refresh_token', refreshToken);
        }
        
        state.isAuthenticated = true;
      } else {
        // Clear tokens from state
        state.userSession = null;
        state.refreshToken = null;
        
        // Clear tokens from localStorage
        localStorage.removeItem('userSession');
        localStorage.removeItem('refreshToken');
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        
        state.isAuthenticated = false;
      }
    },
    clearAuth(state) {
      state.user = null;
      state.userSession = null;
      state.refreshToken = null;
      state.csrfToken = null;
      state.isAuthenticated = false;
      
      // Clear localStorage
      localStorage.removeItem('userSession');
      localStorage.removeItem('refreshToken');
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
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
    setAdminDashboardData(state, data) {
      state.adminDashboardData = data;
      state.adminDashboardError = null;
      state.isAdminDataLoading = false;
    },
    setAdminDashboardError(state, error) {
      state.adminDashboardData = null;
      state.adminDashboardError = error;
      state.isAdminDataLoading = false;
    },
    setAdminDataLoading(state) {
      state.isAdminDataLoading = true;
      state.adminDashboardError = null; // Clear previous error on new load
    },
    setGlobalLoading(state, isLoading) { // Generic setter
      state.isLoadingGlobal = isLoading;
    },
    startGlobalLoading(state) {
      state.isLoadingGlobal = true;
    },
    stopGlobalLoading(state) {
      state.isLoadingGlobal = false;
    },
    setAdminUsersLoading(state, isLoading) {
      state.isAdminUsersLoading = isLoading;
      state.adminUsersError = null;
    },
    setAdminUsersData(state, { users, page, pages, per_page, total }) {
      state.adminUsers = users;
      state.adminUsersCurrentPage = page;
      state.adminUsersTotalPages = pages;
      state.adminUsersPerPage = per_page;
      state.adminUsersTotalCount = total;
      state.isAdminUsersLoading = false;
      state.adminUsersError = null;
    },
    setAdminUsersError(state, error) {
      state.adminUsers = [];
      state.isAdminUsersLoading = false;
      state.adminUsersError = error;
    }
  },
  actions: {
    // --- Authentication with HTTP-Only Cookies ---
    async register({ dispatch, commit }, payload) {
      try {
        const response = await apiService.register(payload);
        const data = response.data;
        if (data.status && data.user) {
          commit('setUser', data.user);
          if (data.csrf_token) {
            commit('setCsrfToken', data.csrf_token);
          }
        }
        return data;
      } catch (error) {
        // The interceptor in api.js will handle generic network errors or 401s.
        // Specific error handling for registration (e.g., email already exists) can remain here.
        console.error("Registration Error:", error.response?.data || error.message);
        return error.response?.data || { status: false, status_message: "Network error during registration." };
      }
    },
    
    async login({ commit }, payload) {
      commit('startGlobalLoading');
      try {
        const response = await apiService.login(payload);
        const data = response.data;
        if (data.status && data.user) {
          commit('setUser', data.user);
          if (data.csrf_token) {
            commit('setCsrfToken', data.csrf_token);
          }
        }
        return data;
      } catch (error) {
        const errData = error.response?.data;
        const defaultMessage = "Login failed. Please try again later.";
        if (error.response && error.response.status !== 401) {
          commit('setGlobalError', errData?.status_message || defaultMessage);
        }
        return errData || { status: false, status_message: defaultMessage };
      } finally {
        commit('stopGlobalLoading');
      }
    },
    
    async refreshToken({ commit }) {
      try {
        const response = await apiService.refreshToken();
        const data = response.data;
        if (data.status) {
          if (data.csrf_token) {
            commit('setCsrfToken', data.csrf_token);
          }
          return { status: true };
        } else {
          commit('clearAuth');
          return { status: false, status_message: data.status_message || "Session refresh failed." };
        }
      } catch (error) {
        // Logout will be dispatched by the interceptor in api.js
        console.error("Token Refresh Action Error:", error.response?.data || error.message);
        commit('clearAuth');
        return { status: false, status_message: "Session expired. Please log in again." };
      }
    },
    
    async logout({ commit }) {
      try {
        await apiService.logout();
      } catch (error) {
        console.error("Logout error:", error);
      } finally {
        commit('clearAuth');
      }
    },
    
    async loadSession({ dispatch, commit }) {
      // For HTTP-only cookies, we don't check localStorage
      // Instead, try to fetch user profile which will validate cookies
      commit('startGlobalLoading');
      try {
        // fetchUserProfile will use the new apiService which has interceptors.
        // If token is expired, interceptor should try to refresh.
        // If refresh fails, interceptor should logout.
        await dispatch('fetchUserProfile');
      } catch (error) {
        // If fetchUserProfile itself fails (e.g. network error not caught by interceptor)
        // this catch might not be strictly necessary if interceptor handles all logout cases.
        console.error("Load session error:", error);
      } finally {
        commit('stopGlobalLoading');
      }
    },
    async fetchUserProfile({ commit }) {
      try {
        const response = await apiService.getUserProfile();
        const data = response.data;
        if (data.status && data.user) {
          commit('setUser', data.user);
          return data;
        } else {
          commit('clearAuth');
          return { status: false, status_message: data.status_message || "Failed to fetch user profile." };
        }
      } catch (error) {
        const errData = error.response?.data;
        if (error.response?.status === 401) {
          commit('clearAuth');
        }
        console.error("Error fetching user profile:", errData || error.message);
        return errData || { status: false, status_message: "Failed to load user profile." };
      }
    },
    
    async setAuthTokensAndFetchUser({ commit, dispatch }, tokens) {
      // For HTTP-only cookies, we don't need to handle tokens manually
      // Just fetch user profile to validate cookies
      return await dispatch('fetchUserProfile');
    },
    
    async getCsrfToken({ commit }) {
      try {
        const response = await apiService.getCsrfToken();
        if (response.data.status && response.data.csrf_token) {
          commit('setCsrfToken', response.data.csrf_token);
          return response.data.csrf_token;
        }
      } catch (error) {
        console.error("Error getting CSRF token:", error);
      }
      return null;
    },

    // --- Game Data ---
    // Placeholder for other actions that need to be refactored
    // Example:
    async fetchSlots({ commit }) {
      try {
        // const response = await apiClient.get('/slots'); // OLD
        const response = await apiService.getSlots(); // NEW - assuming getSlots method in apiService
        if (response.data.status && Array.isArray(response.data.slots)) {
          commit('setSlots', response.data.slots);
          return response.data;
        } else {
          const errorMessage = response.data.status_message || 'Failed to parse slots data.';
          commit('setGlobalError', errorMessage);
          return { status: false, status_message: errorMessage };
        }
      } catch (error) {
        const errData = error.response?.data;
        const defaultMessage = "Failed to load slot machines. Please try again.";
        if (error.response && error.response.status !== 401) { // Check error.response exists
          commit('setGlobalError', errData?.status_message || defaultMessage);
        }
        return { status: false, status_message: errData?.status_message || defaultMessage };
      }
    },
    async fetchSlotConfig({ commit, state, dispatch }, slotId) {
      if (!state.slotsLoaded) {
        const fetchResult = await dispatch('fetchSlots'); // Already uses apiService if fetchSlots is updated
        if (!fetchResult || fetchResult.status === false || !fetchResult.slots) { // Adjusted condition
            return null;
        }
      }
      const slot = state.slots.find(s => s.id === Number(slotId));
      if (slot) {
        commit('setCurrentSlotConfig', slot);
        return slot;
      } else {
        return null;
      }
    },
    async fetchTables({ commit }) {
      try {
        // const response = await apiClient.get('/tables'); // OLD
        const response = await apiService.getTables(); // NEW - assuming getTables method in apiService
        if (response.data.status && Array.isArray(response.data.tables)) {
          commit('setTables', response.data.tables);
          return response.data;
        } else {
           const errorMessage = response.data.status_message || 'Failed to parse tables data.';
           return { status: false, status_message: errorMessage };
        }
      } catch (error) {
        const errData = error.response?.data;
        const defaultMessage = "Failed to load tables. Please try again.";
        if (error.response && error.response.status !== 401) { // Check error.response exists
           // commit('setGlobalError', errData?.status_message || defaultMessage);
        }
        return { status: false, status_message: errData?.status_message || defaultMessage };
      }
    },
    async fetchTableConfig({ commit, state, dispatch }, tableId) {
      if (!state.tablesLoaded) {
        const fetchResult = await dispatch('fetchTables'); // Already uses apiService if fetchTables is updated
        if (!fetchResult || fetchResult.status === false || !fetchResult.tables) { // Adjusted condition
            return null;
        }
      }
      const table = state.tables.find(t => t.id === Number(tableId));
      if (table) {
        commit('setCurrentTableConfig', table);
        return table;
      } else {
        return null;
      }
    },

    // --- Gameplay Actions ---
    async endSession({commit}) {
      try {
        // const response = await apiClient.post('/end_session', {}); // OLD
        const response = await apiService.endSession({}); // NEW - assuming endSession method in apiService
        return response.data;
      } catch (error) {
        const errData = error.response?.data;
        const defaultMessage = "Network error ending game session.";
        if (error.response && error.response.status !== 401) { // Check error.response exists
            commit('setGlobalError', errData?.status_message || defaultMessage);
        }
        return errData || { status: false, status_message: defaultMessage };
      }
    },
    async joinGame({ commit }, payload) {
      try {
        payload.game_type = payload.game_type || (payload.slot_id ? 'slot' : (payload.table_id ? 'blackjack' : 'unknown'));
        // const response = await apiClient.post('/join', payload); // OLD
        const response = await apiService.joinGame(payload); // NEW - assuming joinGame method in apiService
        return response.data;
      } catch (error) {
        const errData = error.response?.data;
        const defaultMessage = "Network error joining game.";
        if (error.response && error.response.status !== 401) { // Check error.response exists
            commit('setGlobalError', errData?.status_message || defaultMessage);
        }
        return errData || { status: false, status_message: defaultMessage };
      }
    },
    async spin({ commit }, payload) {
      try {
        const betAmount = parseInt(payload.bet_amount, 10);
        if (isNaN(betAmount) || betAmount <= 0) {
            return { status: false, status_message: "Invalid bet amount."};
        }
        // const response = await apiClient.post('/spin', { bet_amount: betAmount }); // OLD
        const response = await apiService.spin({ bet_amount: betAmount }); // NEW - assuming spin method in apiService
        if (response.data.status && response.data.user) {
          commit('updateUserBalance', response.data.user.balance);
        }
        return response.data;
      } catch (error) {
        const errData = error.response?.data;
        const defaultMessage = "Network error during spin.";
         if (error.response && error.response.status !== 400 && error.response.status !== 401 ) { // Check error.response
            commit('setGlobalError', errData?.status_message || defaultMessage);
        }
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
        // const response = await apiClient.post('/join_blackjack', { table_id: tableId, bet_amount: betAmount }); // OLD
        const response = await apiService.joinBlackjack({ table_id: tableId, bet_amount: betAmount }); // NEW
        if (response.data.status && response.data.user) {
          commit('updateUserBalance', response.data.user.balance);
        }
        return response.data;
      } catch (error) {
        const errData = error.response?.data;
        const defaultMessage = "Network error joining blackjack.";
        if (error.response && error.response.status !== 400 && error.response.status !== 401) { // Check error.response
            commit('setGlobalError', errData?.status_message || defaultMessage);
        }
        return errData || { status: false, status_message: defaultMessage };
      }
    },
    async blackjackAction({ commit }, payload) {
      try {
        // const response = await apiClient.post('/blackjack_action', payload); // OLD
        const response = await apiService.blackjackAction(payload); // NEW
        if (response.data.status && response.data.user) {
          commit('updateUserBalance', response.data.user.balance);
        }
        return response.data;
      } catch (error) {
        const errData = error.response?.data;
        const defaultMessage = "Network error during blackjack action.";
        if (error.response && error.response.status !== 400 && error.response.status !== 401) { // Check error.response
            commit('setGlobalError', errData?.status_message || defaultMessage);
        }
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
        // const response = await apiClient.post('/withdraw', { // OLD
        //     amount_sats: amountSats,
        //     withdraw_wallet_address: payload.withdraw_wallet_address
        // });
        const response = await apiService.withdraw({ // NEW
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
        if (error.response && error.response.status !== 400 && error.response.status !== 401) { // Check error.response
            commit('setGlobalError', errData?.status_message || defaultMessage);
        }
        return errData || { status: false, status_message: defaultMessage };
      }
    },
    async updateSettings({ commit }, payload) {
      try {
        // const response = await apiClient.post('/settings', payload); // OLD
        const response = await apiService.updateSettings(payload); // NEW
        if (response.data.status && response.data.user) {
          commit('setUser', response.data.user);
        }
        return response.data;
      } catch (error) {
        const errData = error.response?.data;
        const defaultMessage = "Network error updating settings.";
        if (error.response && error.response.status !== 400 && error.response.status !== 401 && error.response.status !== 409) { // Check error.response
            commit('setGlobalError', errData?.status_message || defaultMessage);
        }
        return errData || { status: false, status_message: defaultMessage };
      }
    },
    async applyBonusCode({ commit }, payload) {
      try {
        // const response = await apiClient.post('/deposit', payload); // OLD
        const response = await apiService.applyBonusCode(payload); // NEW
        if (response.data.status && response.data.user) {
          commit('updateUserBalance', response.data.user.balance);
        }
        return response.data;
      } catch (error) {
        const errData = error.response?.data;
        const defaultMessage = "Network error applying bonus code.";
        if (error.response && error.response.status !== 400 && error.response.status !== 401) { // Check error.response
            commit('setGlobalError', errData?.status_message || defaultMessage);
        }
        return errData || { status: false, status_message: defaultMessage };
      }
    },
    async fetchAdminDashboardData({ commit }) {
      commit('setAdminDataLoading');
      try {
        // const response = await apiClient.get('/admin/dashboard'); // OLD
        const response = await apiService.fetchAdminDashboardData(); // NEW
        if (response.data.status && response.data.dashboard_data) {
          commit('setAdminDashboardData', response.data.dashboard_data);
          return response.data.dashboard_data;
        } else {
          const errorMsg = response.data.status_message || 'Failed to fetch admin dashboard data.';
          commit('setAdminDashboardError', errorMsg);
          return null;
        }
      } catch (error) {
        const errorMsg = error.response?.data?.status_message || error.message || 'Network error fetching admin dashboard data.';
        commit('setAdminDashboardError', errorMsg);
        return null;
      }
    },
    async fetchAdminUsers({ commit, state }, page = 1) {
      commit('setAdminUsersLoading', true);
      try {
        // const response = await apiClient.get(`/admin/users?page=${page}&per_page=${state.adminUsersPerPage}`); // OLD
        const response = await apiService.fetchAdminUsers(page, state.adminUsersPerPage); // NEW
        if (response.data.status && response.data.users && response.data.users.items) { // Ensure this matches apiService response
          commit('setAdminUsersData', {
            users: response.data.users.items, // Or response.data.items if structure changed
            page: response.data.users.page,
            pages: response.data.users.pages,
            per_page: response.data.users.per_page,
            total: response.data.users.total
          });
          return response.data.users;
        } else {
          const errorMsg = response.data.status_message || 'Failed to fetch admin users list.';
          commit('setAdminUsersError', errorMsg);
          return null;
        }
      } catch (error) {
        const errorMsg = error.response?.data?.status_message || error.message || 'Network error fetching admin users.';
        commit('setAdminUsersError', errorMsg);
        return null;
      }
    }
  },
  getters: {
    isAuthenticated: (state) => state.isAuthenticated,
    currentUser: (state) => state.user,
    isAdmin: (state) => state.user?.is_admin === true,
    getSlots: (state) => state.slots,
    getSlotById: (state) => (id) => {
      return state.slots.find(slot => slot.id === Number(id));
    },
    getTables: (state) => state.tables,
    getTableById: (state) => (id) => {
      return state.tables.find(table => table.id === Number(id));
    },
  },
  modules: {},
});
