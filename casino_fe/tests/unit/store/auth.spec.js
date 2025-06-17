// Mock localStorage before importing store
const localStorageMock = {
  getItem: jest.fn(),
  setItem: jest.fn(),
  removeItem: jest.fn(),
  clear: jest.fn(),
};

// Override localStorage globally before store import
Object.defineProperty(global, 'localStorage', {
  value: localStorageMock,
  writable: true
});

import store from '@/store';
import apiService from '@/services/api';

// Mock the API service
jest.mock('@/services/api', () => ({
  register: jest.fn(),
  login: jest.fn(),
  logout: jest.fn(),
  refreshToken: jest.fn(),
  getCsrfToken: jest.fn(),
  getUserProfile: jest.fn(),
}));

describe('Vuex Store - Auth Module', () => {
  beforeEach(() => {
    // Clear all mocks before each test
    jest.clearAllMocks();
    localStorageMock.clear();
    
    // Reset store state
    store.commit('clearAuth');
    store.commit('clearGlobalError');
  });

  describe('Mutations', () => {
    it('setUser correctly sets user data', () => {
      const userData = { id: 1, username: 'testuser', email: 'test@example.com' };
      store.commit('setUser', userData);
      expect(store.state.user).toEqual(userData);
    });

    it('setAuthTokens correctly sets tokens in state and localStorage', () => {
      const tokens = { accessToken: 'access123', refreshToken: 'refresh456' };
      store.commit('setAuthTokens', tokens);
      expect(store.state.userSession).toBe(tokens.accessToken);
      expect(store.state.refreshToken).toBe(tokens.refreshToken);
      expect(localStorageMock.setItem).toHaveBeenCalledWith('userSession', tokens.accessToken);
      expect(localStorageMock.setItem).toHaveBeenCalledWith('refreshToken', tokens.refreshToken);
    });

    it('setAuthTokens clears localStorage if tokens are null', () => {
      store.commit('setAuthTokens', { accessToken: null, refreshToken: null });
      expect(localStorageMock.removeItem).toHaveBeenCalledWith('userSession');
      expect(localStorageMock.removeItem).toHaveBeenCalledWith('refreshToken');
    });

    it('clearAuth correctly clears state and localStorage', () => {
      // Setup initial state
      store.commit('setUser', { id: 1, username: 'testuser' });
      store.commit('setAuthTokens', { accessToken: 'access123', refreshToken: 'refresh456' });

      store.commit('clearAuth');
      expect(store.state.user).toBeNull();
      expect(store.state.userSession).toBeNull();
      expect(store.state.refreshToken).toBeNull();
      expect(localStorageMock.removeItem).toHaveBeenCalledWith('userSession');
      expect(localStorageMock.removeItem).toHaveBeenCalledWith('refreshToken');
    });

    it('setGlobalError sets the global error message', () => {
      const errorMessage = 'Something went wrong!';
      store.commit('setGlobalError', errorMessage);
      expect(store.state.globalError).toBe(errorMessage);
    });

    it('clearGlobalError clears the global error message', () => {
      store.commit('setGlobalError', 'Some error');
      store.commit('clearGlobalError');
      expect(store.state.globalError).toBeNull();
    });
  });

  describe('Actions', () => {
    describe('register', () => {
      it('commits tokens and fetches user on successful registration', async () => {
        const userData = { username: 'newuser', email: 'new@example.com', password: 'password123' };
        const responseData = {
          status: true,
          user: { id: 1, username: 'newuser' },
          csrf_token: 'csrf123'
        };
        apiService.register.mockResolvedValueOnce({ data: responseData });

        const result = await store.dispatch('register', userData);

        expect(apiService.register).toHaveBeenCalledWith(userData);
        expect(result).toEqual(responseData);
        expect(store.state.user).toEqual(responseData.user);
        expect(store.state.csrfToken).toBe(responseData.csrf_token);
      });

      it('returns error data on failed registration', async () => {
        const userData = { username: 'newuser', email: 'new@example.com', password: 'password123' };
        const errorResponse = { status: false, status_message: 'User already exists' };
        apiService.register.mockRejectedValueOnce({ response: { data: errorResponse } });

        const result = await store.dispatch('register', userData);

        expect(apiService.register).toHaveBeenCalledWith(userData);
        expect(result).toEqual(errorResponse);
        expect(store.state.globalError).toBeNull(); // Register action doesn't set global error by default
      });
    });

    describe('login', () => {
      it('commits user data on successful login', async () => {
        const loginPayload = { username: 'test', password: 'pw' };
        const responseData = {
          status: true,
          user: { id: 1, username: 'test' },
          csrf_token: 'csrf123'
        };
        apiService.login.mockResolvedValueOnce({ data: responseData });

        const result = await store.dispatch('login', loginPayload);

        expect(apiService.login).toHaveBeenCalledWith(loginPayload);
        expect(result).toEqual(responseData);
        expect(store.state.user).toEqual(responseData.user);
        expect(store.state.csrfToken).toBe(responseData.csrf_token);
      });

      it('sets globalError and returns error data on failed login (non-401)', async () => {
        const loginPayload = { username: 'test', password: 'pw' };
        const errorResponse = { status: false, status_message: 'Server error' };
        apiService.login.mockRejectedValueOnce({ response: { status: 500, data: errorResponse } });

        const result = await store.dispatch('login', loginPayload);

        expect(apiService.login).toHaveBeenCalledWith(loginPayload);
        expect(result).toEqual(errorResponse);
        expect(store.state.globalError).toBe(errorResponse.status_message);
      });

      it('returns error data but does not set globalError on 401 login failure', async () => {
        const loginPayload = { username: 'test', password: 'pw' };
        const errorResponse = { status: false, status_message: 'Invalid credentials' };
        apiService.login.mockRejectedValueOnce({ response: { status: 401, data: errorResponse } });

        const result = await store.dispatch('login', loginPayload);

        expect(apiService.login).toHaveBeenCalledWith(loginPayload);
        expect(result).toEqual(errorResponse);
        expect(store.state.globalError).toBeNull(); // 401s are handled by interceptor or component
      });
    });

    describe('fetchUserProfile', () => {
      it('commits setUser on successful fetch', async () => {
        const userData = { id: 1, username: 'testuser' };
        apiService.getUserProfile.mockResolvedValueOnce({ data: { status: true, user: userData } });

        const result = await store.dispatch('fetchUserProfile');

        expect(apiService.getUserProfile).toHaveBeenCalled();
        expect(store.state.user).toEqual(userData);
        expect(result).toEqual({ status: true, user: userData });
      });

      it('does not commit setUser on failed fetch', async () => {
        apiService.getUserProfile.mockRejectedValueOnce({ response: { data: { status: false } } });

        const result = await store.dispatch('fetchUserProfile');

        expect(apiService.getUserProfile).toHaveBeenCalled();
        expect(store.state.user).toBeNull(); // Assuming initial state is null
        expect(result).toEqual({ status: false });
      });
    });

    describe('logout', () => {
      it('clears auth state and calls logout API', async () => {
        store.commit('setAuthTokens', { accessToken: 'access123', refreshToken: 'refresh456' });
        store.commit('setUser', { id: 1, username: 'test' });

        apiService.logout.mockResolvedValueOnce({ data: { status: true } });

        await store.dispatch('logout');

        expect(store.state.user).toBeNull();
        expect(store.state.userSession).toBeNull();
        expect(store.state.refreshToken).toBeNull();
        expect(localStorageMock.removeItem).toHaveBeenCalledWith('userSession');
        expect(localStorageMock.removeItem).toHaveBeenCalledWith('refreshToken');
        expect(apiService.logout).toHaveBeenCalled();
      });
    });

    describe('refreshToken', () => {
      it('commits new token on successful refresh', async () => {
        const responseData = { status: true, csrf_token: 'newCsrf' };
        apiService.refreshToken.mockResolvedValueOnce({ data: responseData });

        const result = await store.dispatch('refreshToken');

        expect(apiService.refreshToken).toHaveBeenCalled();
        expect(store.state.csrfToken).toBe('newCsrf');
        expect(result).toEqual({ status: true });
      });

      it('clears auth on failed refresh', async () => {
        apiService.refreshToken.mockRejectedValueOnce({ response: { data: { status: false } } });

        const result = await store.dispatch('refreshToken');

        expect(apiService.refreshToken).toHaveBeenCalled();
        expect(store.state.user).toBeNull();
        expect(result.status).toBe(false);
      });
    });
  });
});
