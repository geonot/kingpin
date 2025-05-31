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
    // These paths should be absolute or relative to the game's base URL.
    // Assuming they are in the public/assets/ui directory.
    this.load.image('loader-bg', '/assets/ui/loader_bg.png');
    this.load.image('loader-fill', '/assets/ui/loader_fill.png');
  }

  create() {
    console.log('BootScene: Create');
    // Slot.vue is responsible for fetching the slot configuration (slotInfo)
    // and passing it to Phaser through the registry as 'slotConfigData'.
    // It also passes 'slotId'.

    const slotId = this.registry.get('slotId');
    const slotConfigData = this.registry.get('slotConfigData'); // This is the parsed gameConfig.json content

    if (!slotId || !slotConfigData) {
      const errorMessage = 'Critical Error: Slot ID or Slot Configuration Data not found in registry.';
      console.error(`BootScene: ${errorMessage}`);
      this.showError(errorMessage);
      // Potentially emit an event to Vue to handle this critical failure
      const eventBus = this.registry.get('eventBus') || EventBus; // Fallback to imported EventBus
      if (eventBus) {
        eventBus.emit('phaserError', errorMessage);
      }
      this.scene.stop(); // Stop further scene processing
      return;
    }
    
    // The slotConfigData should already be the object that was gameConfig.json's content.
    // If slotConfigData is the full slot object from backend (which includes short_name, etc.),
    // and the actual game config is a sub-object (e.g., slotConfigData.game_config_json), adjust accordingly.
    // Based on Slot.vue, slotInfo (which becomes slotConfigData) is the direct content of gameConfig.json.
    // So, slotConfigData itself is what we need for gameConfig.

    // Ensure 'gameConfig' in registry is the specific 'game' object from the JSON structure.
    // The current Slot.vue passes the entire slot object from the store as slotConfigData.
    // The actual game design config (reels, symbols, paylines) is typically a part of this.
    // Let's assume slotConfigData *is* the game configuration object (equivalent to gameConfig.json's content)
    // And that it has a 'game' property as per original BootScene structure.

    // If slotConfigData is the result from /api/slots/:id (which includes name, description, short_name, AND the game config content)
    // we need to extract the actual game config part.
    // Let's assume Slot.vue sets `slotConfigData` to be the direct JSON content that was in `public/slotX/gameConfig.json`

    let gameSpecificConfig;
    if (slotConfigData.game && typeof slotConfigData.game === 'object') {
        // This implies slotConfigData was an object like { "game": {...}, "other_meta_data_from_slot_model": ... }
        // This was the structure expected by the old BootScene if it loaded the config itself.
        // If Slot.vue sets slotConfigData to the content of gameConfig.json (which is game_config.game from backend model),
        // then slotConfigData *is* gameSpecificConfig.
        gameSpecificConfig = slotConfigData.game;
    } else if (slotConfigData.layout && slotConfigData.symbols) {
        // This implies slotConfigData is already the "game" object itself.
        gameSpecificConfig = slotConfigData;
    } else {
        const errorMessage = 'Critical Error: Invalid Slot Configuration Data structure in registry.';
        console.error(`BootScene: ${errorMessage}`, slotConfigData);
        this.showError(errorMessage);
        const eventBus = this.registry.get('eventBus') || EventBus;
        if (eventBus) eventBus.emit('phaserError', errorMessage);
        this.scene.stop();
        return;
    }

    if (!gameSpecificConfig) {
        const errorMessage = 'Critical Error: Game specific configuration (reels, symbols, etc.) is missing.';
        console.error(`BootScene: ${errorMessage}`, slotConfigData);
        this.showError(errorMessage);
        const eventBus = this.registry.get('eventBus') || EventBus;
        if (eventBus) eventBus.emit('phaserError', errorMessage);
        this.scene.stop();
        return;
    }

    this.registry.set('gameConfig', gameSpecificConfig);
    // Also store short_name if available at the root of slotConfigData (from Slot.vue's slotInfo) for PreloadScene
    if (slotConfigData.short_name) {
        this.registry.set('slotShortName', slotConfigData.short_name);
    } else if (gameSpecificConfig.short_name) { // Or if it's inside the game object
         this.registry.set('slotShortName', gameSpecificConfig.short_name);
    } else {
        // Fallback or error if short_name is essential for asset paths and not found
        console.warn("BootScene: slotShortName not found in slotConfigData. Asset paths might be incorrect if they rely on it.");
        // Attempt to derive from slotId if convention is /slotX/
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


