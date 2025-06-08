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
    // Load UI assets from the slot-specific directory using asset_dir instead of short_name
    const basePath = slotGameJsonConfig.game?.asset_dir || `/${slotApiData.short_name}/`;
    
    // Load slot-specific UI buttons
    this.load.image('spin-button', `${basePath}spin.png`);
    this.load.image('settings-button', `${basePath}settings.png`);
    this.load.image('turbo-button', `${basePath}autospin.png`); // Using autospin.png for turbo
    this.load.image('auto-button', `${basePath}autospin.png`);
    
    // Load generic UI assets from /ui/ if they exist, otherwise use slot-specific fallbacks
    this.load.image('sound-on-button', '/ui/sound_on_button.png');
    this.load.image('sound-off-button', '/ui/sound_off_button.png');
    this.load.image('bet-increase-button', '/ui/bet_increase.png');
    this.load.image('bet-decrease-button', '/ui/bet_decrease.png');
    this.load.image('max-bet-button', '/ui/max_bet.png');
    this.load.image('paytable-button', '/ui/paytable_button.png');
    this.load.image('close-button', '/ui/close_button.png'); // For modals
    
    // Load win particle effect - use coin.png from slot directory as fallback
    this.load.image('win-particle', `${basePath}coin.png`);


    // --- Load Slot-Specific Assets ---
    // Use slotApiData for the base path (via short_name)
    // Use slotGameJsonConfig for the list of assets and their relative paths within the slot's folder

    // Background
    let bgPath = null;
    if (slotGameJsonConfig.assets?.background) {
      bgPath = slotGameJsonConfig.assets.background;
    } else if (slotGameJsonConfig.game?.background?.image) {
      bgPath = slotGameJsonConfig.game.background.image;
    }
    
    if (bgPath) {
      // Handle absolute vs relative paths
      const backgroundPath = bgPath.startsWith('/') ? bgPath : `${basePath}${bgPath}`;
      this.load.image('background', backgroundPath);
    } else {
      console.warn(`Slots PreloadScene: Background image not defined in slotGameJsonConfig for ${slotApiData.short_name}. Using default.`);
      // Use a fallback that actually exists - the bg.png in slot1
      this.load.image('background', '/slot1/bg.png');
    }

    // Symbols - from slotGameJsonConfig.game.symbols
    if (slotGameJsonConfig.game && slotGameJsonConfig.game.symbols && Array.isArray(slotGameJsonConfig.game.symbols)) {
      slotGameJsonConfig.game.symbols.forEach(symbol => {
        if (symbol.id !== undefined && symbol.icon) {
          // Handle both absolute and relative paths correctly
          let symbolPath;
          if (symbol.icon.startsWith('/')) {
            // Icon path is already absolute, use it directly
            symbolPath = symbol.icon;
          } else {
            // Icon path is relative, combine with basePath
            symbolPath = `${basePath}${symbol.icon}`;
          }
          
          // Key used here: `symbol-${symbol.id}` must match GameScene.js (and potentially BonusHoldAndWinScene)
          this.load.image(`symbol-${symbol.id}`, symbolPath);
        } else {
          console.warn('Slots PreloadScene: Symbol missing id or icon path in slotGameJsonConfig.game.symbols.', symbol);
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

    // Load HoldAndWin Bonus Specific Background Asset
    if (slotGameJsonConfig.holdAndWinBonus && slotGameJsonConfig.holdAndWinBonus.bonusBackgroundAsset) {
        const bonusBgPath = slotGameJsonConfig.holdAndWinBonus.bonusBackgroundAsset;
        // Ensure path is relative to the slot's asset directory
        const fullPath = `${basePath}${bonusBgPath.startsWith('/') ? bonusBgPath.substring(1) : bonusBgPath}`;
        this.load.image('bonus_background_specific', fullPath);
        console.log(`Preloading HoldAndWin specific background: bonus_background_specific from ${fullPath}`);
    }


    // Load Slot-Specific Audio Assets from slotGameJsonConfig.assets.sounds
    if (slotGameJsonConfig.assets && slotGameJsonConfig.assets.sounds) {
      for (const key in slotGameJsonConfig.assets.sounds) {
        if (Object.prototype.hasOwnProperty.call(slotGameJsonConfig.assets.sounds, key)) {
          const soundPathOrPaths = slotGameJsonConfig.assets.sounds[key];
          const soundKey = `snd-${slotApiData.short_name}-${key}`;
          let assetPathArray;
          const processPath = p => `${basePath}${p.startsWith('/') ? p.substring(1) : p}`;

          if (typeof soundPathOrPaths === 'string') {
            assetPathArray = [processPath(soundPathOrPaths)];
          } else if (Array.isArray(soundPathOrPaths)) {
            assetPathArray = soundPathOrPaths.map(processPath);
          } else {
            console.warn(`Slots PreloadScene: Invalid sound path format for ${key} in ${slotApiData.short_name}`);
            continue;
          }
          this.load.audio(soundKey, assetPathArray);
        }
      }
    }

    // Load HoldAndWin Bonus Specific Music
    if (slotGameJsonConfig.holdAndWinBonus && slotGameJsonConfig.holdAndWinBonus.bonusMusic) {
        const bonusMusicPath = slotGameJsonConfig.holdAndWinBonus.bonusMusic;
        const musicKey = `snd-${slotApiData.short_name}-holdAndWinMusic`;
        // Ensure path is relative to the slot's asset directory
        const fullMusicPath = `${basePath}${bonusMusicPath.startsWith('/') ? bonusMusicPath.substring(1) : bonusMusicPath}`;
        this.load.audio(musicKey, [fullMusicPath]); // Phaser expects an array of paths for audio
        console.log(`Preloading HoldAndWin specific music: ${musicKey} from ${fullMusicPath}`);
    }

    // --- Load Common Audio Assets ---
    // These keys should be different from slot-specific ones to avoid conflicts if a slot defines 'spin', 'reel_stop' etc.
    // For now, comment out missing audio assets to prevent 404 errors
    // this.load.audio('snd-common-spin', ['/assets/slots/audio/spin.mp3', '/assets/slots/audio/spin.ogg']);
    // this.load.audio('snd-common-reel-stop', ['/assets/slots/audio/reel_stop.mp3', '/assets/slots/audio/reel_stop.ogg']);
    // this.load.audio('snd-common-win-small', ['/assets/slots/audio/win_small.mp3', '/assets/slots/audio/win_small.ogg']);
    // this.load.audio('snd-common-win-medium', ['/assets/slots/audio/win_medium.mp3', '/assets/slots/audio/win_medium.ogg']);
    // this.load.audio('snd-common-win-large', ['/assets/slots/audio/win_large.mp3', '/assets/slots/audio/win_large.ogg']);
    // this.load.audio('snd-common-bonus-trigger', ['/assets/slots/audio/bonus_trigger.mp3', '/assets/slots/audio/bonus_trigger.ogg']);
    // this.load.audio('snd-common-button-click', ['/assets/slots/audio/button_click.mp3', '/assets/slots/audio/button_click.ogg']);


    // Particle Effects (Example) - comment out until assets exist
    // this.load.image('win-particle-star', '/assets/slots/particles/star.png');
    // this.load.image('win-particle-coin', '/assets/slots/particles/coin.png');
  }

  create() {
    console.log('Slots PreloadScene: create() - transitioning to scenes.');

    // Check if critical configs were loaded before proceeding
    // Note: criticalConfigError is defined in preload() scope. Re-check registry or pass via a scene property if needed here.
    // For simplicity, we assume if preload reached this point, criticals were okay or handled.
    // However, for robustness, a check like this would be better:
    const slotApiData = this.registry.get('slotApiData');
    const slotGameJsonConfig = this.registry.get('slotGameJsonConfig');
    if (!slotApiData || !slotApiData.short_name || !slotGameJsonConfig) {
        console.error("Slots PreloadScene: Halting creation due to missing critical configuration detected in create().");
        // Optionally, display an error message on screen if not already handled by preload's text
        if (!this.scene.get('ErrorScene')) { // Prevent multiple error displays if preload already showed one
             this.add.text(this.cameras.main.width / 2, this.cameras.main.height / 2, 'Error: Config missing in create().', { font: '18px Arial', fill: '#ff0000', align: 'center' }).setOrigin(0.5);
        }
        return;
    }

    this.scene.launch('UIScene');
    this.scene.launch('SettingsModalScene');
    this.scene.sleep('SettingsModalScene');

    this.scene.start('GameScene');
  }
}
