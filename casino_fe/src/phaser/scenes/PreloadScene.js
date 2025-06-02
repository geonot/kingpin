import Phaser from 'phaser';

export default class PreloadScene extends Phaser.Scene {
  constructor() {
    super({ key: 'PreloadScene' });
  }

  preload() {
    console.log('Slots PreloadScene: preload()');
    const slotApiData = this.registry.get('slotApiData');
    const slotGameJsonConfig = this.registry.get('slotGameJsonConfig');

    let criticalConfigError = false;
    if (!slotApiData || !slotApiData.short_name) {
      console.error('Slots PreloadScene: slotApiData (especially short_name) not found in registry.');
      criticalConfigError = true;
    }
    if (!slotGameJsonConfig) {
      console.error('Slots PreloadScene: slotGameJsonConfig not found in registry.');
      criticalConfigError = true;
    }

    if (criticalConfigError) {
        this.add.text(this.cameras.main.width / 2, this.cameras.main.height / 2, 'Error: Critical slot configuration missing.\nPlease try reloading.', { font: '18px Arial', fill: '#ff0000', align: 'center' }).setOrigin(0.5);
        // Stop further asset loading if critical configs are missing
        return;
    }

    // --- Display Loading Bar ---
    const progressBar = this.add.graphics();
    const progressBox = this.add.graphics();
    const width = this.cameras.main.width;
    const height = this.cameras.main.height;

    const loadingText = this.make.text({
      x: width / 2,
      y: height / 2 - 50,
      text: 'Loading Slot...',
      style: { font: '20px Arial', fill: '#ffffff' }, // Changed font for better default availability
    }).setOrigin(0.5, 0.5);

    const percentText = this.make.text({
      x: width / 2,
      y: height / 2,
      text: '0%',
      style: { font: '18px Arial', fill: '#ffffff' }, // Changed font
    }).setOrigin(0.5, 0.5);

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
      console.log('Slots PreloadScene: Asset loading complete.');
    });

    // --- Load Common UI Assets ---
    this.load.image('ui-spin-button', 'public/assets/slots/ui/spin_button.png');
    this.load.image('ui-settings-button', 'public/assets/slots/ui/settings_button.png');
    this.load.image('ui-turbo-button', 'public/assets/slots/ui/turbo_button.png');
    this.load.image('ui-sound-on-button', 'public/assets/slots/ui/sound_on_button.png');
    this.load.image('ui-sound-off-button', 'public/assets/slots/ui/sound_off_button.png');
    this.load.image('ui-bet-increase-button', 'public/assets/slots/ui/bet_increase.png');
    this.load.image('ui-bet-decrease-button', 'public/assets/slots/ui/bet_decrease.png');
    this.load.image('ui-max-bet-button', 'public/assets/slots/ui/max_bet.png');
    this.load.image('ui-paytable-button', 'public/assets/slots/ui/paytable_button.png');
    this.load.image('ui-close-button', 'public/assets/slots/ui/close_button.png'); // For modals


    // --- Load Slot-Specific Assets ---
    // Use slotApiData for the base path (via short_name)
    // Use slotGameJsonConfig for the list of assets and their relative paths within the slot's folder

    const basePath = `public/slots/${slotApiData.short_name}/`;

    // Background
    const bgAsset = slotGameJsonConfig.assets?.background;
    if (bgAsset) {
      this.load.image('background', `${basePath}${bgAsset}`);
    } else {
      console.warn(`Slots PreloadScene: Background image not defined in slotGameJsonConfig.assets for ${slotApiData.short_name}. Loading fallback.`);
      this.load.image('background', 'public/assets/slots/default_background.png');
    }

    // Symbols - from slotGameJsonConfig.game.symbols
    if (slotGameJsonConfig.game && slotGameJsonConfig.game.symbols && Array.isArray(slotGameJsonConfig.game.symbols)) {
      slotGameJsonConfig.game.symbols.forEach(symbol => {
        if (symbol.id !== undefined && symbol.image) {
          // Key used here: `symbol-${symbol.id}` must match GameScene.js
          this.load.image(`symbol-${symbol.id}`, `${basePath}${symbol.image}`);
        } else {
          console.warn('Slots PreloadScene: Symbol missing id or image path in slotGameJsonConfig.game.symbols.', symbol);
        }
      });
    } else {
      console.warn(`Slots PreloadScene: Symbols array not found or invalid in slotGameJsonConfig.game.symbols for ${slotApiData.short_name}`);
    }

    // Optional Assets from slotGameJsonConfig.assets
    if (slotGameJsonConfig.assets) {
        if (slotGameJsonConfig.assets['reel-frame']) {
            this.load.image('reel-frame', `${basePath}${slotGameJsonConfig.assets['reel-frame']}`);
        }
        if (slotGameJsonConfig.assets['paytable_bg']) {
            this.load.image('paytable-bg', `${basePath}${slotGameJsonConfig.assets['paytable_bg']}`);
        }
        if (slotGameJsonConfig.assets['bonus_background']) {
            this.load.image('bonus-background', `${basePath}${slotGameJsonConfig.assets['bonus_background']}`);
        }
    }

    // Load Slot-Specific Audio Assets from slotGameJsonConfig.assets.sounds
    if (slotGameJsonConfig.assets && slotGameJsonConfig.assets.sounds) {
      for (const key in slotGameJsonConfig.assets.sounds) {
        if (Object.prototype.hasOwnProperty.call(slotGameJsonConfig.assets.sounds, key)) {
          const soundPathOrPaths = slotGameJsonConfig.assets.sounds[key];
          // Create a unique key for slot-specific sounds to avoid clashes with common sounds
          const soundKey = `snd-${slotApiData.short_name}-${key}`;

          let assetPathArray;
          if (typeof soundPathOrPaths === 'string') {
            assetPathArray = [`${basePath}${soundPathOrPaths}`];
          } else if (Array.isArray(soundPathOrPaths)) {
            assetPathArray = soundPathOrPaths.map(p => `${basePath}${p}`);
          } else {
            console.warn(`Slots PreloadScene: Invalid sound path format for ${key} in ${slotApiData.short_name}`);
            continue;
          }
          this.load.audio(soundKey, assetPathArray);
        }
      }
    }

    // --- Load Common Audio Assets ---
    // These keys should be different from slot-specific ones to avoid conflicts if a slot defines 'spin', 'reel_stop' etc.
    this.load.audio('snd-common-spin', ['public/assets/slots/audio/spin.mp3', 'public/assets/slots/audio/spin.ogg']);
    this.load.audio('snd-common-reel-stop', ['public/assets/slots/audio/reel_stop.mp3', 'public/assets/slots/audio/reel_stop.ogg']);
    this.load.audio('snd-common-win-small', ['public/assets/slots/audio/win_small.mp3', 'public/assets/slots/audio/win_small.ogg']);
    this.load.audio('snd-common-win-medium', ['public/assets/slots/audio/win_medium.mp3', 'public/assets/slots/audio/win_medium.ogg']);
    this.load.audio('snd-common-win-large', ['public/assets/slots/audio/win_large.mp3', 'public/assets/slots/audio/win_large.ogg']);
    this.load.audio('snd-common-bonus-trigger', ['public/assets/slots/audio/bonus_trigger.mp3', 'public/assets/slots/audio/bonus_trigger.ogg']);
    this.load.audio('snd-common-button-click', ['public/assets/slots/audio/button_click.mp3', 'public/assets/slots/audio/button_click.ogg']);


    // Particle Effects (Example)
    this.load.image('win-particle-star', 'public/assets/slots/particles/star.png');
    this.load.image('win-particle-coin', 'public/assets/slots/particles/coin.png');
  }

  create() {
    console.log('Slots PreloadScene: create() - transitioning to scenes.');

    // Check if critical configs were loaded before proceeding
    if (criticalConfigError) { // This var was set at the beginning of preload()
        console.error("Slots PreloadScene: Halting creation due to missing critical configuration.");
        // Optionally, you could transition to a dedicated ErrorScene:
        // this.scene.start('ErrorScene', { message: 'Slot configuration failed to load.' });
        return;
    }

    this.scene.launch('UIScene');
    this.scene.launch('SettingsModalScene');
    this.scene.sleep('SettingsModalScene');

    this.scene.start('GameScene');
  }
}
