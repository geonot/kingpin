import { shallowMount, flushPromises } from '@vue/test-utils';
import ErrorMessage from '@/components/ErrorMessage.vue';
import { createStore } from 'vuex';
import { createRouter, createWebHistory } from 'vue-router';

// Mock Vuex store
const createMockStore = (initialError = null) => {
  return createStore({
    state: {
      globalError: initialError,
    },
    mutations: {
      setGlobalError(state, errorPayload) {
        state.globalError = errorPayload;
      },
      clearGlobalError(state) {
        state.globalError = null;
      },
    },
    actions: {
      // Mock any actions that might be dispatched by actionButton
      mockTestAction: jest.fn(),
    },
  });
};

// Mock Vue Router
const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: { template: '<div>Home</div>' } },
    { path: '/login', component: { template: '<div>Login</div>' } },
    { path: '/deposit', component: { template: '<div>Deposit</div>' } },
  ],
});


describe('@/components/ErrorMessage.vue', () => {
  let mockStore;

  beforeEach(() => {
    // Create a fresh store for each test
    mockStore = createMockStore();
    // Mock router push
    router.push = jest.fn();
  });

  const mountComponent = (errorProp = null, messageProp = '') => {
    return shallowMount(ErrorMessage, {
      props: {
        error: errorProp,
        message: messageProp,
      },
      global: {
        plugins: [mockStore, router], // Provide store and router
      },
    });
  };

  it('renders nothing when no error or message is provided', () => {
    const wrapper = mountComponent();
    expect(wrapper.find('.error-message-box').exists()).toBe(false);
  });

  it('renders with legacy message prop', () => {
    const wrapper = mountComponent(null, 'Legacy error message');
    expect(wrapper.find('.error-message-box').exists()).toBe(true);
    expect(wrapper.find('.message').text()).toBe('Legacy error message');
  });

  describe('Structured Error Handling', () => {
    it('displays message from structured error', () => {
      const error = {
        isStructuredError: true,
        message: 'This is a structured error.',
        errorCode: 'TEST_001',
      };
      const wrapper = mountComponent(error);
      expect(wrapper.find('.message').text()).toBe('This is a structured error.');
    });

    it('uses enhancedMessage for UNAUTHENTICATED (BE_GEN_003) if no actionButton', () => {
      const error = {
        isStructuredError: true,
        message: 'Original unauthenticated message.',
        errorCode: 'BE_GEN_003',
        actionButton: null, // No action button
      };
      const wrapper = mountComponent(error);
      expect(wrapper.find('.message').text()).toBe('Your session has expired. Please log in again.');
    });

    it('uses enhancedMessage for INSUFFICIENT_FUNDS (BE_FIN_200) if no actionButton', () => {
      const error = {
        isStructuredError: true,
        message: 'Original insufficient funds.',
        errorCode: 'BE_FIN_200',
      };
      const wrapper = mountComponent(error);
      expect(wrapper.find('.message').text()).toBe('You have insufficient funds for this action. Please consider making a deposit.');
    });

    it('uses original message if errorCode for enhancedMessage does not match or actionButton exists', () => {
      const error = {
        isStructuredError: true,
        message: 'Specific error message from backend.',
        errorCode: 'SOME_OTHER_CODE',
      };
      const wrapper = mountComponent(error);
      expect(wrapper.find('.message').text()).toBe('Specific error message from backend.');

      const errorWithAction = {
         isStructuredError: true,
        message: 'Original unauthenticated message.',
        errorCode: 'BE_GEN_003',
        actionButton: { text: 'Login', actionType: 'NAVIGATE_TO_ROUTE', actionPayload: '/login' }
      };
      const wrapper2 = mountComponent(errorWithAction);
      expect(wrapper2.find('.message').text()).toBe('Original unauthenticated message.');

    });
  });

  describe('Non-Structured Error Handling', () => {
    it('displays message from non-structured error object', () => {
      const error = {
        isStructuredError: false,
        message: 'This is a non-structured error (e.g., network).',
      };
      const wrapper = mountComponent(error);
      expect(wrapper.find('.message').text()).toBe('This is a non-structured error (e.g., network).');
    });

    it('displays default message if non-structured error has no message', () => {
      const error = { isStructuredError: false };
      const wrapper = mountComponent(error);
      expect(wrapper.find('.message').text()).toBe('An unexpected error occurred.');
    });
  });

  describe('Action Button', () => {
    it('renders action button if provided in structured error', () => {
      const error = {
        isStructuredError: true,
        message: 'Error with action.',
        errorCode: 'ACT_001',
        actionButton: { text: 'Go Home', actionType: 'NAVIGATE_TO_ROUTE', actionPayload: { route: '/' } },
      };
      const wrapper = mountComponent(error);
      const button = wrapper.find('.error-message-box button.bg-blue-600'); // More specific selector
      expect(button.exists()).toBe(true);
      expect(button.text()).toBe('Go Home');
    });

    it('handles NAVIGATE_TO_ROUTE action', async () => {
      const error = {
        isStructuredError: true,
        message: 'Navigate action.',
        errorCode: 'NAV_001',
        actionButton: { text: 'Login Page', actionType: 'NAVIGATE_TO_ROUTE', actionPayload: { route: '/login' } },
      };
      const wrapper = mountComponent(error);
      const actionBtn = wrapper.find('.error-message-box button.bg-blue-600');
      await actionBtn.trigger('click');
      expect(router.push).toHaveBeenCalledWith({ route: '/login' });
      await flushPromises(); // Wait for dismiss operations
      expect(wrapper.find('.error-message-box').exists()).toBe(false); // Should be dismissed
    });

    it('handles DISPATCH_VUEX_ACTION action', async () => {
      const error = {
        isStructuredError: true,
        message: 'Dispatch action.',
        errorCode: 'DISPATCH_001',
        actionButton: {
          text: 'Test Dispatch',
          actionType: 'DISPATCH_VUEX_ACTION',
          actionPayload: { actionName: 'mockTestAction', payload: { data: 'test' } }
        },
      };
      const wrapper = mountComponent(error);
      const actionBtn = wrapper.find('.error-message-box button.bg-blue-600');
      await actionBtn.trigger('click');
      expect(mockStore.dispatch).toHaveBeenCalledWith('mockTestAction', { data: 'test' });
      await flushPromises();
      expect(wrapper.find('.error-message-box').exists()).toBe(false);
    });
  });

  describe('Dismiss Functionality', () => {
    it('dismisses when dismiss button is clicked', async () => {
      const wrapper = mountComponent(null, 'Test dismiss');
      expect(wrapper.find('.error-message-box').exists()).toBe(true);
      await wrapper.find('button.dismiss-button').trigger('click');
      expect(wrapper.find('.error-message-box').exists()).toBe(false);
      expect(wrapper.emitted('dismiss')).toBeTruthy();
    });

    it('clears globalError from store if it matches the dismissed error', async () => {
      const errorToDisplay = { isStructuredError: true, message: 'Global error test', errorCode: 'GLOBAL_TEST' };
      mockStore.commit('setGlobalError', errorToDisplay); // Set this error as the global one
      
      const wrapper = mountComponent(errorToDisplay);
      expect(mockStore.state.globalError).toEqual(errorToDisplay);
      
      await wrapper.find('button.dismiss-button').trigger('click');
      
      expect(mockStore.state.globalError).toBeNull();
    });

    it('does not clear globalError if it does not match the dismissed error', async () => {
      const globalErrorInStore = { isStructuredError: true, message: 'Some other global error', errorCode: 'OTHER_GLOBAL' };
      mockStore.commit('setGlobalError', globalErrorInStore);
      
      const errorForComponent = { isStructuredError: true, message: 'Local component error', errorCode: 'LOCAL_TEST' };
      const wrapper = mountComponent(errorForComponent); // ErrorMessage displays a different error
      
      await wrapper.find('button.dismiss-button').trigger('click');
      
      expect(mockStore.state.globalError).toEqual(globalErrorInStore); // Global error should remain unchanged
    });
  });
});
