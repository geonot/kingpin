import Phaser from 'phaser';
import EventBus from '@/event-bus'; // For global events if needed

export default class BootScene extends Phaser.Scene {

  constructor() {
    super({ key: 'BootScene' });
  }

  // No preload needed here, moved to PreloadScene
  preload() {
     // Display a simple loading message during boot
     this.add.text(
        this.cameras.main.width / 2,
        this.cameras.main.height / 2,
        'Booting Game...',
        {
          font: '24px Arial',
          fill: '#ffffff'
        }
      ).setOrigin(0.5);

     // Load the game config JSON needed for PreloadScene
     // Get slotId from registry (passed from Vue component)
     const slotId = this.registry.get('slotId'); // Use registry now
     
     // If slotId is not available yet, wait for it to be set
     if (!slotId) {
        console.warn("BootScene: Slot ID not found in registry yet. Waiting for it to be set...");
        
        // Create a registry change listener to detect when slotId is set
        const registryChangeHandler = (key, data) => {
          if (key === 'slotId' && data) {
            console.log(`BootScene: Slot ID ${data} received from registry update.`);
            this.registry.events.off('changedata', registryChangeHandler);
            this.loadSlotConfig(data);
          }
        };
        
        this.registry.events.on('changedata', registryChangeHandler);
        
        // Set a timeout to handle the case where slotId is never set
        this.time.delayedCall(5000, () => {
          if (!this.registry.get('slotId')) {
            console.error("BootScene: Timed out waiting for Slot ID!");
            this.registry.events.off('changedata', registryChangeHandler);
            EventBus.$emit('phaserError', 'Configuration error: Slot ID missing after timeout.');
            this.scene.stop();
          }
        });
        
        return;
     }
     
     // If slotId is available immediately, load the config
     this.loadSlotConfig(slotId);
  }
  
  loadSlotConfig(slotId) {
      // Construct config path using asset_dir convention
      const configPath = `/slot${slotId}/gameConfig.json`;
      this.load.json(`gameConfig_${slotId}`, configPath); // Use unique key per slot

      // Load common UI assets needed early (like loading bar background)
      this.load.image('loader-bg', '/assets/ui/loader_bg.png');
      this.load.image('loader-fill', '/assets/ui/loader_fill.png');
      
      // Start loading
      this.load.start();
  }

  create() {
    console.log('BootScene: Create');
    const slotId = this.registry.get('slotId');
    
    // If slotId is still not available, we'll wait for the registry change event in preload
    if (!slotId) {
      console.warn('BootScene: Create called but slotId still not available in registry');
      return;
    }
    
    const configKey = `gameConfig_${slotId}`;

    try {
        // Check if the config is loaded
        if (!this.cache.json.exists(configKey)) {
            console.warn(`BootScene: Game config for slot ${slotId} not loaded yet. Waiting for load to complete.`);
            
            // Set up a one-time event listener for when the file loads
            this.load.once('filecomplete-json-' + configKey, () => {
                console.log(`BootScene: Game config for slot ${slotId} loaded asynchronously.`);
                this.processGameConfig(slotId);
            });
            
            // Set a timeout in case the load never completes
            this.time.delayedCall(5000, () => {
                if (!this.cache.json.exists(configKey)) {
                    console.error(`BootScene: Timed out waiting for game config to load for slot ${slotId}`);
                    this.showError('Timed out waiting for game configuration to load.');
                }
            });
            
            return;
        }
        
        // If we get here, the config is already loaded, so process it
        this.processGameConfig(slotId);

    } catch (error) {
        console.error('Error in BootScene create:', error);
        this.showError(`Error loading configuration: ${error.message}`);
    }
  }
  
  processGameConfig(slotId) {
    const configKey = `gameConfig_${slotId}`;
    
    try {
        const gameConfigData = this.cache.json.get(configKey);
        if (!gameConfigData) {
            throw new Error('Failed to load game config');
        }
        console.log(`BootScene: Game config for slot ${slotId} loaded successfully.`);

        // Store loaded config in the registry for other scenes
        this.registry.set('gameConfig', gameConfigData.game); // Store only the 'game' object

        // Set default settings in registry if not already set
        this.registry.set('soundEnabled', this.registry.get('soundEnabled') ?? gameConfigData.game.settings.soundDefault ?? true);
        this.registry.set('turboEnabled', this.registry.get('turboEnabled') ?? gameConfigData.game.settings.turboDefault ?? false);

        // Start the PreloadScene, passing the config key (or let PreloadScene get from registry)
        console.log('BootScene: Starting PreloadScene...');
        this.scene.start('PreloadScene'); // PreloadScene will get config from registry
    } catch (error) {
        console.error('Error processing game config:', error);
        this.showError(`Error processing configuration: ${error.message}`);
    }
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


