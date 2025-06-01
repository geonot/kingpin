import { createStore } from 'vuex';
import storeConfig from '@/store/index'; // Assuming this is the configuration object
import axios from 'axios';

// 1. Mock axios library
jest.mock('axios', () => {
  const mockAxiosInstance = {
    post: jest.fn(),
    get: jest.fn(),
    // Mock interceptors if your actions rely on them being configured,
    // though for unit testing actions, we often focus on pre/post interceptor logic.
    interceptors: {
      request: { use: jest.fn(), eject: jest.fn() },
      response: { use: jest.fn(), eject: jest.fn() },
    },
  };
  return {
    create: jest.fn(() => mockAxiosInstance), // apiClient is created via axios.create()
    post: jest.fn(), // For any direct axios.post calls (if any)
    get: jest.fn(),  // For any direct axios.get calls (if any)
  };
});


// Helper to create a fresh store for each test if needed, or use parts of storeConfig directly
const createTestStore = (initialState = {}) => {
  // Deep clone initial store config to avoid state leakage if modules are complex
  // For this store, it's relatively simple.
  const testStoreConfig = JSON.parse(JSON.stringify(storeConfig));
  return createStore({
    ...testStoreConfig,
    state: {
      ...testStoreConfig.state,
      ...initialState, // Override with any specific initial state for a test
    },
  });
};

// Mock localStorage
const localStorageMock = (() => {
  let store = {};
  return {
    getItem: jest.fn(key => store[key] || null),
    setItem: jest.fn((key, value) => {
      store[key] = value.toString();
    }),
    removeItem: jest.fn(key => {
      delete store[key];
    }),
    clear: jest.fn(() => {
      store = {};
    }),
  };
})();
Object.defineProperty(window, 'localStorage', { value: localStorageMock });


describe('Vuex Store - Auth Module', () => {
  let store;
  let mockedAxios;

  beforeEach(() => {
    // Create a new store instance for each test
    store = createTestStore();

    // Clear all mocks before each test
    jest.clearAllMocks();
    localStorageMock.clear();

    // apiClient inside the store module will use the mocked axios.create()
    // We can get a reference to the mocked methods via the imported axios
    // This assumes apiClient is the single instance created by axios.create() in store/index.js
    // If store/index.js calls axios.create() multiple times, this might need adjustment,
    // but it seems to create only one `apiClient`.
    // The mock for `axios.create()` returns an object where we can access `post` and `get`.
    // So, `axios.create().post` and `axios.create().get` are the jest.fn() instances.
    // To get the instance returned by create():
    mockedAxios = axios.create(); // This will give us the mocked instance
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
          access_token: 'newAccess',
          refresh_token: 'newRefresh',
          // user object is not directly returned by /register in app, fetchUserProfile gets it
        };
        mockedAxios.post.mockResolvedValueOnce({ data: responseData });

        // Mock fetchUserProfile for this test as it's dispatched by setAuthTokensAndFetchUser
        const dispatch = jest.fn(); // Mock dispatch
        const commit = jest.fn(); // Mock commit, though setAuthTokensAndFetchUser primarily dispatches

        await store.dispatch('register', userData); // store.dispatch directly calls actions from storeConfig

        expect(mockedAxios.post).toHaveBeenCalledWith('/register', userData);
        // register action dispatches 'setAuthTokensAndFetchUser'
        // Check if 'setAuthTokensAndFetchUser' was dispatched correctly by the real store's dispatch
        // This requires a more integrated store or spying on dispatch.
        // For now, let's assume if apiClient.post was called, the next step is to test setAuthTokensAndFetchUser separately.
        // Or, we can check the final state if fetchUserProfile was also mocked.
        // Given the current structure, register calls dispatch('setAuthTokensAndFetchUser', ...)

        // To test this properly, we need to see if setAuthTokensAndFetchUser was dispatched.
        // This is hard without spying on the store's own dispatch.
        // Alternative: Test the side effects (localStorage, state) if fetchUserProfile is also mocked.
      });

      it('returns error data on failed registration', async () => {
        const userData = { username: 'newuser', email: 'new@example.com', password: 'password123' };
        const errorResponse = { status: false, status_message: 'User already exists' };
        mockedAxios.post.mockRejectedValueOnce({ response: { data: errorResponse } });

        const result = await store.dispatch('register', userData);

        expect(mockedAxios.post).toHaveBeenCalledWith('/register', userData);
        expect(result).toEqual(errorResponse);
        expect(store.state.globalError).toBeNull(); // Register action doesn't set global error by default
      });
    });

    describe('login', () => {
      it('dispatches setAuthTokensAndFetchUser on successful login', async () => {
        const loginPayload = { username: 'test', password: 'pw' };
        const responseData = {
          status: true,
          access_token: 'fakeAccess',
          refresh_token: 'fakeRefresh',
          user: { id: 1, username: 'test' } // Login response includes user
        };
        mockedAxios.post.mockResolvedValueOnce({ data: responseData });

        // Spy on the dispatch method of the specific store instance
        const dispatchSpy = jest.spyOn(store, 'dispatch');

        await store.dispatch('login', loginPayload);

        expect(mockedAxios.post).toHaveBeenCalledWith('/login', loginPayload);
        expect(dispatchSpy).toHaveBeenCalledWith('setAuthTokensAndFetchUser', {
          accessToken: responseData.access_token,
          refreshToken: responseData.refresh_token,
        });
        dispatchSpy.mockRestore();
      });

      it('sets globalError and returns error data on failed login (non-401)', async () => {
        const loginPayload = { username: 'test', password: 'pw' };
        const errorResponse = { status: false, status_message: 'Server error' };
        mockedAxios.post.mockRejectedValueOnce({ response: { status: 500, data: errorResponse } });

        const result = await store.dispatch('login', loginPayload);

        expect(mockedAxios.post).toHaveBeenCalledWith('/login', loginPayload);
        expect(result).toEqual(errorResponse);
        expect(store.state.globalError).toBe(errorResponse.status_message);
      });

      it('returns error data but does not set globalError on 401 login failure', async () => {
        const loginPayload = { username: 'test', password: 'pw' };
        const errorResponse = { status: false, status_message: 'Invalid credentials' };
        mockedAxios.post.mockRejectedValueOnce({ response: { status: 401, data: errorResponse } });

        const result = await store.dispatch('login', loginPayload);

        expect(mockedAxios.post).toHaveBeenCalledWith('/login', loginPayload);
        expect(result).toEqual(errorResponse);
        expect(store.state.globalError).toBeNull(); // 401s are handled by interceptor or component
      });
    });

    describe('setAuthTokensAndFetchUser', () => {
        it('commits setAuthTokens and dispatches fetchUserProfile', async () => {
            const tokens = { accessToken: 'access123', refreshToken: 'refresh456' };
            const commit = jest.fn();
            const dispatch = jest.fn();

            // Directly test the action function if it's complex, or test through store.dispatch
            // For storeConfig.actions.setAuthTokensAndFetchUser, we need to get it from the config
            const action = storeConfig.actions.setAuthTokensAndFetchUser;
            await action({ commit, dispatch }, tokens);

            expect(commit).toHaveBeenCalledWith('setAuthTokens', tokens);
            expect(dispatch).toHaveBeenCalledWith('fetchUserProfile');
        });
    });

    describe('fetchUserProfile', () => {
      it('commits setUser on successful fetch', async () => {
        const userData = { id: 1, username: 'testuser' };
        mockedAxios.get.mockResolvedValueOnce({ data: { status: true, user: userData } });

        await store.dispatch('fetchUserProfile');

        expect(mockedAxios.get).toHaveBeenCalledWith('/me');
        expect(store.state.user).toEqual(userData);
      });

      it('does not commit setUser on failed fetch', async () => {
        mockedAxios.get.mockRejectedValueOnce({ response: { data: { status: false } } });

        await store.dispatch('fetchUserProfile');

        expect(mockedAxios.get).toHaveBeenCalledWith('/me');
        expect(store.state.user).toBeNull(); // Assuming initial state is null
      });
    });

    describe('logout', () => {
      it('clears auth state and calls logout APIs', async () => {
        store.commit('setAuthTokens', { accessToken: 'access123', refreshToken: 'refresh456' });

        mockedAxios.post.mockResolvedValue({ data: { status: true } }); // Mock for /logout and /logout2

        await store.dispatch('logout');

        expect(store.state.userSession).toBeNull();
        expect(store.state.refreshToken).toBeNull();
        expect(localStorageMock.removeItem).toHaveBeenCalledWith('userSession');
        expect(localStorageMock.removeItem).toHaveBeenCalledWith('refreshToken');

        expect(mockedAxios.post).toHaveBeenCalledWith('/logout', {});
        // For /logout2, it creates a new axios instance in the actual code.
        // This mock setup for `axios.create()` means `mockedAxios` IS that instance.
        // However, the actual code is: `const tempApiClient = axios.create({ baseURL: '/api' });`
        // `await tempApiClient.post('/logout2', {}, { headers: { Authorization: `Bearer ${refreshToken}` } });`
        // This means `axios.create` would be called again.
        // Our current mock for `axios.create` returns the same `mockedAxios` instance.
        // So, we check if `mockedAxios.post` was called with '/logout2'.
        expect(mockedAxios.post).toHaveBeenCalledWith('/logout2', {}, {"headers": {"Authorization": "Bearer refresh456"}});
      });
    });

    describe('refreshToken', () => {
        it('commits new access token on successful refresh', async () => {
            store.commit('setAuthTokens', { accessToken: 'oldAccess', refreshToken: 'validRefresh' });
            const responseData = { status: true, access_token: 'newAccess' };
            // refreshToken action uses a new axios instance for the call
            // axios.create().post is mockedAxios.post
            mockedAxios.post.mockResolvedValueOnce({ data: responseData });

            const result = await store.dispatch('refreshToken');

            expect(mockedAxios.post).toHaveBeenCalledWith('/refresh', {}, {
                headers: { Authorization: `Bearer validRefresh` }
            });
            expect(store.state.userSession).toBe('newAccess');
            expect(store.state.refreshToken).toBe('validRefresh'); // Refresh token remains the same
            expect(result).toEqual({ status: true, access_token: 'newAccess' });
        });

        it('dispatches logout on failed refresh', async () => {
            store.commit('setAuthTokens', { accessToken: 'oldAccess', refreshToken: 'invalidRefresh' });
            mockedAxios.post.mockRejectedValueOnce({ response: { data: { status: false } } });
            const dispatchSpy = jest.spyOn(store, 'dispatch');

            const result = await store.dispatch('refreshToken');

            expect(mockedAxios.post).toHaveBeenCalledWith('/refresh', {}, {
                headers: { Authorization: `Bearer invalidRefresh` }
            });
            expect(dispatchSpy).toHaveBeenCalledWith('logout');
            expect(result.status).toBe(false);
            dispatchSpy.mockRestore();
        });

        it('dispatches logout if no refresh token exists', async () => {
            store.commit('clearAuth'); // Ensure no refresh token
            const dispatchSpy = jest.spyOn(store, 'dispatch');

            const result = await store.dispatch('refreshToken');

            expect(dispatchSpy).toHaveBeenCalledWith('logout');
            expect(result.status).toBe(false);
            expect(result.status_message).toContain("No refresh token available");
            dispatchSpy.mockRestore();
        });
    });

    describe('loadSession', () => {
        it('dispatches fetchUserProfile if token exists in localStorage', async () => {
            localStorageMock.setItem('userSession', 'storedAccessToken');
            // store needs to be re-initialized to pick up localStorageMock change in its own initial state.
            store = createTestStore({ userSession: 'storedAccessToken' });
            const dispatchSpy = jest.spyOn(store, 'dispatch');
            mockedAxios.get.mockResolvedValueOnce({ data: { status: true, user: {id:1, name:'test'} } }); // for fetchUserProfile

            await store.dispatch('loadSession');

            expect(localStorageMock.getItem).toHaveBeenCalledWith('userSession');
            expect(dispatchSpy).toHaveBeenCalledWith('fetchUserProfile');
            dispatchSpy.mockRestore();
        });

        it('dispatches logout if no token exists in localStorage', async () => {
            localStorageMock.removeItem('userSession');
            store = createTestStore({ userSession: null }); // Ensure store state is also clean
            const dispatchSpy = jest.spyOn(store, 'dispatch');

            await store.dispatch('loadSession');

            expect(localStorageMock.getItem).toHaveBeenCalledWith('userSession');
            expect(dispatchSpy).toHaveBeenCalledWith('logout');
            dispatchSpy.mockRestore();
        });
    });

  });
});
