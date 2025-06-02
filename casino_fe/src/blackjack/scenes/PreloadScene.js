import Phaser from 'phaser';

export default class PreloadScene extends Phaser.Scene {
  constructor() {
    super({ key: 'PreloadScene' });
  }

  preload() {
    // --- Display Loading Bar ---
    const progressBar = this.add.graphics();
    const progressBox = this.add.graphics();
    const width = this.cameras.main.width;
    const height = this.cameras.main.height;
    const loadingText = this.make.text({
      x: width / 2,
      y: height / 2 - 50,
      text: 'Loading...',
      style: {
        font: '20px monospace',
        fill: '#ffffff',
      },
    });
    loadingText.setOrigin(0.5, 0.5);

    const percentText = this.make.text({
      x: width / 2,
      y: height / 2,
      text: '0%',
      style: {
        font: '18px monospace',
        fill: '#ffffff',
      },
    });
    percentText.setOrigin(0.5, 0.5);

    progressBox.fillStyle(0x222222, 0.8);
    progressBox.fillRect(width / 2 - 160, height / 2 - 30 + 20, 320, 50);

    this.load.on('progress', (value) => {
      percentText.setText(parseInt(value * 100, 10) + '%');
      progressBar.clear();
      progressBar.fillStyle(0xffffff, 1);
      progressBar.fillRect(width / 2 - 150, height / 2 - 20 + 20, 300 * value, 30);
    });

    this.load.on('complete', () => {
      progressBar.destroy();
      progressBox.destroy();
      loadingText.destroy();
      percentText.destroy();
    });

    // --- Load Game Assets ---

    // Table and General UI
    this.load.image('blackjack-background', 'public/assets/blackjack/background.png');
    this.load.image('blackjack-table', 'public/assets/blackjack/table.png');
    this.load.image('card-back', 'public/assets/cards/cardBack.png');

    // Card Sprites (RankSuit@1x.png convention)
    const suits = ['C', 'D', 'H', 'S']; // Clubs, Diamonds, Hearts, Spades
    const ranks = ['A', '2', '3', '4', '5', '6', '7', '8', '9', 'T', 'J', 'Q', 'K'];

    suits.forEach(suit => {
      ranks.forEach(rank => {
        const cardKey = `card-${rank}${suit}`;
        const cardPath = `public/cards/${rank}${suit}@1x.png`;
        this.load.image(cardKey, cardPath);
      });
    });

    // Chip Images (dynamically from gameDefinition)
    // Retrieve gameDefinition from registry, set by Vue component
    const gameDefinition = this.registry.get('gameDefinition');
    if (gameDefinition && gameDefinition.settings && gameDefinition.settings.chipValues) {
      gameDefinition.settings.chipValues.forEach(value => {
        this.load.image(`chip-${value}`, `public/assets/chips/chip_${value}.png`);
      });
    } else {
      // Fallback if gameDefinition is not available or chipValues are not set
      const defaultChipValues = [5, 10, 25, 100, 500]; // Common default values
      defaultChipValues.forEach(value => {
        this.load.image(`chip-${value}`, `public/assets/chips/chip_${value}.png`);
      });
      console.warn('PreloadScene: Chip values not found in gameDefinition registry. Loading default chip images.');
    }

    // UI Button Assets
    this.load.image('button-deal', 'public/assets/blackjack/ui/button_deal.png');
    this.load.image('button-hit', 'public/assets/blackjack/ui/button_hit.png');
    this.load.image('button-stand', 'public/assets/blackjack/ui/button_stand.png');
    this.load.image('button-double', 'public/assets/blackjack/ui/button_double.png');
    this.load.image('button-split', 'public/assets/blackjack/ui/button_split.png');
    this.load.image('button-rebet', 'public/assets/blackjack/ui/button_rebet.png');
    this.load.image('button-new-round', 'public/assets/blackjack/ui/button_new_round.png');

    // Audio Assets
    // Providing both mp3 and ogg for wider browser compatibility
    this.load.audio('snd-card-deal', ['public/assets/blackjack/audio/card_deal.mp3', 'public/assets/blackjack/audio/card_deal.ogg']);
    this.load.audio('snd-chip-place', ['public/assets/blackjack/audio/chip_place.mp3', 'public/assets/blackjack/audio/chip_place.ogg']);
    this.load.audio('snd-win', ['public/assets/blackjack/audio/win.mp3', 'public/assets/blackjack/audio/win.ogg']);
    this.load.audio('snd-lose', ['public/assets/blackjack/audio/lose.mp3', 'public/assets/blackjack/audio/lose.ogg']);
    this.load.audio('snd-push', ['public/assets/blackjack/audio/push.mp3', 'public/assets/blackjack/audio/push.ogg']);
    this.load.audio('snd-blackjack', ['public/assets/blackjack/audio/blackjack.mp3', 'public/assets/blackjack/audio/blackjack.ogg']);
    this.load.audio('snd-button-click', ['public/assets/blackjack/audio/button_click.mp3', 'public/assets/blackjack/audio/button_click.ogg']);
    this.load.audio('snd-shuffle', ['public/assets/blackjack/audio/shuffle.mp3', 'public/assets/blackjack/audio/shuffle.ogg']);
  }

  create() {
    // Start the main game scene and UI scene
    // UIScene is launched in parallel to GameScene. It will typically overlay GameScene.
    this.scene.launch('UIScene');
    this.scene.start('GameScene'); // Start will shut down PreloadScene and start GameScene.

    console.log('PreloadScene complete, starting GameScene and UIScene.');
  }
}
