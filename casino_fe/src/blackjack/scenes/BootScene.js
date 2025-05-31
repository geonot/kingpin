import Phaser from 'phaser';

export default class BootScene extends Phaser.Scene {
  constructor() {
    super({ key: 'BootScene' });
  }

  preload() {
    console.log('BootScene: Preload');
    
    // Load minimal assets needed for loading screen
    this.load.image('loader-bg', '/assets/ui/loader_bg.png');
    this.load.image('loader-fill', '/assets/ui/loader_fill.png');
  }

  create() {
    console.log('BootScene: Create');
    
    // Get game configuration from registry (set by Vue component)
    const tableId = this.registry.get('tableId');
    const gameConfig = this.game.config.gameConfig; // Default config from main.js
    
    // Merge with any table-specific config from the backend
    const tableConfig = this.registry.get('tableConfig');
    
    // Create merged config
    const mergedConfig = {
      ...gameConfig,
      table: {
        id: tableId,
        ...tableConfig
      }
    };
    
    // Ensure positions property exists
    if (!mergedConfig.positions) {
      console.warn('BootScene: positions property not found in gameConfig, using default positions');
      mergedConfig.positions = {
        dealer: {
          x: 400,
          y: 150,
          spacing: 30
        },
        player: {
          x: 400,
          y: 350,
          spacing: 30,
          hands: {
            spacing: 200 // Spacing between split hands
          }
        }
      };
    }
    
    // Ensure rules property exists
    if (!mergedConfig.rules) {
      console.warn('BootScene: rules property not found in gameConfig, using default rules');
      mergedConfig.rules = {
        blackjackPayout: 1.5,      // Blackjack pays 3:2
        dealerStandsOn: 'soft17',  // Dealer stands on soft 17
        doubleAfterSplit: true,    // Can double after split
        hitSplitAces: false,       // Cannot hit split aces
        maxSplitHands: 4,          // Maximum number of hands after splits
        insurance: true,           // Insurance offered
        surrenderAllowed: false    // Surrender not allowed
      };
    }
    
    // Store the merged config in the registry for other scenes
    this.registry.set('gameConfig', mergedConfig);
    
    // Set up any game-wide settings
    this.registry.set('soundEnabled', true);
    
    // Initialize any game state
    this.registry.set('gameState', {
      round: 0,
      playerHands: [],
      dealerHand: null,
      currentHandIndex: 0,
      deck: [],
      isPlaying: false
    });
    
    // Transition to the preload scene
    console.log('BootScene: Starting PreloadScene...');
    this.scene.start('PreloadScene');
  }
}