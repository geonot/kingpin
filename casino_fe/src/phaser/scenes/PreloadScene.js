import Phaser from 'phaser';

export default class PreloadScene extends Phaser.Scene {
    constructor() {
        super({ key: 'PreloadScene' });
    }

    preload() {
        console.log('PreloadScene: Preload');
        const gameConfig = this.registry.get('gameConfig');
        const slotShortName = this.registry.get('slotShortName'); // Get slotShortName

        if (!gameConfig) {
            console.error("PreloadScene: Game config not found in registry!");
            // Optionally emit an event or stop the scene
            this.registry.get('eventBus')?.emit('phaserError', 'Game configuration missing in PreloadScene.');
            return;
        }
        if (!slotShortName) {
            console.error("PreloadScene: slotShortName not found in registry! Asset paths will be incorrect.");
            // Fallback to a default or handle error
            this.registry.get('eventBus')?.emit('phaserError', 'Slot identifier missing for assets.');
            return;
        }

        this.createLoadingBar();

        // --- Load Game Assets Based on Config ---
        const assetBaseUrl = `/public/${slotShortName}/`; // Base path for this slot's assets e.g. /public/slot1/

        // 1. Background Image
        if (gameConfig.background?.image) {
            // Assuming gameConfig.background.image is relative to the slot's asset folder e.g., "background.png" or "images/bg.jpg"
            this.load.image('background', `${assetBaseUrl}${gameConfig.background.image.replace(/^\//, '')}`);
        }

        // 2. Symbol Images
        if (gameConfig.symbols && Array.isArray(gameConfig.symbols)) {
            gameConfig.symbols.forEach(symbol => {
                if (symbol.icon) { // symbol.icon is like "symbols/symbol_0.png"
                    this.load.image(`symbol_${symbol.id}`, `${assetBaseUrl}${symbol.icon.replace(/^\//, '')}`);
                }
            });
        }

        // 3. UI Button Images & Other UI Assets from gameConfig.json
        // Assuming gameConfig.ui.buttons paths are also relative to assetBaseUrl
        if (gameConfig.ui?.buttons) {
            Object.entries(gameConfig.ui.buttons).forEach(([key, buttonData]) => {
                // buttonData could be a string (path) or an object {name, icon}
                let iconPath = '';
                let loadKey = key; // Use the key from gameConfig.ui.buttons as the Phaser asset key

                if (typeof buttonData === 'string') { // e.g. "spin_button": "ui/spin_button.png"
                    iconPath = buttonData;
                } else if (buttonData && buttonData.icon) { // e.g. "spin_button": { "name": "spinButton", "icon": "ui/spin_button.png" }
                    iconPath = buttonData.icon;
                    if(buttonData.name) loadKey = buttonData.name; // Use provided name if available
                }

                if (iconPath) {
                    this.load.image(loadKey, `${assetBaseUrl}${iconPath.replace(/^\//, '')}`);
                }
            });
        }
        // Common UI assets (not slot-specific, loaded from /public/assets/ui/)
        // These were already loaded in BootScene for the loader itself, but if others are needed:
        this.load.image('settings-button', '/assets/ui/settings.png');
        this.load.image('payline-dot', '/assets/ui/payline_dot.png');
        this.load.image('win-particle', '/assets/ui/particle.png');


        // 4. Audio Files
        if (gameConfig.sound) {
            Object.entries(gameConfig.sound).forEach(([key, path]) => {
                if (path && typeof path === 'string') { // Ensure path is a string
                    // Assuming sound paths in gameConfig are relative to the slot's asset folder
                    const fullPath = `${assetBaseUrl}${path.replace(/^\//, '')}`;
                    console.log(`Loading sound: ${key} from ${fullPath}`);
                    this.load.audio(key, fullPath);
                } else if (path && path.src && typeof path.src === 'string') { // Handle if path is an object like {src: "...", volume: 1}
                    const fullPath = `${assetBaseUrl}${path.src.replace(/^\//, '')}`;
                    console.log(`Loading sound: ${key} from ${fullPath}`);
                    this.load.audio(key, fullPath);
                }
            });
        }

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

