import Phaser from 'phaser';
import EventBus from '@/event-bus'; // For global events if needed

export default class BootScene extends Phaser.Scene {

  constructor() {
    super({ key: 'BootScene' });
  }

  preload() {
    // Display a simple loading message during boot
    this.add.text(
      this.cameras.main.width / 2,
      this.cameras.main.height / 2,
      'Booting Game...',
      { font: '24px Arial', fill: '#ffffff' }
    ).setOrigin(0.5);

    // Load common UI assets needed for the PreloadScene's loading bar
    // These are served from the Vue.js public/ui directory
    this.load.image('loader-bg', '/ui/loader_bg.png');
    this.load.image('loader-fill', '/ui/loader_fill.png');
  }

  create() {
    console.log('BootScene: Create');
    // Slot.vue passes slot data through the registry with these keys:
    // - 'slotIdFromVue' (the slot ID)
    // - 'slotApiData' (the slot info from API)
    // - 'slotGameJsonConfig' (the gameConfig.json content)

    const slotId = this.registry.get('slotIdFromVue');
    const slotApiData = this.registry.get('slotApiData');
    const slotGameJsonConfig = this.registry.get('slotGameJsonConfig');

    if (!slotId || !slotGameJsonConfig) {
      const errorMessage = 'Critical Error: Slot ID or Slot Configuration Data not found in registry.';
      console.error(`BootScene: ${errorMessage}`);
      this.showError(errorMessage);
      // Emit event to Vue to handle this critical failure
      const eventBus = this.registry.get('eventBus');
      if (eventBus && typeof eventBus.$emit === 'function') {
        eventBus.$emit('phaserError', errorMessage);
      }
      this.scene.stop(); // Stop further scene processing
      return;
    }
    
    // slotGameJsonConfig is the content from gameConfig.json
    // It should have the game configuration structure
    let gameSpecificConfig;
    if (slotGameJsonConfig.game && typeof slotGameJsonConfig.game === 'object') {
        // gameConfig.json has structure: { "game": {...}, "metadata": ... }
        gameSpecificConfig = slotGameJsonConfig.game;
    } else if (slotGameJsonConfig.layout && slotGameJsonConfig.symbols) {
        // gameConfig.json is directly the game config object
        gameSpecificConfig = slotGameJsonConfig;
    } else {
        const errorMessage = 'Critical Error: Invalid Slot Configuration Data structure in registry.';
        console.error(`BootScene: ${errorMessage}`, slotGameJsonConfig);
        this.showError(errorMessage);
        const eventBus = this.registry.get('eventBus');
        if (eventBus && typeof eventBus.$emit === 'function') {
          eventBus.$emit('phaserError', errorMessage);
        }
        this.scene.stop();
        return;
    }

    if (!gameSpecificConfig) {
        const errorMessage = 'Critical Error: Game specific configuration (reels, symbols, etc.) is missing.';
        console.error(`BootScene: ${errorMessage}`, slotGameJsonConfig);
        this.showError(errorMessage);
        const eventBus = this.registry.get('eventBus');
        if (eventBus && typeof eventBus.$emit === 'function') {
          eventBus.$emit('phaserError', errorMessage);
        }
        this.scene.stop();
        return;
    }

    this.registry.set('gameConfig', gameSpecificConfig);
    
    // Get short_name from API data for asset paths
    if (slotApiData && slotApiData.short_name) {
        this.registry.set('slotShortName', slotApiData.short_name);
    } else if (gameSpecificConfig.short_name) {
         this.registry.set('slotShortName', gameSpecificConfig.short_name);
    } else {
        // Fallback using slotId
        console.warn("BootScene: slotShortName not found. Using slot ID as fallback.");
        this.registry.set('slotShortName', `slot${slotId}`);
    }


    // Set default sound/turbo settings from game config, respecting values already in registry (passed from Vue)
    const soundEnabled = this.registry.get('soundEnabled');
    const turboEnabled = this.registry.get('turboEnabled');

    if (soundEnabled === undefined && gameSpecificConfig.settings?.soundDefault !== undefined) {
      this.registry.set('soundEnabled', gameSpecificConfig.settings.soundDefault);
    } else if (soundEnabled === undefined) {
      this.registry.set('soundEnabled', true); // Default true if not in config or Vue
    }

    if (turboEnabled === undefined && gameSpecificConfig.settings?.turboDefault !== undefined) {
      this.registry.set('turboEnabled', gameSpecificConfig.settings.turboDefault);
    } else if (turboEnabled === undefined) {
      this.registry.set('turboEnabled', false); // Default false if not in config or Vue
    }

    console.log('BootScene: Configuration processed. Starting PreloadScene...');
    this.scene.start('PreloadScene');
  }
  
  showError(message) {
    // Display error message to user
    this.add.text(
        this.cameras.main.width / 2,
        this.cameras.main.height / 2 + 50,
        message,
        { font: '18px Arial', fill: '#ff0000', align: 'center', wordWrap: { width: this.cameras.main.width - 40 } }
    ).setOrigin(0.5);
    
    EventBus.$emit('phaserError', message);
  }
}


