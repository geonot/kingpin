import { shallowMount } from '@vue/test-utils';
import Footer from '@/components/Footer.vue';

describe('Footer.vue', () => {
  let wrapper;

  beforeEach(() => {
    wrapper = shallowMount(Footer, {
      global: {
        stubs: {
          'router-link': true // Basic stub for <router-link>
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
    // Find by attribute `to`
    const termsLink = wrapper.find('router-link[to="/terms"]');
    expect(termsLink.exists()).toBe(true);
    // Check text content if available, assuming stub renders children or has text
    // For a basic stub like `true`, it might not render text.
    // If using a component stub like `<template><slot/></template>`, text can be checked.
    // For this simple case, checking existence and `to` prop is often enough.
  });

  test('renders link to Privacy Policy page', () => {
    const privacyLink = wrapper.find('router-link[to="/privacy"]');
    expect(privacyLink.exists()).toBe(true);
  });

  test('renders link to Responsible Gaming page', () => {
    const responsibleGamingLink = wrapper.find('router-link[to="/responsible-gaming"]');
    expect(responsibleGamingLink.exists()).toBe(true);
  });

  test('matches snapshot', () => {
    // Re-mount for snapshot if previous interactions could alter it, or use the existing wrapper
    // For a simple component like Footer, the initial mount is usually fine.
    expect(wrapper.html()).toMatchSnapshot();
  });
});
