// src/event-bus.js
// Using Mitt for a lightweight event emitter
import mitt from 'mitt';

const emitter = mitt();

// Optionally wrap for easier debugging or typing
export const EventBus = {
  $on: (...args) => emitter.on(...args),
  $off: (...args) => emitter.off(...args),
  $emit: (...args) => emitter.emit(...args),
  $clear: () => emitter.all.clear(), // Method to clear all listeners if needed
};

// No need to attach to Vue global properties in Vue 3 setup script style
export default EventBus;

