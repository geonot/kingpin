import { config } from '@vue/test-utils';

// Mock global objects that may be used in components
global.console = {
  ...console,
  // Suppress console warnings in tests unless needed
  warn: jest.fn(),
  error: jest.fn(),
};

// Mock Phaser if any components use it
global.Phaser = {
  Game: jest.fn(),
  Scene: jest.fn(),
  AUTO: 'AUTO',
};

// Mock localStorage globally
const localStorageMock = {
  getItem: jest.fn(),
  setItem: jest.fn(),
  removeItem: jest.fn(),
  clear: jest.fn(),
};
Object.defineProperty(global, 'localStorage', {
  value: localStorageMock,
  writable: true
});

// Setup Vue Test Utils global config
config.global.mocks = {
  $router: {
    push: jest.fn(),
    replace: jest.fn(),
    go: jest.fn(),
    back: jest.fn(),
  },
  $route: {
    path: '/',
    params: {},
    query: {},
  },
};

// Global stubs for common components
config.global.stubs = {
  'router-link': {
    template: '<a :href="to"><slot /></a>',
    props: ['to']
  }
};

// Mock API service
jest.mock('@/services/api', () => ({
  login: jest.fn(),
  register: jest.fn(),
  logout: jest.fn(),
  getUserProfile: jest.fn(),
  getSlots: jest.fn(),
  spin: jest.fn(),
}));
