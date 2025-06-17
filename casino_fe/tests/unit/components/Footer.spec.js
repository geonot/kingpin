import { shallowMount } from '@vue/test-utils';
import Footer from '@/components/Footer.vue';

describe('Footer.vue', () => {
  let wrapper;

  beforeEach(() => {
    wrapper = shallowMount(Footer, {
      global: {
        stubs: {
          'router-link': {
            template: '<a :href="to"><slot /></a>',
            props: ['to']
          }
        }
      }
    });
  });

  test('renders copyright text with current year', () => {
    const currentYear = new Date().getFullYear();
    // Using a regex to match the copyright text, including the dynamic year
    expect(wrapper.text()).toMatch(`© ${currentYear} Kingpin Casino. All rights reserved.`);
  });

  test('renders responsible gambling message', () => {
    expect(wrapper.text()).toContain('Please gamble responsibly. For help, visit BeGambleAware.org.');
  });

  test('renders link to Terms page', () => {
    // Find by href since we're stubbing router-link as an anchor
    const termsLink = wrapper.find('a[href="/terms"]');
    expect(termsLink.exists()).toBe(true);
  });

  test('renders link to Privacy Policy page', () => {
    const privacyLink = wrapper.find('a[href="/privacy"]');
    expect(privacyLink.exists()).toBe(true);
  });

  test('renders link to Responsible Gaming page', () => {
    const responsibleGamingLink = wrapper.find('a[href="/responsible-gaming"]');
    expect(responsibleGamingLink.exists()).toBe(true);
  });

  test('matches snapshot', () => {
    // Re-mount for snapshot if previous interactions could alter it, or use the existing wrapper
    // For a simple component like Footer, the initial mount is usually fine.
    expect(wrapper.html()).toMatchSnapshot();
  });
});
