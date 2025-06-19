import apiClient, { injectStore } from '@/services/api';
import axios from 'axios'; // Needed for axios.isAxiosError if used, or to access adapter
import { flushPromises } from '@vue/test-utils';

// Mock Axios
jest.mock('axios', () => {
  const mockAxiosInstance = {
    create: jest.fn(() => mockAxiosInstance),
    interceptors: {
      request: { use: jest.fn() },
      response: { use: jest.fn() },
    },
    // Mock HTTP methods if your tests make actual calls through apiClient
    // For interceptor tests, we mostly care about how it processes mocked errors.
    post: jest.fn(),
    get: jest.fn(),
  };
  return mockAxiosInstance;
});


describe('@/services/api.js', () => {
  let mockStore;
  let responseInterceptor;

  beforeAll(() => {
    // Capture the response interceptor
    // The call to axios.interceptors.response.use in api.js will pass its function
    // to this mock. We store that function to call it directly in tests.
    axios.interceptors.response.use.mockImplementation((success, error) => {
      responseInterceptor = error; // Store the error handler part of the interceptor
    });
    // Initialize apiClient to set up interceptors
    // This is a bit of a workaround to get the interceptor function.
    // The 'apiClient' instance from the actual module is what we want to test,
    // but its interceptor function is what we need to invoke with mock errors.
    require('@/services/api');
  });

  beforeEach(() => {
    // Reset mocks and create a fresh store for each test
    jest.clearAllMocks();

    mockStore = {
      dispatch: jest.fn(),
      state: { csrfToken: 'test-csrf-token' }, // Mock CSRF token if needed by request interceptor tests
    };
    injectStore(mockStore); // Inject the mock store into api.js

    // Ensure we have the interceptor function
    // Re-setup if somehow lost, though beforeAll should handle it.
     if (!responseInterceptor) {
        axios.interceptors.response.use.mockImplementation((success, error) => {
            responseInterceptor = error;
        });
        require('@/services/api'); // Re-initialize to capture interceptor
     }
     expect(responseInterceptor).toBeDefined();

  });

  describe('Response Interceptor - Structured Errors', () => {
    it('should parse and reject a structured error object', async () => {
      const mockError = {
        isAxiosError: true,
        config: {},
        response: {
          data: {
            request_id: 'req_123',
            error_code: 'BE_GEN_001',
            status_message: 'A generic error occurred.',
            details: { extra: 'info' },
            action_button: { text: 'Retry', actionType: 'RETRY' },
          },
          status: 400,
        },
      };

      try {
        await responseInterceptor(mockError);
      } catch (e) {
        expect(e.isStructuredError).toBe(true);
        expect(e.errorCode).toBe('BE_GEN_001');
        expect(e.message).toBe('A generic error occurred.');
        expect(e.details).toEqual({ extra: 'info' });
        expect(e.actionButton).toEqual({ text: 'Retry', actionType: 'RETRY' });
        expect(e.originalError).toBe(mockError);
      }
    });

    it('handles UNAUTHENTICATED (BE_GEN_003) and retries on successful token refresh', async () => {
      const mockError = {
        isAxiosError: true,
        config: { _retry: false }, // Original request, not a retry yet
        response: {
          data: { error_code: 'BE_GEN_003', status_message: 'Unauthorized' },
          status: 401,
        },
      };
      mockStore.dispatch.mockResolvedValueOnce({ status: true }); // Simulate successful token refresh

      // Mock apiClient for the retry, assuming it's called after refresh
      // This is tricky because apiClient itself uses the interceptor.
      // For simplicity, we assume the retry would succeed or fail separately.
      // Here, we just check if apiClient(originalRequest) is called.
      // Since apiClient is the mockAxiosInstance, we can check its methods.
      // If the original request was a POST:
      mockError.config.method = 'post';
      axios.post.mockResolvedValueOnce({ data: 'retry success' });


      await responseInterceptor(mockError);

      expect(mockStore.dispatch).toHaveBeenCalledWith('refreshToken');
      expect(mockError.config._retry).toBe(true);
      // Check if the original request was retried (e.g., axios.post was called again)
      // This depends on how apiClient(originalRequest) is implemented.
      // If apiClient is the mockAxiosInstance, then a method on it should be called.
      expect(axios.post).toHaveBeenCalledWith(mockError.config);
    });

    it('handles UNAUTHENTICATED (BE_GEN_003) and logs out on failed token refresh', async () => {
      const mockError = {
        isAxiosError: true,
        config: { _retry: false },
        response: {
          data: { error_code: 'BE_GEN_003', status_message: 'Unauthorized' },
          status: 401,
        },
      };
      mockStore.dispatch.mockResolvedValueOnce({ status: false }); // Simulate failed token refresh

      try {
        await responseInterceptor(mockError);
      } catch (e) {
        expect(mockStore.dispatch).toHaveBeenCalledWith('refreshToken');
        expect(mockStore.dispatch).toHaveBeenCalledWith('logout');
        expect(e.isStructuredError).toBe(true);
        expect(e.errorCode).toBe('BE_GEN_003');
      }
    });

    it('handles UNAUTHENTICATED (BE_GEN_003) and logs out if already retried', async () => {
      const mockError = {
        isAxiosError: true,
        config: { _retry: true }, // Already retried
        response: {
          data: { error_code: 'BE_GEN_003', status_message: 'Unauthorized' },
          status: 401,
        },
      };

      try {
        await responseInterceptor(mockError);
      } catch (e) {
        expect(mockStore.dispatch).not.toHaveBeenCalledWith('refreshToken');
        expect(mockStore.dispatch).toHaveBeenCalledWith('logout');
        expect(e.isStructuredError).toBe(true);
        expect(e.errorCode).toBe('BE_GEN_003');
      }
    });

    it('handles CSRF_TOKEN_INVALID (BE_GEN_010) and retries on successful CSRF token refresh', async () => {
      const mockError = {
        isAxiosError: true,
        config: { _retryCSRF: false, method: 'post' },
        response: {
          data: { error_code: 'BE_GEN_010', status_message: 'Invalid CSRF token' },
          status: 403, // Typically CSRF errors are 403
        },
      };
      mockStore.dispatch.mockResolvedValueOnce(undefined); // Simulate successful getCsrfToken
      axios.post.mockResolvedValueOnce({ data: 'csrf retry success' });

      await responseInterceptor(mockError);

      expect(mockStore.dispatch).toHaveBeenCalledWith('getCsrfToken');
      expect(mockError.config._retryCSRF).toBe(true);
      expect(axios.post).toHaveBeenCalledWith(mockError.config);
    });
  });

  describe('Response Interceptor - Non-Structured Errors', () => {
    it('handles non-structured HTTP errors', async () => {
      const mockError = {
        isAxiosError: true,
        config: {},
        response: {
          data: { message: 'Old style error' }, // Not our new structure
          status: 500,
        },
      };
      try {
        await responseInterceptor(mockError);
      } catch (e) {
        expect(e.isStructuredError).toBe(false);
        expect(e.message).toBe('Old style error');
        expect(e.statusCode).toBe(500);
        expect(e.originalError).toBe(mockError);
      }
    });

    it('handles network errors', async () => {
      const mockError = {
        isAxiosError: true,
        config: {},
        message: 'Network Error', // No error.response
      };
      try {
        await responseInterceptor(mockError);
      } catch (e) {
        expect(e.isStructuredError).toBe(false);
        expect(e.message).toBe('Network Error');
        expect(e.originalError).toBe(mockError);
      }
    });
  });
});
