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
    setGlobalError(state, errorPayload) { // Can be string or object
      state.globalError = errorPayload;
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
        commit('setGlobalError', error); // Error object from interceptor
        console.error("Registration Error:", error);
        // Return the error structure so UI can potentially use it if needed
        // Or rely solely on globalError for display. For now, rethrow.
        throw error;
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
        // Interceptor handles 401 (UNAUTHENTICATED) for refresh.
        // Other errors (like invalid credentials if not 401, or network errors) will be caught here.
        commit('setGlobalError', error);
        console.error("Login Error:", error);
        throw error;
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
          // This path might be less likely if interceptor handles failed refresh by logging out
          commit('clearAuth');
          commit('setGlobalError', { message: data.status_message || "Session refresh failed." });
          return { status: false, status_message: data.status_message || "Session refresh failed." };
        }
      } catch (error) {
        // Interceptor should handle logout on refresh failure.
        // This catch is for unexpected errors during the refresh call itself.
        commit('clearAuth');
        commit('setGlobalError', error);
        console.error("Token Refresh Action Error:", error);
        throw error; // Rethrow to propagate
      }
    },
    
    async logout({ commit }) {
      try {
        await apiService.logout();
      } catch (error) {
        // Even if logout API call fails, clear client-side auth
        console.error("Logout API error:", error);
        commit('setGlobalError', error); // Show potential error from API
      } finally {
        commit('clearAuth');
      }
    },
    
    async loadSession({ dispatch, commit }) {
      commit('startGlobalLoading');
      try {
        await dispatch('fetchUserProfile');
      } catch (error) {
        // fetchUserProfile will commit its own errors if any.
        // The interceptor in api.js handles refresh/logout for UNAUTHENTICATED.
        // This catch is for other errors from fetchUserProfile if not already handled.
        console.error("Load session error (possibly already handled):", error);
        // No specific commit('setGlobalError', error) here as fetchUserProfile should do it.
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
          // This case might indicate a soft error from backend (status: false but not an HTTP error status)
          commit('clearAuth'); // Should be handled by interceptor if it was 401
          commit('setGlobalError', { message: data.status_message || "Failed to fetch user profile." });
          return { status: false, status_message: data.status_message || "Failed to fetch user profile." };
        }
      } catch (error) {
        // Interceptor handles 401/UNAUTHENTICATED.
        // This catch is for other errors (network, non-401 structured errors).
        commit('setGlobalError', error);
        // clearAuth is typically done by the interceptor for UNAUTHENTICATED.
        // If error is NOT UNAUTHENTICATED, we might not want to clearAuth.
        // Example: if it's a 500 error, user is still technically logged in.
        // The interceptor's logout for UNAUTHENTICATED is the primary auth clearing mechanism.
        console.error("Error fetching user profile:", error);
        throw error; // Rethrow
      }
    },
    
    async setAuthTokensAndFetchUser({ commit, dispatch }, tokens) {
      // For HTTP-only cookies, this action might be less relevant for setting tokens,
      // but fetching user profile is still key.
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
        commit('setGlobalError', error);
        console.error("Error getting CSRF token:", error);
        throw error; // Rethrow
      }
      return null; // Should not be reached if error is thrown
    },

    // --- Game Data ---
    async fetchSlots({ commit }) {
      try {
        const response = await apiService.getSlots();
        if (response.data.status && Array.isArray(response.data.slots)) {
          commit('setSlots', response.data.slots);
          return response.data;
        } else {
          // Soft error from backend
          const errorMessage = response.data.status_message || 'Failed to parse slots data.';
          commit('setGlobalError', { message: errorMessage, errorCode: response.data.error_code });
          return { status: false, status_message: errorMessage };
        }
      } catch (error) {
        commit('setGlobalError', error);
        console.error("Fetch slots error:", error);
        throw error;
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
        const response = await apiService.getTables();
        if (response.data.status && Array.isArray(response.data.tables)) {
          commit('setTables', response.data.tables);
          return response.data;
        } else {
           const errorMessage = response.data.status_message || 'Failed to parse tables data.';
           commit('setGlobalError', { message: errorMessage, errorCode: response.data.error_code });
           return { status: false, status_message: errorMessage };
        }
      } catch (error) {
        commit('setGlobalError', error);
        console.error("Fetch tables error:", error);
        throw error;
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
        const response = await apiService.endSession({});
        return response.data;
      } catch (error) {
        commit('setGlobalError', error);
        console.error("End session error:", error);
        throw error;
      }
    },
    async joinGame({ commit }, payload) {
      try {
        payload.game_type = payload.game_type || (payload.slot_id ? 'slot' : (payload.table_id ? 'blackjack' : 'unknown'));
        const response = await apiService.joinGame(payload);
        return response.data;
      } catch (error) {
        commit('setGlobalError', error);
        console.error("Join game error:", error);
        throw error;
      }
    },
    async spin({ commit }, payload) {
      try {
        const betAmount = parseInt(payload.bet_amount, 10);
        if (isNaN(betAmount) || betAmount <= 0) {
            // This is client-side validation, handle it before API call
            const clientError = { isStructuredError: false, message: "Invalid bet amount."};
            commit('setGlobalError', clientError);
            throw clientError; // Or return structure expected by UI
        }
        const response = await apiService.spin({ bet_amount: betAmount });
        if (response.data.status && response.data.user) {
          commit('updateUserBalance', response.data.user.balance);
        }
        return response.data;
      } catch (error) {
        // If error is from client-side validation above, it will be caught here too.
        // Ensure it's not double-committed or override if necessary.
        if (!error.isStructuredError && error.message === "Invalid bet amount.") {
            // Already handled by client-side validation, re-throw if necessary
        } else {
            commit('setGlobalError', error);
        }
        console.error("Spin error:", error);
        throw error;
      }
    },
    async joinBlackjack({ commit }, payload) {
      try {
        const betAmount = parseInt(payload.bet_amount, 10);
        const tableId = parseInt(payload.table_id, 10);
        if (isNaN(betAmount) || betAmount <= 0) {
            const clientError = { isStructuredError: false, message: "Invalid bet amount."};
            commit('setGlobalError', clientError);
            throw clientError;
        }
        if (isNaN(tableId) || tableId <= 0) {
            const clientError = { isStructuredError: false, message: "Invalid table ID."};
            commit('setGlobalError', clientError);
            throw clientError;
        }
        const response = await apiService.joinBlackjack({ table_id: tableId, bet_amount: betAmount });
        if (response.data.status && response.data.user) {
          commit('updateUserBalance', response.data.user.balance);
        }
        return response.data;
      } catch (error) {
        if (!error.isStructuredError && (error.message === "Invalid bet amount." || error.message === "Invalid table ID.")) {
            // Client-side validation already handled
        } else {
            commit('setGlobalError', error);
        }
        console.error("Join blackjack error:", error);
        throw error;
      }
    },
    async blackjackAction({ commit }, payload) {
      try {
        const response = await apiService.blackjackAction(payload);
        if (response.data.status && response.data.user) {
          commit('updateUserBalance', response.data.user.balance);
        }
        return response.data;
      } catch (error) {
        commit('setGlobalError', error);
        console.error("Blackjack action error:", error);
        throw error;
      }
    },

    // --- User Account Actions ---
    async withdraw({ commit }, payload) {
      try {
        const amountSats = parseInt(payload.amount_sats || payload.amount, 10);
        if (isNaN(amountSats) || amountSats <= 0) {
            const clientError = { isStructuredError: false, message: "Invalid withdrawal amount."};
            commit('setGlobalError', clientError);
            throw clientError;
        }
        const response = await apiService.withdraw({
            amount: amountSats, // Ensure consistent naming with API expectations
            address: payload.withdraw_wallet_address // Ensure consistent naming
        });
        if (response.data.status && response.data.user) {
          commit('updateUserBalance', response.data.user.balance);
        }
        return response.data;
      } catch (error) {
         if (!error.isStructuredError && error.message === "Invalid withdrawal amount.") {
            // Client-side validation
        } else {
            commit('setGlobalError', error);
        }
        console.error("Withdraw error:", error);
        throw error;
      }
    },
    async updateSettings({ commit }, payload) {
      try {
        const response = await apiService.updateSettings(payload);
        if (response.data.status && response.data.user) {
          commit('setUser', response.data.user);
        }
        return response.data;
      } catch (error) {
        commit('setGlobalError', error);
        console.error("Update settings error:", error);
        throw error;
      }
    },
    // Assuming applyBonusCode is a distinct endpoint, if it's part of deposit, it needs adjustment.
    // For now, treating as if apiService.applyBonusCode exists.
    // If it's part of deposit, the deposit action should be refactored.
    async deposit({ commit }, payload) { // Renamed from applyBonusCode to deposit for clarity
      try {
        const response = await apiService.deposit(payload); // Assumes apiService.deposit exists
        if (response.data.status && response.data.user) {
          commit('updateUserBalance', response.data.user.balance);
        }
        // If deposit returns bonus info, handle it here or ensure response.data is sufficient
        return response.data;
      } catch (error) {
        commit('setGlobalError', error);
        console.error("Deposit error:", error);
        throw error;
      }
    },
    async fetchAdminDashboardData({ commit }) {
      commit('setAdminDataLoading');
      try {
        const response = await apiService.fetchAdminDashboardData();
        if (response.data.status && response.data.dashboard_data) {
          commit('setAdminDashboardData', response.data.dashboard_data);
          return response.data.dashboard_data;
        } else {
          const errorMsg = response.data.status_message || 'Failed to fetch admin dashboard data.';
          // Create a structured-like error for consistency if backend returns soft error
          const customError = { isStructuredError: true, message: errorMsg, errorCode: response.data.error_code || 'ADMIN_DATA_ERROR' };
          commit('setAdminDashboardError', customError.message); // old mutation expects string
          commit('setGlobalError', customError); // new global error can take object
          return null;
        }
      } catch (error) {
        commit('setGlobalError', error); // Handles structured errors from interceptor
        commit('setAdminDashboardError', error.message || 'Network error'); // old mutation
        console.error("Fetch admin dashboard error:", error);
        return null; // Or throw error
      }
    },
    async fetchAdminUsers({ commit, state }, page = 1) {
      commit('setAdminUsersLoading', true);
      try {
        const response = await apiService.fetchAdminUsers(page, state.adminUsersPerPage);
        if (response.data.status && response.data.users && response.data.users.items) {
          commit('setAdminUsersData', {
            users: response.data.users.items,
            page: response.data.users.page,
            pages: response.data.users.pages,
            per_page: response.data.users.per_page,
            total: response.data.users.total
          });
          return response.data.users;
        } else {
          const errorMsg = response.data.status_message || 'Failed to fetch admin users list.';
          const customError = { isStructuredError: true, message: errorMsg, errorCode: response.data.error_code || 'ADMIN_USERS_ERROR' };
          commit('setAdminUsersError', customError.message); // old mutation
          commit('setGlobalError', customError);
          return null;
        }
      } catch (error) {
        commit('setGlobalError', error);
        commit('setAdminUsersError', error.message || 'Network error'); // old mutation
        console.error("Fetch admin users error:", error);
        return null; // Or throw error
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
