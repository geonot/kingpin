import { createStore } from 'vuex';
import axios from 'axios'; // Keep for /logout2 or other direct calls if necessary
import apiService from '@/services/api';

export default createStore({
  state: {
    user: null,
    accessToken: null, // Renamed from userSession, removed localStorage
    // refreshToken is no longer stored in Vuex state or localStorage
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
    setAuthTokens(state, { accessToken }) { // refreshToken parameter removed
      state.accessToken = accessToken;
      // localStorage interaction for accessToken removed
      // localStorage interaction for refreshToken removed
    },
    clearAuth(state) {
      state.user = null;
      state.accessToken = null;
      // refreshToken state was already removed
      // localStorage interaction for userSession (now accessToken) removed
      // localStorage interaction for refreshToken removed
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
    // --- Authentication ---
    async register({ dispatch }, payload) {
      try {
        const response = await apiService.register(payload); // Use apiService
        const data = response.data;
        // refreshToken from response is no longer handled here, HttpOnly cookie set by backend
        if (data.status && data.access_token) {
          dispatch('setAuthTokensAndFetchUser', { accessToken: data.access_token });
        }
        return data;
      } catch (error) {
        console.error("Registration Error:", error.response?.data || error.message);
        // The interceptor in api.js will handle generic network errors or 401s.
        // Specific error handling for registration (e.g., email already exists) can remain here.
        return error.response?.data || { status: false, status_message: "Network error during registration." };
      }
    },
    async login({ dispatch, commit }, payload) {
      commit('startGlobalLoading');
      try {
        const response = await apiService.login(payload); // Use apiService
        const data = response.data;
        // refreshToken from response is no longer handled here, HttpOnly cookie set by backend
        if (data.status && data.access_token) {
          dispatch('setAuthTokensAndFetchUser', { accessToken: data.access_token });
        }
        return data;
      } catch (error) {
        const errData = error.response?.data;
        const defaultMessage = "Login failed. Please try again later.";
        // Interceptor handles 401. Other errors (e.g., 400 bad request) can be handled here.
        if (error.response && error.response.status !== 401) {
            commit('setGlobalError', errData?.status_message || defaultMessage);
        }
        console.error("Login Error:", errData || error.message);
        return errData || { status: false, status_message: defaultMessage };
      } finally {
        commit('stopGlobalLoading');
      }
    },
    async setAuthTokensAndFetchUser({ commit, dispatch }, { accessToken }) { // refreshToken parameter removed
        commit('setAuthTokens', { accessToken }); // refreshToken parameter removed
        if (accessToken) {
            await dispatch('fetchUserProfile');
        }
    },
    async refreshToken({ commit, dispatch }) { // state parameter removed as refreshToken is not in state
      // The refresh token is an HttpOnly cookie, so the browser will send it automatically.
      // This action now primarily serves to call the backend endpoint and handle the response.
      try {
        const response = await apiService.refreshToken(); // No need to pass token from frontend
        const data = response.data;
        if (data.status && data.access_token) {
          // refreshToken is not passed to setAuthTokens anymore as it's not stored in Vuex
          commit('setAuthTokens', { accessToken: data.access_token });
          return { status: true, access_token: data.access_token };
        } else {
          await dispatch('logout');
          return { status: false, status_message: data.status_message || "Session refresh failed." };
        }
      } catch (error) {
        console.error("Token Refresh Action Error:", error.response?.data || error.message);
        await dispatch('logout');
        return { status: false, status_message: "Session expired. Please log in again." };
      }
    },
    async logout({ commit }) { // state parameter removed
      // currentRefreshToken is no longer available in Vuex state.
      // The backend's /logout2 endpoint (if still used) would need to rely on the cookie.
      // Or, the /logout endpoint on the backend should also invalidate the refresh token cookie.
      // For simplicity, we'll assume /logout handles access token and /logout2 (called via cookie) handles refresh.
      commit('clearAuth'); // Clear local access token and user state immediately

      try {
        await apiService.logout(); // Invalidates access token via API

        // To invalidate the HttpOnly refresh token, the backend /logout or a dedicated
        // /logout_refresh endpoint should clear the cookie.
        // If we still want to call /logout2, it needs to be a GET or POST that backend handles
        // by reading the refresh token from the cookie and blacklisting it.
        // For now, we'll rely on the backend to clear the cookie upon /logout or /logout2 if called.
        // The direct axios call to /logout2 is removed as we don't store refresh token.
        // The browser will send the cookie for /logout2 if that endpoint is called by apiService.
        // Assuming apiService.logout2() exists if needed, or backend /logout handles cookie.
        // Let's assume for now apiService.logout also triggers backend to clear refresh cookie,
        // or a separate call is made by apiService if needed.

        // If /logout2 is still meant to be called to invalidate the refresh token,
        // and it's a separate endpoint that relies on the cookie being sent:
        // await apiService.logout2(); // This would rely on withCredentials: true

        return { status: true, status_message: "Logged out successfully." };
      } catch (error) {
        console.warn("Server Logout Error during logout action:", error.response?.data || error.message);
        return { status: true, status_message: "Logged out locally. Server session might have issues clearing." };
      }
    },
    async loadSession({ dispatch, commit, state }) {
      const accessToken = state.accessToken; // Check state for accessToken
      if (accessToken) {
        commit('startGlobalLoading');
        try {
            // fetchUserProfile will use the new apiService which has interceptors.
            // If token is expired, interceptor should try to refresh.
            // If refresh fails, interceptor should logout.
            await dispatch('fetchUserProfile');
        } catch (error) {
            // If fetchUserProfile itself fails (e.g. network error not caught by interceptor, or refresh fails and logs out)
            // this catch might not be strictly necessary if interceptor handles all logout cases.
            console.error("Error during loadSession's fetchUserProfile:", error);
            // dispatch('logout'); // Consider if this is needed or if interceptor handles it.
        } finally {
            commit('stopGlobalLoading');
        }
      }
      // No 'else dispatch logout' here, app starts in logged-out state if no token.
    },
    async fetchUserProfile({ commit }) {
      try {
        const response = await apiService.fetchUserProfile(); // Use apiService
        if (response.data.status) {
          commit('setUser', response.data.user);
          return response.data.user;
        } else {
          // Non-2xx responses that are not 401 should be caught by the .catch block
          // This part might be redundant if apiService throws for non-ok responses.
          console.warn("Failed to fetch user profile (API reported !status):", response.data.status_message);
          return null;
        }
      } catch (error) {
        // Interceptor should handle 401. This catches other errors (500, network, etc.).
        console.error("Error fetching user profile:", error.response?.data || error.message);
        // Do not dispatch logout here directly, interceptor in api.js should manage it on 401.
        return null;
      }
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
          console.error('Error fetching slots:', errorMessage);
          return { status: false, status_message: errorMessage };
        }
      } catch (error) {
        const errData = error.response?.data;
        const defaultMessage = "Failed to load slot machines. Please try again.";
        if (error.response && error.response.status !== 401) { // Check error.response exists
          commit('setGlobalError', errData?.status_message || defaultMessage);
        }
        console.error('Network error fetching slots:', errData || error.message);
        return { status: false, status_message: errData?.status_message || defaultMessage };
      }
    },
    async fetchSlotConfig({ commit, state, dispatch }, slotId) {
      if (!state.slotsLoaded) {
        const fetchResult = await dispatch('fetchSlots'); // Already uses apiService if fetchSlots is updated
        if (!fetchResult || fetchResult.status === false || !fetchResult.slots) { // Adjusted condition
            console.error("fetchSlots failed or returned no slots, cannot filter for slot config");
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
    async fetchTables({ commit }) {
      try {
        // const response = await apiClient.get('/tables'); // OLD
        const response = await apiService.getTables(); // NEW - assuming getTables method in apiService
        if (response.data.status && Array.isArray(response.data.tables)) {
          commit('setTables', response.data.tables);
          return response.data;
        } else {
           const errorMessage = response.data.status_message || 'Failed to parse tables data.';
           console.error('Error fetching tables:', errorMessage);
           return { status: false, status_message: errorMessage };
        }
      } catch (error) {
        const errData = error.response?.data;
        const defaultMessage = "Failed to load tables. Please try again.";
        if (error.response && error.response.status !== 401) { // Check error.response exists
           // commit('setGlobalError', errData?.status_message || defaultMessage);
        }
        console.error('Network error fetching tables:', errData || error.message);
        return { status: false, status_message: errData?.status_message || defaultMessage };
      }
    },
    async fetchTableConfig({ commit, state, dispatch }, tableId) {
      if (!state.tablesLoaded) {
        const fetchResult = await dispatch('fetchTables'); // Already uses apiService if fetchTables is updated
        if (!fetchResult || fetchResult.status === false || !fetchResult.tables) { // Adjusted condition
            console.error("fetchTables failed or returned no tables, cannot filter for table config");
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
        console.error("End Session Error:", errData || error.message);
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
        console.error("Join Blackjack Error:", errData || error.message);
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
        console.error("Withdraw Error:", errData || error.message);
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
        console.error("Update Settings Error:", errData || error.message);
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
        console.error("Apply Bonus Code Error:", errData || error.message);
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
    isAuthenticated: (state) => !!state.accessToken, // Changed from userSession
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
