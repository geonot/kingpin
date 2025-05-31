import { createStore } from 'vuex';
import axios from 'axios'; // Use axios for API calls

// --- Helper Functions ---
const getAuthConfig = (state) => {
  const headers = { 'Content-Type': 'application/json' };
  if (state.userSession) {
    headers['Authorization'] = `Bearer ${state.userSession}`;
  }
  return { headers };
};

const SATOSHI_FACTOR = 100_000_000;

export default createStore({
  state: {
    user: null, // User object { id, username, email, balance (sats), deposit_wallet_address, is_admin, etc. }
    userSession: localStorage.getItem('userSession') || null, // Access Token
    refreshToken: localStorage.getItem('refreshToken') || null,
    slots: [], // Array of slot objects { id, name, description, ... }
    slotsLoaded: false, // Flag to avoid redundant fetching
    currentSlotConfig: null, // Store config for the currently viewed slot game
    tables: [], // Array of blackjack table objects { id, name, description, min_bet, max_bet, ... }
    tablesLoaded: false, // Flag to avoid redundant fetching
    currentTableConfig: null, // Store config for the currently viewed blackjack table
  },
  mutations: {
    setUser(state, user) {
      state.user = user;
      if (user) {
        // Store only necessary, non-sensitive info if needed, or rely on re-fetching
        // localStorage.setItem('user', JSON.stringify({ id: user.id, username: user.username, is_admin: user.is_admin })); // Example
      } else {
        localStorage.removeItem('user'); // Clear any stale user data if logging out
      }
    },
    // Combined mutation for setting tokens
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
    // Separate logout mutation for clarity
    clearAuth(state) {
        state.user = null;
        state.userSession = null;
        state.refreshToken = null;
        localStorage.removeItem('userSession');
        localStorage.removeItem('refreshToken');
        localStorage.removeItem('user'); // Clear any other user data
    },
    setSlots(state, slots) {
      state.slots = slots;
      state.slotsLoaded = true;
    },
     setCurrentSlotConfig(state, config) {
      state.currentSlotConfig = config;
    },
    // Mutation to directly update user balance (e.g., after spin)
    updateUserBalance(state, newBalanceSats) {
      if (state.user && typeof newBalanceSats === 'number') {
        state.user.balance = newBalanceSats;
        // Persist updated user info (optional, consider security)
        // if (state.user) localStorage.setItem('user', JSON.stringify(state.user));
      }
    },
    // Blackjack table mutations
    setTables(state, tables) {
      state.tables = tables;
      state.tablesLoaded = true;
    },
    setCurrentTableConfig(state, config) {
      state.currentTableConfig = config;
    }
  },
  actions: {
    // --- Authentication ---
    async register({ commit }, payload) {
      try {
        const response = await axios.post('/api/register', payload);
        const data = response.data;
        if (data.status) {
          commit('setUser', data.user);
          commit('setAuthTokens', { accessToken: data.access_token, refreshToken: data.refresh_token });
        }
        return data; // Return full response { status, user?, access_token?, refresh_token?, status_message? }
      } catch (error) {
         console.error("Registration Error:", error.response?.data || error.message);
         return error.response?.data || { status: false, status_message: "Network error during registration." };
      }
    },
    async login({ commit }, payload) {
        try {
            const response = await axios.post('/api/login', payload);
            const data = response.data;
            if (data.status) {
              commit('setUser', data.user);
              commit('setAuthTokens', { accessToken: data.access_token, refreshToken: data.refresh_token });
            }
            return data;
        } catch (error) {
            console.error("Login Error:", error.response?.data || error.message);
            return error.response?.data || { status: false, status_message: "Network error during login." };
        }
    },
     async refreshToken({ commit, state }) {
        if (!state.refreshToken) {
            return { status: false, status_message: "No refresh token available." };
        }
        try {
            const response = await axios.post('/api/refresh', {}, {
                headers: { Authorization: `Bearer ${state.refreshToken}` }
            });
            const data = response.data;
            if (data.status) {
                 // Only update the access token
                 commit('setAuthTokens', { accessToken: data.access_token, refreshToken: state.refreshToken });
            } else {
                 // Refresh failed (e.g., token expired/invalidated) -> Logout
                 commit('clearAuth');
            }
            return data;
        } catch (error) {
            console.error("Token Refresh Error:", error.response?.data || error.message);
             // Assume refresh token is invalid -> Logout
             commit('clearAuth');
            return error.response?.data || { status: false, status_message: "Session expired. Please log in again." };
        }
    },
     async logout({ commit, state }) {
         const accessToken = state.userSession;
         const refreshToken = state.refreshToken;
         commit('clearAuth'); // Clear local state immediately

         try {
             // Attempt to invalidate tokens on the backend
             if (accessToken) {
                 await axios.post('/api/logout', {}, { headers: { Authorization: `Bearer ${accessToken}` } });
             }
              if (refreshToken) {
                 await axios.post('/api/logout2', {}, { headers: { Authorization: `Bearer ${refreshToken}` } });
             }
             return { status: true, status_message: "Logged out successfully." };
         } catch (error) {
             console.warn("Logout Error (backend invalidation might have failed):", error.response?.data || error.message);
             // Logout still successful locally, backend failure isn't critical for user experience here
             return { status: true, status_message: "Logged out." };
         }
     },
     // Action to load session from storage and potentially fetch user data if needed
     loadSession({ commit, state }) {
        const accessToken = localStorage.getItem('userSession');
        const refreshToken = localStorage.getItem('refreshToken');
        // const storedUser = localStorage.getItem('user'); // Fetch fresh user data instead?

        if (accessToken && refreshToken) {
            commit('setAuthTokens', { accessToken, refreshToken });
             // TODO: Fetch fresh user data from a '/api/me' endpoint instead of relying on stale localStorage 'user'
             // Example:
             // dispatch('fetchUserProfile');
        } else {
            // Ensure state is clean if tokens are missing
            commit('clearAuth');
        }
      },
      // Example: Action to fetch current user profile
       async fetchUserProfile({ commit, state }) {
           if (!state.userSession) return; // No token, can't fetch
           try {
               // Assuming you have a '/api/me' endpoint secured by JWT
               const response = await axios.get('/api/me', getAuthConfig(state));
               if (response.data.status) {
                   commit('setUser', response.data.user);
               } else {
                    console.warn("Failed to fetch user profile:", response.data.status_message);
                   // Potentially handle token expiry here by trying refresh
               }
           } catch (error) {
               console.error("Error fetching user profile:", error.response?.data || error.message);
               // Handle error, maybe token expired -> try refresh or logout
               if (error.response?.status === 401) { // Unauthorized
                   // Attempt refresh or logout
               }
           }
       },

    // --- Game Data ---
    async fetchSlots({ commit, state }) {
      // Avoid refetching if already loaded, unless forced
      // if (state.slotsLoaded && !force) { return state.slots; }
      try {
        const response = await axios.get('/api/slots', getAuthConfig(state)); // Use auth if available
        const data = response.data;
        if (data.status && Array.isArray(data.slots)) {
          commit('setSlots', data.slots);
          return data.slots;
        } else {
          console.error('Error fetching slots:', data.status_message || 'Unknown error');
          return []; // Return empty array on failure
        }
      } catch (error) {
        console.error('Network error fetching slots:', error.response?.data || error.message);
        return [];
      }
    },
     // Action to get specific slot config (could fetch from API or filter state)
     async fetchSlotConfig({ commit, state, dispatch }, slotId) {
        // Option 1: Fetch directly if endpoint exists
        // const response = await axios.get(`/api/slots/${slotId}`, getAuthConfig(state));
        // commit('setCurrentSlotConfig', response.data.slot);

        // Option 2: Filter from existing slots state
         if (!state.slotsLoaded) {
             await dispatch('fetchSlots'); // Ensure slots are loaded
         }
         const slot = state.slots.find(s => s.id === slotId);
         if (slot) {
             commit('setCurrentSlotConfig', slot);
             return slot;
         } else {
              console.error(`Slot config for ID ${slotId} not found.`);
              return null;
         }
    },

    // --- Blackjack Table Data ---
    async fetchTables({ commit, state }) {
      // Avoid refetching if already loaded, unless forced
      // if (state.tablesLoaded && !force) { return state.tables; }
      try {
        const response = await axios.get('/api/tables', getAuthConfig(state)); // Use auth if available
        const data = response.data;
        if (data.status && Array.isArray(data.tables)) {
          commit('setTables', data.tables);
          return data.tables;
        } else {
          console.error('Error fetching tables:', data.status_message || 'Unknown error');
          return []; // Return empty array on failure
        }
      } catch (error) {
        console.error('Network error fetching tables:', error.response?.data || error.message);
        return [];
      }
    },
    // Action to get specific table config (could fetch from API or filter state)
    async fetchTableConfig({ commit, state, dispatch }, tableId) {
      // Filter from existing tables state
      if (!state.tablesLoaded) {
        await dispatch('fetchTables'); // Ensure tables are loaded
      }
      const table = state.tables.find(t => t.id === tableId);
      if (table) {
        commit('setCurrentTableConfig', table);
        return table;
      } else {
        console.error(`Table config for ID ${tableId} not found.`);
        return null;
      }
    },

    // --- Gameplay Actions ---
    async endSession({ state }) {
        try {
            const response = await axios.post('/api/end_session', {}, getAuthConfig(state));
            console.log('Store: Session ended:', response.data);
            return response.data;
        } catch (error) {
            console.error("End Session Error:", error.response?.data || error.message);
            return error.response?.data || { status: false, status_message: "Network error ending game session." };
        }
    },
    
    async joinGame({ state, commit }, payload) {
        // Use the provided game_type or default to 'slot'
        payload['game_type'] = payload['game_type'] || 'slot';
        try {
            const response = await axios.post('/api/join', payload, getAuthConfig(state));
            // No specific state mutation needed here unless tracking active session ID globally
            return response.data;
        } catch (error) {
            console.error("Join Game Error:", error.response?.data || error.message);
            return error.response?.data || { status: false, status_message: "Network error joining game." };
        }
    },
    async spin({ state, commit }, payload) {
        try {
            console.log('Store: Sending spin request with payload:', payload);
            const response = await axios.post('/api/spin', payload, getAuthConfig(state));
            const data = response.data;
            console.log('Store: Received spin response:', data);
            if (data.status && data.user) {
                // Update user balance in the store
                commit('updateUserBalance', data.user.balance);
            }
            return data;
        } catch (error) {
             console.error("Spin Error:", error.response?.data || error.message);
            // Handle specific errors like insufficient balance (400/402) if needed
            if (error.response?.status === 400 && error.response?.data?.status_message?.toLowerCase().includes('balance')) {
                 // Optionally commit a state change to indicate insufficient funds
            }
            return error.response?.data || { status: false, status_message: "Network error during spin." };
        }
    },

    // --- Blackjack Actions ---
    async joinBlackjack({ state, commit }, payload) {
      try {
        console.log('Store: Sending join blackjack request with payload:', payload);
        const response = await axios.post('/api/join_blackjack', payload, getAuthConfig(state));
        const data = response.data;
        console.log('Store: Received join blackjack response:', data);
        if (data.status && data.user) {
          // Update user balance in the store
          commit('updateUserBalance', data.user.balance);
        }
        return data;
      } catch (error) {
        console.error("Join Blackjack Error:", error.response?.data || error.message);
        // Handle specific errors like insufficient balance (400/402) if needed
        if (error.response?.status === 400 && error.response?.data?.status_message?.toLowerCase().includes('balance')) {
          // Optionally commit a state change to indicate insufficient funds
        }
        return error.response?.data || { status: false, status_message: "Network error joining blackjack game." };
      }
    },
    async blackjackAction({ state, commit }, payload) {
      try {
        console.log('Store: Sending blackjack action request with payload:', payload);
        const response = await axios.post('/api/blackjack_action', payload, getAuthConfig(state));
        const data = response.data;
        console.log('Store: Received blackjack action response:', data);
        if (data.status && data.user) {
          // Update user balance in the store
          commit('updateUserBalance', data.user.balance);
        }
        return data;
      } catch (error) {
        console.error("Blackjack Action Error:", error.response?.data || error.message);
        return error.response?.data || { status: false, status_message: "Network error during blackjack action." };
      }
    },

    // --- User Account Actions ---
    async withdraw({ state, commit }, payload) {
        try {
             // Backend expects amount_sats, schema uses 'amount' with data_key
            const response = await axios.post('/api/withdraw', payload, getAuthConfig(state));
            const data = response.data;
            if (data.status && data.user) {
                // Update user balance after successful request submission
                commit('updateUserBalance', data.user.balance);
            }
            return data;
        } catch (error) {
            console.error("Withdraw Error:", error.response?.data || error.message);
            return error.response?.data || { status: false, status_message: "Network error during withdrawal request." };
        }
    },
    async updateSettings({ state, commit }, payload) {
        try {
            const response = await axios.post('/api/settings', payload, getAuthConfig(state));
            const data = response.data;
            if (data.status && data.user) {
              // Update the user object in the store
              commit('setUser', data.user);
            }
            return data;
        } catch (error) {
             console.error("Update Settings Error:", error.response?.data || error.message);
             return error.response?.data || { status: false, status_message: "Network error updating settings." };
        }
    },
    // Action to apply bonus code (might be part of deposit flow)
    async applyBonusCode({ state, commit }, payload) {
         try {
            // Using /api/deposit endpoint for bonus code application for now
            const response = await axios.post('/api/deposit', payload, getAuthConfig(state));
            const data = response.data;
            if (data.status && data.user) {
                // Update user balance if bonus was applied
                commit('updateUserBalance', data.user.balance);
            }
            return data; // { status, user?, status_message }
        } catch (error) {
            console.error("Apply Bonus Code Error:", error.response?.data || error.message);
            return error.response?.data || { status: false, status_message: "Network error applying bonus code." };
        }
    },
  },
  getters: {
    isAuthenticated: (state) => !!state.userSession, // Check if access token exists
    // Optional: Getter to get user data safely
    currentUser: (state) => state.user,
    // Getter for all slots
    getSlots: (state) => state.slots,
    // Getter to find a slot by ID
    getSlotById: (state) => (id) => {
        const numericId = Number(id);
        return state.slots.find(slot => slot.id === numericId);
    },
    // Getter for admin status
    isAdmin: (state) => state.user?.is_admin ?? false,
    // Getter for all tables
    getTables: (state) => state.tables,
    // Getter to find a table by ID
    getTableById: (state) => (id) => {
      const numericId = Number(id);
      return state.tables.find(table => table.id === numericId);
    },
  },
  modules: {},
});
