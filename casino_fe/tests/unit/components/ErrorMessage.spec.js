import { mount, shallowMount } from '@vue/test-utils';
import { createRouter, createWebHistory } from 'vue-router';
import ErrorMessage from '@/components/ErrorMessage.vue';

// Mock router
const createMockRouter = () => {
  return createRouter({
    history: createWebHistory(),
    routes: [
      { path: '/deposit', component: { template: '<div>Deposit</div>' } }
    ]
  });
};

describe('ErrorMessage.vue', () => {
  let wrapper;
  let router;

  beforeEach(() => {
    router = createMockRouter();
  });

  afterEach(() => {
    if (wrapper) {
      wrapper.unmount();
    }
  });

  const mountErrorMessage = (props = {}, options = {}) => {
    return mount(ErrorMessage, {
      props: {
        error: null,
        ...props
      },
      global: {
        plugins: [router]
      },
      ...options
    });
  };

  describe('Component Rendering', () => {
    it('renders nothing when no error is provided', () => {
      wrapper = mountErrorMessage();
      expect(wrapper.find('.error-message-box').exists()).toBe(false);
    });

    it('renders nothing when error is null', () => {
      wrapper = mountErrorMessage({ error: null });
      expect(wrapper.find('.error-message-box').exists()).toBe(false);
    });

    it('renders error message when error is provided', () => {
      const error = {
        status_message: 'Test error message'
      };
      
      wrapper = mountErrorMessage({ error });
      
      expect(wrapper.find('.error-message-box').exists()).toBe(true);
      expect(wrapper.text()).toContain('Test error message');
    });

    it('shows error icon and "Error!" label', () => {
      const error = {
        status_message: 'Test error'
      };
      
      wrapper = mountErrorMessage({ error });
      
      expect(wrapper.find('svg').exists()).toBe(true);
      expect(wrapper.text()).toContain('Error!');
    });

    it('shows dismiss button', () => {
      const error = {
        status_message: 'Test error'
      };
      
      wrapper = mountErrorMessage({ error });
      
      const dismissButton = wrapper.find('.dismiss-button');
      expect(dismissButton.exists()).toBe(true);
      expect(dismissButton.attributes('aria-label')).toBe('Dismiss');
    });
  });

  describe('Error Message Display', () => {
    it('displays simple string error message', () => {
      const error = {
        status_message: 'Simple error message'
      };
      
      wrapper = mountErrorMessage({ error });
      
      expect(wrapper.find('.message').text()).toBe('Simple error message');
    });

    it('displays default message for empty status_message', () => {
      const error = {
        status_message: ''
      };
      
      wrapper = mountErrorMessage({ error });
      
      expect(wrapper.find('.message').text()).toBe('An unknown error occurred.');
    });

    it('displays default message for undefined status_message', () => {
      const error = {};
      
      wrapper = mountErrorMessage({ error });
      
      expect(wrapper.find('.message').text()).toBe('An unknown error occurred.');
    });

    it('handles error object without status_message property', () => {
      const error = {
        message: 'Different property name'
      };
      
      wrapper = mountErrorMessage({ error });
      
      expect(wrapper.find('.message').text()).toBe('Different property name');
    });
  });

  describe('Special Error Handling', () => {
    it('shows deposit action button for insufficient balance error', () => {
      const error = {
        status_message: 'Insufficient balance to place bet',
        actionButton: {
          text: 'Deposit',
          action: jest.fn()
        }
      };
      
      wrapper = mountErrorMessage({ error });
      
      const actionButton = wrapper.find('[class*="bg-blue-600"]'); // Look for the action button by its class
      expect(actionButton.exists()).toBe(true);
      expect(actionButton.text()).toContain('Deposit');
    });

    it('shows different styles for different error types', () => {
      const error = {
        status_message: 'Insufficient balance to place bet'
      };
      
      wrapper = mountErrorMessage({ error });
      
      // Should have special styling for balance errors
      expect(wrapper.find('.error-message-box').classes()).toContain('bg-red-100');
    });

    it('handles network errors appropriately', () => {
      const error = {
        status_message: 'Network error. Please check your connection.'
      };
      
      wrapper = mountErrorMessage({ error });
      
      expect(wrapper.text()).toContain('Network error');
    });
  });

  describe('Action Buttons', () => {
    it('navigates to deposit page when deposit button is clicked', async () => {
      const error = {
        status_message: 'Insufficient balance to place bet'
      };
      
      const routerPush = jest.spyOn(router, 'push');
      
      wrapper = mountErrorMessage({ error });
      
      const depositButton = wrapper.find('button').filter(btn => btn.text().includes('Deposit'));
      expect(depositButton.exists()).toBe(true);
      await depositButton.trigger('click');
      
      expect(routerPush).toHaveBeenCalledWith('/deposit');
    });

    it('does not show action button for general errors', () => {
      const error = {
        status_message: 'General error message'
      };
      
      wrapper = mountErrorMessage({ error });
      
      expect(wrapper.find('.action-button').exists()).toBe(false);
    });
  });

  describe('Dismiss Functionality', () => {
    it('emits dismiss event when dismiss button is clicked', async () => {
      const error = {
        status_message: 'Test error'
      };
      
      wrapper = mountErrorMessage({ error });
      
      const dismissButton = wrapper.find('.dismiss-button');
      await dismissButton.trigger('click');
      
      expect(wrapper.emitted('dismiss')).toBeTruthy();
      expect(wrapper.emitted('dismiss')).toHaveLength(1);
    });

    it('hides error message after dismiss', async () => {
      const error = {
        status_message: 'Test error'
      };
      
      wrapper = mountErrorMessage({ error });
      
      expect(wrapper.find('.error-message-box').exists()).toBe(true);
      
      // Simulate dismiss by clicking the dismiss button
      const dismissButton = wrapper.find('.dismiss-button');
      await dismissButton.trigger('click');
      
      expect(wrapper.find('.error-message-box').exists()).toBe(false);
    });
  });

  describe('Auto-dismiss', () => {
    beforeEach(() => {
      jest.useFakeTimers();
    });

    afterEach(() => {
      jest.useRealTimers();
    });

    it('auto-dismisses after timeout for non-critical errors', async () => {
      const error = {
        status_message: 'Non-critical error'
      };
      
      wrapper = mountErrorMessage({ error, autoDismiss: true });
      
      expect(wrapper.find('.error-message-box').exists()).toBe(true);
      
      // Fast-forward time
      jest.advanceTimersByTime(5000);
      await wrapper.vm.$nextTick();
      
      expect(wrapper.emitted('dismiss')).toBeTruthy();
    });

    it('does not auto-dismiss critical errors', async () => {
      const error = {
        status_message: 'Critical error that requires attention'
      };
      
      wrapper = mountErrorMessage({ error, autoDismiss: false });
      
      jest.advanceTimersByTime(10000);
      await wrapper.vm.$nextTick();
      
      expect(wrapper.emitted('dismiss')).toBeFalsy();
    });
  });

  describe('Accessibility', () => {
    it('has proper ARIA role', () => {
      const error = {
        status_message: 'Test error'
      };
      
      wrapper = mountErrorMessage({ error });
      
      expect(wrapper.find('.error-message-box').attributes('role')).toBe('alert');
    });

    it('has screen reader text for dismiss button', () => {
      const error = {
        status_message: 'Test error'
      };
      
      wrapper = mountErrorMessage({ error });
      
      expect(wrapper.find('.sr-only').text()).toBe('Dismiss');
    });

    it('has proper focus management for dismiss button', () => {
      const error = {
        status_message: 'Test error'
      };
      
      wrapper = mountErrorMessage({ error });
      
      const dismissButton = wrapper.find('.dismiss-button');
      expect(dismissButton.attributes('aria-label')).toBe('Dismiss');
    });
  });

  describe('Dark Mode Support', () => {
    it('has dark mode classes', () => {
      const error = {
        status_message: 'Test error'
      };
      
      wrapper = mountErrorMessage({ error });
      
      const errorBox = wrapper.find('.error-message-box');
      expect(errorBox.classes()).toContain('dark:bg-red-900');
      expect(errorBox.classes()).toContain('dark:text-red-300');
      expect(errorBox.classes()).toContain('dark:border-red-600');
    });

    it('has dark mode dismiss button styles', () => {
      const error = {
        status_message: 'Test error'
      };
      
      wrapper = mountErrorMessage({ error });
      
      const dismissButton = wrapper.find('.dismiss-button');
      expect(dismissButton.classes()).toContain('dark:bg-red-900');
      expect(dismissButton.classes()).toContain('dark:text-red-300');
      expect(dismissButton.classes()).toContain('dark:hover:bg-red-800');
    });
  });

  describe('Edge Cases', () => {
    it('handles very long error messages', () => {
      const error = {
        status_message: 'A'.repeat(1000) // Very long message
      };
      
      wrapper = mountErrorMessage({ error });
      
      expect(wrapper.find('.error-message-box').exists()).toBe(true);
      expect(wrapper.text()).toContain('A'.repeat(100)); // Should contain part of message
    });

    it('handles HTML in error messages safely', () => {
      const error = {
        status_message: '<script>alert("xss")</script>Safe message'
      };
      
      wrapper = mountErrorMessage({ error });
      
      // Should not execute script, just display as text
      expect(wrapper.find('script').exists()).toBe(false);
      expect(wrapper.text()).toContain('Safe message');
    });

    it('handles error object updates', async () => {
      const initialError = {
        status_message: 'Initial error'
      };
      
      wrapper = mountErrorMessage({ error: initialError });
      
      expect(wrapper.text()).toContain('Initial error');
      
      // Update error
      await wrapper.setProps({
        error: {
          status_message: 'Updated error'
        }
      });
      
      expect(wrapper.text()).toContain('Updated error');
    });

    it('handles error prop changing to null', async () => {
      const error = {
        status_message: 'Test error'
      };
      
      wrapper = mountErrorMessage({ error });
      
      expect(wrapper.find('.error-message-box').exists()).toBe(true);
      
      // Change to null
      await wrapper.setProps({ error: null });
      
      expect(wrapper.find('.error-message-box').exists()).toBe(false);
    });
  });
});
