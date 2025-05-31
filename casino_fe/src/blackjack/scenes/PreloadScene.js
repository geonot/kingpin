import Phaser from 'phaser';

export default class PreloadScene extends Phaser.Scene {
  constructor() {
    super({ key: 'PreloadScene' });
  }

  preload() {
    console.log('PreloadScene: Preload');
    const gameConfig = this.registry.get('gameConfig'); // Get config from registry

    if (!gameConfig) {
      console.error("PreloadScene: Game config not found in registry!");
      // Handle error - perhaps return to main menu or show error
      return;
    }

    this.createLoadingBar();

    // --- Load Game Assets ---
    
    // 1. Card Assets
    // Load card back
    this.load.image('card-back', '/cards/back.png');
    
    // Load card faces - we'll use a naming convention like 'card-hearts-A', 'card-spades-10', etc.
    // Use default values if gameConfig.cards is undefined
    const suits_code = gameConfig.cards?.suits_code || ['H', 'D', 'C', 'S'];
    const suits_names = gameConfig.cards?.suits_names || ['hearts', 'diamonds', 'clubs', 'spades'];
    const values = gameConfig.cards?.values || ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A'];
    
    // Iterate through both arrays in parallel
    for (let i = 0; i < suits_code.length; i++) {
      const suitCode = suits_code[i];
      const suitName = suits_names[i];
      
      values.forEach(value => {
      this.load.image(`card-${suitName}-${value}`, `/cards/${value}${suitCode}@1x.png`);
      });
    }

    // 2. UI Button Images
    this.load.image('hit-button', '/assets/blackjack/hit-button.png');
    this.load.image('stand-button', '/assets/blackjack/stand-button.png');
    this.load.image('double-button', '/assets/blackjack/double-button.png');
    this.load.image('split-button', '/assets/blackjack/split-button.png');
    this.load.image('bet-button', '/assets/blackjack/bet-button.png');
    this.load.image('settings-button', '/assets/ui/settings.png');
    
    // 3. Background and Table
    this.load.image('background', '/assets/blackjack/background.png');
    this.load.image('table', '/assets/blackjack/table.png');
    
    // 4. Chip Images
    this.load.image('chip-10', '/assets/blackjack/chip-10.png');
    this.load.image('chip-20', '/assets/blackjack/chip-20.png');
    this.load.image('chip-50', '/assets/blackjack/chip-50.png');
    this.load.image('chip-100', '/assets/blackjack/chip-100.png');
    this.load.image('chip-500', '/assets/blackjack/chip-500.png');
    this.load.image('chip-1000', '/assets/blackjack/chip-1000.png');
    
    // 5. Sound Effects
    this.load.audio('card-deal', '/assets/blackjack/sounds/card-deal.mp3');
    this.load.audio('card-flip', '/assets/blackjack/sounds/card-flip.mp3');
    this.load.audio('chip-place', '/assets/blackjack/sounds/chip-place.mp3');
    this.load.audio('win', '/assets/blackjack/sounds/win.mp3');
    this.load.audio('lose', '/assets/blackjack/sounds/lose.mp3');
    this.load.audio('push', '/assets/blackjack/sounds/push.mp3');
    this.load.audio('blackjack', '/assets/blackjack/sounds/blackjack.mp3');
    this.load.audio('button-click', '/assets/blackjack/sounds/button-click.mp3');

    // --- Loading Progress ---
    this.load.on('progress', (value) => {
      this.updateLoadingBar(value);
    });

    this.load.on('complete', () => {
      console.log('PreloadScene: Asset loading complete.');
      this.loadingFill?.destroy(); // Clean up loading bar elements
      this.loadingBg?.destroy();
      this.loadingText?.destroy();
      this.percentText?.destroy();

      // Start the main game scenes
      console.log('PreloadScene: Starting GameScene and UIScene...');
      this.scene.start('GameScene');
      this.scene.start('UIScene'); // Start UI scene concurrently
    });

    this.load.on('loaderror', (file) => {
      console.error('PreloadScene: Error loading file:', file.key, file.src);
      // Optionally display error to user
    });
  }

  createLoadingBar() {
    const centerX = this.cameras.main.width / 2;
    const centerY = this.cameras.main.height / 2;

    this.loadingText = this.add.text(centerX, centerY - 50, 'Loading...', {
      font: '24px Arial',
      fill: '#ffffff'
    }).setOrigin(0.5);

    // Background of the loading bar
    this.loadingBg = this.add.image(centerX, centerY, 'loader-bg').setOrigin(0.5);

    // Filling part of the loading bar
    this.loadingFill = this.add.image(centerX - this.loadingBg.width / 2 + 4, centerY, 'loader-fill').setOrigin(0, 0.5); // Align left edge
    this.loadingFill.setCrop(0, 0, 0, this.loadingFill.height); // Initially crop to zero width

    this.percentText = this.add.text(centerX, centerY + 50, '0%', {
      font: '18px Arial',
      fill: '#ffffff'
    }).setOrigin(0.5);
  }

  updateLoadingBar(value) {
    if (this.loadingFill) {
      const fillWidth = (this.loadingBg.width - 8) * value; // Calculate width based on progress (-8 for padding)
      this.loadingFill.setCrop(0, 0, fillWidth, this.loadingFill.height);
    }
    if (this.percentText) {
      this.percentText.setText(parseInt(value * 100) + '%');
    }
  }

  create() {
    // This scene transitions immediately after preload is complete
    console.log('PreloadScene: Create (should transition immediately)');
  }
}